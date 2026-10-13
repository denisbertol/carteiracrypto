import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException, Response
from pydantic import ValidationError

from app.routes.monitoring import (
    CreateTargetInput,
    PatchSettingsInput,
    PatchTargetInput,
    PutMappingInput,
    create_price_target,
    delete_price_target,
    get_monitoring_quotes,
    list_price_evaluations,
    list_price_notifications,
    patch_monitoring_settings,
    patch_price_target,
    post_monitoring_cycle,
    put_price_mapping,
)
from app.services.monitoring import CycleReservation
from app.services.quotes import QuoteStatus


class RouteCursor:
    def __init__(self):
        self.query = ""
        self.params = None
        self.rows = []
        self.one = None

    def execute(self, query, params=None):
        self.query = " ".join(query.lower().split())
        self.params = params

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.one


class RouteConnection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self._cursor = RouteCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        @contextmanager
        def cursor_context():
            yield self._cursor
        return cursor_context()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class MonitoringRouteTests(unittest.TestCase):
    def setUp(self):
        self.user_id, self.portfolio_id = uuid4(), uuid4()
        self.connection = RouteConnection()
        self.quote_reader = SimpleNamespace(get_quotes=Mock())
        self.portfolio_stub = SimpleNamespace(
            get_or_create_portfolio=lambda cur, user_id: (self.portfolio_id, 1, uuid4()),
            quotes=self.quote_reader,
        )

    def test_create_requires_idempotency_key_before_database_access(self):
        body = CreateTargetInput(
            asset_id=uuid4(), kind="buy", price_usd="60000", active=True
        )
        with self.assertRaises(HTTPException) as raised:
            create_price_target(
                body, Response(), idempotency_key=None, user_id=self.user_id
            )
        self.assertEqual(raised.exception.status_code, 428)

    def test_decimal_inputs_are_strings_and_if_match_is_required(self):
        with self.assertRaises(ValidationError):
            CreateTargetInput(asset_id=uuid4(), kind="buy", price_usd=60000)
        self.assertEqual(PatchSettingsInput(proximity_percent="10.25").proximity_percent, "10.25")
        with self.assertRaises(HTTPException) as raised:
            patch_price_target(
                uuid4(), PatchTargetInput(active=False), Response(),
                if_match=None, idempotency_key=uuid4(), user_id=self.user_id,
            )
        self.assertEqual(raised.exception.status_code, 428)

    def test_target_replay_returns_saved_body_and_no_store_header(self):
        saved = {"id": str(uuid4()), "version": 2, "price_usd": "60000"}
        calls = {}

        class TargetStub:
            def create_target(self, cur, portfolio_id, actor_id, **kwargs):
                calls.update(kwargs)
                return saved, True

        response = Response()
        with patch("app.routes.monitoring.get_db_connection", return_value=self.connection), \
             patch("app.routes.monitoring.portfolio_service", self.portfolio_stub), \
             patch("app.routes.monitoring.target_service", TargetStub()):
            result = create_price_target(
                CreateTargetInput(asset_id=uuid4(), kind="buy", price_usd="60000"),
                response,
                idempotency_key=uuid4(),
                user_id=self.user_id,
            )
        self.assertEqual(result, saved)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["Idempotency-Replayed"], "true")
        self.assertEqual(self.connection.commits, 1)
        self.assertIsInstance(calls["price_usd"], str)

    def test_mapping_uses_cached_catalog_ids_and_current_version(self):
        calls = {}
        expected_body = {"asset_id": str(uuid4()), "status": "valid", "version": 3}

        class MappingStub:
            def put_mapping(self, cur, portfolio_id, actor_id, asset_id, coin_id, **kwargs):
                calls.update(kwargs)
                calls["coin_id"] = coin_id
                return expected_body, False

        response = Response()
        with patch("app.routes.monitoring.ensure_provider_catalog", return_value={
                "state": "fresh", "coins": [{"id": "bitcoin"}, {"id": "ethereum"}]
             }), \
             patch("app.routes.monitoring.get_db_connection", return_value=self.connection), \
             patch("app.routes.monitoring.portfolio_service", self.portfolio_stub), \
             patch("app.routes.monitoring.mapping_service", MappingStub()):
            result = put_price_mapping(
                uuid4(), PutMappingInput(provider_coin_id="bitcoin"), response,
                if_match='"2"', idempotency_key=uuid4(), user_id=self.user_id,
            )
        self.assertEqual(result, expected_body)
        self.assertEqual(calls["expected_version"], 2)
        self.assertEqual(calls["catalog_ids"], {"bitcoin", "ethereum"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_settings_patch_preserves_idempotent_replay_status(self):
        saved = {"proximity_percent": "8.5", "version": 3}
        calls = {}

        class TargetStub:
            def update_settings(self, cur, portfolio_id, actor_id, percent, **kwargs):
                calls["percent"] = percent
                calls.update(kwargs)
                return saved, True

        response = Response()
        with patch("app.routes.monitoring.get_db_connection", return_value=self.connection), \
             patch("app.routes.monitoring.portfolio_service", self.portfolio_stub), \
             patch("app.routes.monitoring.target_service", TargetStub()):
            result = patch_monitoring_settings(
                PatchSettingsInput(proximity_percent="8.50"), response,
                if_match="2", idempotency_key=uuid4(), user_id=self.user_id,
            )
        self.assertEqual(result, saved)
        self.assertEqual(calls["expected_version"], 2)
        self.assertEqual(calls["percent"], "8.50")
        self.assertEqual(response.headers["Idempotency-Replayed"], "true")

    def test_blocked_cycle_returns_retry_after_without_running_provider(self):
        retry_at = datetime.now(timezone.utc) + timedelta(seconds=90)

        class CycleStub:
            def reserve_cycle(self, cur, portfolio_id, request_id, *, now, force=False):
                return CycleReservation(
                    "blocked", 429, next_retry_at=retry_at, reason="quota_exhausted"
                )

            def run_reserved_cycle(self, *args, **kwargs):
                raise AssertionError("ciclo bloqueado não deve iniciar o provedor")

        response = Response()
        with patch("app.routes.monitoring.get_db_connection", return_value=self.connection), \
             patch("app.routes.monitoring.portfolio_service", self.portfolio_stub), \
             patch("app.routes.monitoring.cycle_service", CycleStub()):
            result = post_monitoring_cycle(
                SimpleNamespace(client_request_id=uuid4(), force=False), response, user_id=self.user_id
            )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(result["cycle_id"], None)
        self.assertEqual(result["reason"], "quota_exhausted")
        self.assertGreaterEqual(int(response.headers["Retry-After"]), 89)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_replayed_cycle_reads_saved_status_instead_of_running_again(self):
        cycle_id = uuid4()
        due_at = datetime.now(timezone.utc) + timedelta(minutes=4)
        self.connection._cursor.one = (
            cycle_id, "completed", datetime.now(timezone.utc), datetime.now(timezone.utc), None, due_at
        )

        class CycleStub:
            def reserve_cycle(self, cur, portfolio_id, request_id, *, now, force=False):
                return CycleReservation(
                    "reserved", 201, cycle_id=cycle_id, next_due_at=due_at,
                    replayed=True,
                )

            def run_reserved_cycle(self, *args, **kwargs):
                raise AssertionError("replay de recibo não deve repetir o ciclo")

        response = Response()
        with patch("app.routes.monitoring.get_db_connection", return_value=self.connection), \
             patch("app.routes.monitoring.portfolio_service", self.portfolio_stub), \
             patch("app.routes.monitoring.cycle_service", CycleStub()):
            result = post_monitoring_cycle(
                SimpleNamespace(client_request_id=uuid4(), force=False), response, user_id=self.user_id
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(result["state"], "reused")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["cycle_id"], str(cycle_id))

    def test_evaluation_history_enforces_expiry_and_pagination_limit(self):
        response = Response()
        target_id = uuid4()
        with patch("app.routes.monitoring.get_db_connection", return_value=self.connection), \
             patch("app.routes.monitoring.portfolio_service", self.portfolio_stub):
            result = list_price_evaluations(
                response, limit=25, cursor=None, target_id=target_id, user_id=self.user_id
            )
        self.assertEqual(result, {"items": [], "next_cursor": None})
        self.assertIn("e.created_at > %s", self.connection._cursor.query)
        self.assertIn("e.target_id=%s", self.connection._cursor.query)
        self.assertEqual(self.connection._cursor.params[-1], 26)
        self.assertEqual(self.connection._cursor.params[2], str(target_id))
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_cycle_notification_query_suppresses_changed_targets(self):
        cycle_id = uuid4()
        calls = {}

        class NotificationStub:
            def list_history(self, cur, portfolio_id, **kwargs):
                calls.update(kwargs)
                return {"items": [], "next_cursor": None}

        response = Response()
        with patch("app.routes.monitoring.get_db_connection", return_value=self.connection), \
             patch("app.routes.monitoring.portfolio_service", self.portfolio_stub), \
             patch("app.routes.monitoring.notification_service", NotificationStub()):
            list_price_notifications(
                response, limit=50, cursor=None, cycle_id=cycle_id, user_id=self.user_id
            )
        self.assertEqual(calls["cycle_id"], cycle_id)
        self.assertTrue(calls["current_targets_only"])

    def test_quote_endpoint_reads_cache_and_includes_one_dollar_usdt(self):
        btc_id, usdt_id = uuid4(), uuid4()
        self.connection._cursor.rows = [
            (btc_id, "bitcoin", "BTC", "Bitcoin"),
            (usdt_id, "tether", "USDT", "Tether USD"),
        ]
        quote = SimpleNamespace(
            price_usd=Decimal("61000"), source="coingecko", quoted_at=datetime.now(timezone.utc),
            fetched_at=datetime.now(timezone.utc), status=QuoteStatus.STALE, error_code=None,
        )
        response = Response()
        with patch("app.routes.monitoring.get_db_connection", return_value=self.connection), \
             patch("app.routes.monitoring.portfolio_service", self.portfolio_stub) as portfolio:
            portfolio.quotes.get_quotes.return_value = {btc_id: quote}
            result = get_monitoring_quotes(response, user_id=self.user_id)
        self.assertEqual(result["items"][0]["freshness"], "stale")
        self.assertEqual(result["items"][1]["price_usd"], "1")
        self.assertEqual(result["items"][1]["source"], "usd_peg")
        portfolio.quotes.get_quotes.assert_called_once()
        args, kwargs = portfolio.quotes.get_quotes.call_args
        self.assertEqual(args[0], [btc_id])
        self.assertEqual(kwargs["portfolio_id"], self.portfolio_id)

    @patch("app.routes.monitoring.target_service.delete_target")
    def test_delete_price_target_route_success_and_conflict(self, mock_delete):
        target_id = uuid4()
        mock_delete.return_value = ({"id": str(target_id), "deleted": True}, False)
        with patch("app.routes.monitoring.portfolio_service", self.portfolio_stub), \
             patch("app.routes.monitoring.get_db_connection", return_value=self.connection):
            res = delete_price_target(
                target_id, Response(), if_match="1", idempotency_key=uuid4(), user_id=self.user_id
            )
            self.assertTrue(res["deleted"])
            self.assertEqual(self.connection.commits, 1)

            from app.services.portfolio import RevisionConflictError
            mock_delete.side_effect = RevisionConflictError("Conflito de versão.")
            with self.assertRaises(HTTPException) as raised:
                delete_price_target(
                    target_id, Response(), if_match="1", idempotency_key=uuid4(), user_id=self.user_id
                )
            self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
