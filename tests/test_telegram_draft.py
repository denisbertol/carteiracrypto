"""Testes de persistência de rascunho e idempotência de atualizações do Telegram (T005)."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
import pytest

from app.services.telegram_draft import (
    save_draft,
    get_draft,
    clear_draft,
    record_applied_update,
    is_update_already_applied,
)


class FakeCursor:
    def __init__(self):
        self.drafts = {}
        self.updates = {}

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params

        if "INSERT INTO portfolio_private.telegram_updates" in sql:
            uid = int(params[0])
            self.updates[uid] = {"portfolio_id": params[1], "result_summary": params[2]}
        elif "SELECT" in sql and "telegram_updates" in sql:
            uid = int(params[0])
            item = self.updates.get(uid)
            self._row = (item["result_summary"],) if item else None
        elif "telegram_drafts" in sql and ("INSERT INTO" in sql or "ON CONFLICT" in sql):
            key = (str(params[0]), int(params[1]))
            self.drafts[key] = {
                "portfolio_id": params[0],
                "telegram_user_id": params[1],
                "kind": params[2],
                "symbol": params[3],
                "quantity": params[4],
                "unit_price_usd": params[5],
                "fee_usdt": params[6],
                "note": params[7],
                "missing_fields": params[8],
                "message_time": params[9],
            }
        elif "SELECT" in sql and "telegram_drafts" in sql:
            key = (str(params[0]), int(params[1]))
            item = self.drafts.get(key)
            if item:
                self._row = (
                    item["kind"],
                    item["symbol"],
                    item["quantity"],
                    item["unit_price_usd"],
                    item["fee_usdt"],
                    item["note"],
                    item["missing_fields"],
                    item["message_time"],
                )
            else:
                self._row = None
        elif "DELETE FROM portfolio_private.telegram_drafts" in sql:
            key = (str(params[0]), int(params[1]))
            self.drafts.pop(key, None)

    def fetchone(self):
        return getattr(self, "_row", None)


def test_draft_lifecycle():
    cur = FakeCursor()
    portfolio_id = uuid4()
    tg_user_id = 987654321
    msg_time = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Sem rascunho inicial
    assert get_draft(cur, portfolio_id, tg_user_id) is None

    # 2. Salva rascunho com campo faltante
    draft_data = {
        "kind": "buy",
        "symbol": "BTC",
        "quantity": Decimal("0.5"),
        "unit_price_usd": None,
        "fee_usdt": Decimal("0"),
        "note": None,
        "missing_fields": ["unit_price_usd"],
        "message_time": msg_time,
    }
    save_draft(cur, portfolio_id, tg_user_id, draft_data)

    retrieved = get_draft(cur, portfolio_id, tg_user_id)
    assert retrieved is not None
    assert retrieved["kind"] == "buy"
    assert retrieved["symbol"] == "BTC"
    assert retrieved["quantity"] == Decimal("0.5")
    assert retrieved["missing_fields"] == ["unit_price_usd"]
    assert retrieved["message_time"] == msg_time

    # 3. Limpa rascunho ao cancelar ou ao aceitar lançamento
    clear_draft(cur, portfolio_id, tg_user_id)
    assert get_draft(cur, portfolio_id, tg_user_id) is None


def test_update_idempotency_prevents_duplicate_processing():
    cur = FakeCursor()
    portfolio_id = uuid4()
    update_id = 123456789

    assert not is_update_already_applied(cur, update_id)

    record_applied_update(cur, update_id, portfolio_id, "lancamento_aceito")

    assert is_update_already_applied(cur, update_id)
