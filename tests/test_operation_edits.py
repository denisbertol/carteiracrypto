"""Testes para edição e exclusão de lançamentos (PATCH e DELETE /api/v1/operations/{id})."""

import json
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

from fastapi import HTTPException, Response
from starlette.requests import Request

from app.domain.ledger import InsufficientBalanceError, InvalidOperationError
from app.routes.api import (
    UpdateOperationInput,
    update_operation,
    delete_operation,
)
from app.services.portfolio import compute_request_hash


class MockDbCursor:
    def __init__(self, portfolio_id, user_id, usdt_id, btc_id, revision=1):
        self.portfolio_id = portfolio_id
        self.user_id = user_id
        self.usdt_id = usdt_id
        self.btc_id = btc_id
        self.revision = revision
        self.executed = []
        self.existing_op = None
        self.all_ops_rows = []
        self.receipt = None
        self.asset_symbol = "BTC"

    def execute(self, query, params=None):
        q = " ".join(query.strip().split())
        self.executed.append((q, params))

    def fetchone(self):
        last_q = self.executed[-1][0].upper()
        if "MUTATION_RECEIPTS" in last_q:
            return self.receipt
        if "FROM PORTFOLIO_PRIVATE.PORTFOLIOS WHERE OWNER_ID" in last_q:
            return (str(self.portfolio_id), self.revision)
        if "FROM PORTFOLIO_PRIVATE.PORTFOLIOS WHERE ID" in last_q:
            return (self.revision,)
        if "SELECT ID FROM PORTFOLIO_PRIVATE.ASSETS" in last_q and "SYMBOL = 'USDT'" in last_q:
            return (str(self.usdt_id),)
        if "FROM PORTFOLIO_PRIVATE.OPERATIONS" in last_q and "WHERE O.PORTFOLIO_ID" in last_q:
            return self.existing_op
        if "SELECT SYMBOL FROM PORTFOLIO_PRIVATE.ASSETS" in last_q:
            return (self.asset_symbol,)
        return None

    def fetchall(self):
        last_q = self.executed[-1][0].upper()
        if "FROM PORTFOLIO_PRIVATE.OPERATIONS" in last_q:
            return self.all_ops_rows
        return []


class MockDbConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        @contextmanager
        def ctx():
            yield self._cursor
        return ctx()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def make_request(method="PATCH", path="/api/v1/operations/test"):
    return Request({
        "type": "http",
        "method": method,
        "path": path,
        "headers": [],
        "query_string": b"",
        "server": ("test", 80),
    })


class TestOperationEdits(unittest.TestCase):
    def setUp(self):
        self.portfolio_id = uuid4()
        self.user_id = uuid4()
        self.usdt_id = uuid4()
        self.btc_id = uuid4()
        self.op_id = uuid4()
        self.cursor = MockDbCursor(self.portfolio_id, self.user_id, self.usdt_id, self.btc_id, revision=3)
        self.conn = MockDbConnection(self.cursor)

    def test_update_requires_idempotency_key(self):
        req = make_request("PATCH", f"/api/v1/operations/{self.op_id}")
        body = UpdateOperationInput(quantity=Decimal("5"))
        with self.assertRaises(HTTPException) as ctx:
            update_operation(
                self.op_id, body, Response(), req, idempotency_key=None, user_id=self.user_id
            )
        self.assertEqual(ctx.exception.status_code, 428)

    def test_update_revision_conflict(self):
        req = make_request("PATCH", f"/api/v1/operations/{self.op_id}")
        body = UpdateOperationInput(quantity=Decimal("5"))
        with patch("app.routes.api.get_db_connection", return_value=self.conn), \
             patch("app.routes.api.lock_portfolio_for_update", return_value=(self.portfolio_id, 3)):
            with self.assertRaises(HTTPException) as ctx:
                update_operation(
                    self.op_id, body, Response(), req,
                    idempotency_key=uuid4(), if_match='"2"', user_id=self.user_id
                )
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertEqual(ctx.exception.detail["error"]["code"], "REVISION_CONFLICT")

    def test_update_operation_not_found(self):
        req = make_request("PATCH", f"/api/v1/operations/{self.op_id}")
        body = UpdateOperationInput(quantity=Decimal("5"))
        self.cursor.existing_op = None
        with patch("app.routes.api.get_db_connection", return_value=self.conn), \
             patch("app.routes.api.lock_portfolio_for_update", return_value=(self.portfolio_id, 3)):
            with self.assertRaises(HTTPException) as ctx:
                update_operation(
                    self.op_id, body, Response(), req,
                    idempotency_key=uuid4(), if_match='"3"', user_id=self.user_id
                )
            self.assertEqual(ctx.exception.status_code, 404)

    def test_update_operation_idempotency_replay(self):
        req = make_request("PATCH", f"/api/v1/operations/{self.op_id}")
        body = UpdateOperationInput(quantity=Decimal("5"))
        idem_key = uuid4()
        req_hash = compute_request_hash("PATCH", f"/api/v1/operations/{self.op_id}", body.model_dump(mode="json"), 3)
        saved_body = {"operation": {"id": str(self.op_id)}, "revision": 4}
        self.cursor.receipt = (req_hash, 200, saved_body)

        response = Response()
        with patch("app.routes.api.get_db_connection", return_value=self.conn), \
             patch("app.routes.api.lock_portfolio_for_update", return_value=(self.portfolio_id, 3)):
            result = update_operation(
                self.op_id, body, response, req,
                idempotency_key=idem_key, if_match='"3"', user_id=self.user_id
            )
            self.assertEqual(result, saved_body)
            self.assertEqual(response.headers.get("Idempotency-Replayed"), "true")

    def test_update_operation_success_ca08(self):
        """CA-08: Corrigir o preço de compra de 100 para 120 e recalcular carteira."""
        t1 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)

        # Existing: Deposit 1000 USDT, Buy 2 BTC at 100, Sell 1 BTC at 150
        dep_id = uuid4()
        buy_id = self.op_id
        sell_id = uuid4()

        # Existing buy operation to be edited:
        self.cursor.existing_op = (
            str(buy_id), str(self.btc_id), "BTC", "buy", t2, 1,
            "2", "100", "0", None, None, None, None
        )
        self.cursor.all_ops_rows = [
            (str(dep_id), str(self.usdt_id), "USDT", "deposit", t1, 0, "1000", None, "0", None, None, None, None),
            (str(buy_id), str(self.btc_id), "BTC", "buy", t2, 1, "2", "100", "0", None, None, None, None),
            (str(sell_id), str(self.btc_id), "BTC", "sell", t3, 2, "1", "150", "0", None, None, None, None),
        ]

        # Update buy price to 120
        body = UpdateOperationInput(unit_price_usd=Decimal("120"))
        req = make_request("PATCH", f"/api/v1/operations/{buy_id}")
        response = Response()

        with patch("app.routes.api.get_db_connection", return_value=self.conn), \
             patch("app.routes.api.lock_portfolio_for_update", return_value=(self.portfolio_id, 3)):
            result = update_operation(
                buy_id, body, response, req,
                idempotency_key=uuid4(), if_match='"3"', user_id=self.user_id
            )

        self.assertEqual(result["revision"], 4)
        self.assertEqual(result["operation"]["unit_price_usd"], "120")
        self.assertTrue(self.conn.committed)

        # Check audit record was created with action 'update'
        audit_queries = [q for q in self.cursor.executed if "OPERATION_AUDIT" in q[0].upper()]
        self.assertEqual(len(audit_queries), 1)
        self.assertEqual(audit_queries[0][1][2], "update")

    def test_update_operation_insufficient_balance_ca10(self):
        """CA-10: Correção retroativa que causa saldo negativo posterior é rejeitada integralmente."""
        t1 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)

        dep_id = uuid4()
        buy_id = self.op_id
        sell_id = uuid4()

        # Buy originally bought 2 units. A later sale sold 2 units.
        self.cursor.existing_op = (
            str(buy_id), str(self.btc_id), "BTC", "buy", t2, 1,
            "2", "100", "0", None, None, None, None
        )
        self.cursor.all_ops_rows = [
            (str(dep_id), str(self.usdt_id), "USDT", "deposit", t1, 0, "1000", None, "0", None, None, None, None),
            (str(buy_id), str(self.btc_id), "BTC", "buy", t2, 1, "2", "100", "0", None, None, None, None),
            (str(sell_id), str(self.btc_id), "BTC", "sell", t3, 2, "2", "150", "0", None, None, None, None),
        ]

        # Reducing buy quantity to 1 -> sale of 2 units now exceeds balance!
        body = UpdateOperationInput(quantity=Decimal("1"))
        req = make_request("PATCH", f"/api/v1/operations/{buy_id}")
        response = Response()

        with patch("app.routes.api.get_db_connection", return_value=self.conn), \
             patch("app.routes.api.lock_portfolio_for_update", return_value=(self.portfolio_id, 3)):
            with self.assertRaises(HTTPException) as ctx:
                update_operation(
                    buy_id, body, response, req,
                    idempotency_key=uuid4(), if_match='"3"', user_id=self.user_id
                )
            self.assertEqual(ctx.exception.status_code, 422)
            self.assertEqual(ctx.exception.detail["error"]["code"], "INSUFFICIENT_BALANCE")
            self.assertTrue(self.conn.rolled_back)

    def test_delete_operation_success_ca08(self):
        """CA-08: Excluir a venda retorna a posição para o estado anterior."""
        t1 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)

        dep_id = uuid4()
        buy_id = uuid4()
        sell_id = self.op_id

        self.cursor.existing_op = (
            str(sell_id), str(self.btc_id), "BTC", "sell", t3, 2,
            "1", "150", "0", None, None, None, None
        )
        # Remaining rows after removing sell_id:
        self.cursor.all_ops_rows = [
            (str(dep_id), str(self.usdt_id), "USDT", "deposit", t1, 0, "1000", None, "0", None, None, None, None),
            (str(buy_id), str(self.btc_id), "BTC", "buy", t2, 1, "2", "120", "0", None, None, None, None),
        ]

        req = make_request("DELETE", f"/api/v1/operations/{sell_id}")
        response = Response()

        with patch("app.routes.api.get_db_connection", return_value=self.conn), \
             patch("app.routes.api.lock_portfolio_for_update", return_value=(self.portfolio_id, 3)):
            result = delete_operation(
                sell_id, response, req,
                idempotency_key=uuid4(), if_match='"3"', user_id=self.user_id
            )

        self.assertEqual(result["id"], str(sell_id))
        self.assertTrue(result["deleted"])
        self.assertEqual(result["revision"], 4)
        self.assertTrue(self.conn.committed)

        # Check audit action is delete
        audit_queries = [q for q in self.cursor.executed if "OPERATION_AUDIT" in q[0].upper()]
        self.assertEqual(len(audit_queries), 1)
        self.assertEqual(audit_queries[0][1][2], "delete")

    def test_delete_operation_prevents_deficit(self):
        """Não permite excluir compra se uma venda posterior depender dela."""
        t1 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)

        dep_id = uuid4()
        buy_id = self.op_id
        sell_id = uuid4()

        self.cursor.existing_op = (
            str(buy_id), str(self.btc_id), "BTC", "buy", t2, 1,
            "2", "100", "0", None, None, None, None
        )
        # If buy_id is removed, only deposit and sell remain:
        self.cursor.all_ops_rows = [
            (str(dep_id), str(self.usdt_id), "USDT", "deposit", t1, 0, "1000", None, "0", None, None, None, None),
            (str(sell_id), str(self.btc_id), "BTC", "sell", t3, 2, "1", "150", "0", None, None, None, None),
        ]

        req = make_request("DELETE", f"/api/v1/operations/{buy_id}")
        response = Response()

        with patch("app.routes.api.get_db_connection", return_value=self.conn), \
             patch("app.routes.api.lock_portfolio_for_update", return_value=(self.portfolio_id, 3)):
            with self.assertRaises(HTTPException) as ctx:
                delete_operation(
                    buy_id, response, req,
                    idempotency_key=uuid4(), if_match='"3"', user_id=self.user_id
                )
            self.assertEqual(ctx.exception.status_code, 422)
            self.assertEqual(ctx.exception.detail["error"]["code"], "INSUFFICIENT_BALANCE")
            self.assertTrue(self.conn.rolled_back)


if __name__ == "__main__":
    unittest.main()
