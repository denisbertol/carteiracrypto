import json
import unittest
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app.routes.ai import get_ai_settings, preview_operations, put_ai_settings, AiSettingsInput
from app.services.ai_import import (
    AiImportError,
    GeminiClient,
    key_hint,
    normalize_operations,
    normalize_targets,
    parse_model_json,
    sniff_image,
    validate_model,
)


SECRET = "AIzaSyTESTKEYVALUE1234567890"


class Cursor:
    def __init__(self, ones=None, rows=None):
        self.ones = list(ones or [])
        self.rows = list(rows or [])
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.ones.pop(0) if self.ones else None

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        @contextmanager
        def context():
            yield self._cursor
        return context()

    def commit(self):
        self.commits += 1


class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.btc = uuid4()
        self.usdt = uuid4()
        self.assets = [
            {"id": self.btc, "symbol": "BTC", "name": "Bitcoin"},
            {"id": self.usdt, "symbol": "USDT", "name": "Tether"},
        ]

    def test_buy_uses_brazilian_decimal_and_sorts_deposit_first(self):
        payload = normalize_operations({
            "items": [
                {"kind": "compra", "symbol": "btc", "occurred_at": "2026-10-02T12:00:00Z", "quantity": "0,01", "unit_price_usd": "80.000,50", "fee_usdt": "1,25"},
                {"kind": "deposit", "symbol": "USDT", "occurred_at": "2026-10-02T12:00:00Z", "quantity": "1000"},
            ],
        }, self.assets)
        self.assertEqual([item["kind"] for item in payload["items"]], ["deposit", "buy"])
        buy = payload["items"][1]
        self.assertTrue(buy["ready"])
        self.assertEqual(buy["asset_id"], str(self.btc))
        self.assertEqual(buy["quantity"], "0.01")
        self.assertEqual(Decimal(buy["unit_price_usd"]), Decimal("80000.50"))
        self.assertEqual(buy["fee_usdt"], "1.25")

    def test_unknown_asset_and_trade_without_price_stay_out(self):
        payload = normalize_operations({
            "items": [
                {"kind": "buy", "symbol": "DOGE", "occurred_at": "2026-10-02T12:00:00Z", "quantity": "1", "unit_price_usd": "1"},
                {"kind": "sell", "symbol": "BTC", "occurred_at": "2026-10-02T12:00:00Z", "quantity": "1"},
                {"kind": "deposit", "symbol": "BTC", "occurred_at": "2026-10-02T12:00:00Z", "quantity": "1"},
            ],
            "skipped": [{"description": "bônus GT", "reason": "não é lançamento"}],
        }, self.assets)
        self.assertTrue(all(not item["ready"] for item in payload["items"]))
        self.assertEqual(payload["skipped"][0]["description"], "bônus GT")

    def test_target_updates_existing_buy_and_ignores_same_price(self):
        target_id = uuid4()
        targets = [{
            "id": target_id, "asset_id": self.btc, "kind": "buy",
            "price_usd": Decimal("78000"), "active": True, "orientation": None, "version": 4,
        }]
        payload = normalize_targets({
            "items": [
                {"symbol": "BTC", "price_usd": "79000"},
                {"symbol": "ETH", "price_usd": "2000"},
                {"symbol": "BTC", "price_usd": "80000"},
                {"symbol": "USDT", "price_usd": "1"},
            ],
        }, self.assets, targets)
        ready = {item["symbol"]: item for item in payload["items"] if item["ready"]}
        self.assertEqual(ready["BTC"]["action"], "update")
        self.assertEqual(ready["BTC"]["target_id"], str(target_id))
        self.assertEqual(ready["BTC"]["version"], 4)
        self.assertEqual(ready["BTC"]["price_usd"], "80000")
        self.assertIn("último", ready["BTC"]["reason"])
        blocked = {item["symbol"]: item["reason"] for item in payload["items"] if not item["ready"]}
        self.assertIn("não cadastrado", blocked["ETH"])
        self.assertIn("caixa", blocked["USDT"])

        same = normalize_targets({"items": [{"symbol": "BTC", "price_usd": "78000"}]}, self.assets, targets)
        self.assertFalse(same["items"][0]["ready"])

    def test_fenced_json_and_model_name(self):
        parsed = parse_model_json("```json\n{\"items\": []}\n```")
        self.assertEqual(parsed["items"], [])
        self.assertEqual(validate_model(" gemini-2.5-flash "), "gemini-2.5-flash")
        with self.assertRaises(AiImportError):
            validate_model("../secret")
        self.assertEqual(key_hint(SECRET), "7890")
        self.assertEqual(sniff_image(b"\x89PNG\r\n\x1a\nrest"), "image/png")

    def test_gemini_failure_does_not_reveal_the_api_key(self):
        def poster(url, headers, json):
            raise RuntimeError(headers["x-goog-api-key"])

        client = GeminiClient(SECRET, "gemini-2.5-flash", poster=poster)
        with self.assertRaises(AiImportError) as raised:
            client.generate("instrução", "material", None, {"type": "OBJECT"})
        self.assertNotIn(SECRET, str(raised.exception))


class AiRouteTests(unittest.TestCase):
    def setUp(self):
        self.user_id = uuid4()
        self.portfolio_id = uuid4()
        self.usdt_id = uuid4()
        self.btc_id = uuid4()

    def connection(self, ones, rows=None):
        cursor = Cursor(ones, rows)
        return Connection(cursor), cursor

    def test_settings_response_never_returns_the_api_key(self):
        connection, cursor = self.connection([
            (self.portfolio_id, 3),
            (self.usdt_id,),
            (SECRET, "gemini-2.5-flash"),
            (self.portfolio_id, 3),
            (self.usdt_id,),
            (SECRET, "gemini-2.5-pro"),
        ])
        with patch("app.routes.ai.get_db_connection", return_value=connection):
            current = get_ai_settings(self.user_id)
            saved = put_ai_settings(AiSettingsInput(api_key=SECRET, model="gemini-2.5-pro"), self.user_id)
        self.assertEqual(current, {"configured": True, "model": "gemini-2.5-flash", "key_hint": "7890"})
        self.assertEqual(saved["key_hint"], "7890")
        self.assertNotIn(SECRET, json.dumps(saved))
        update = next(params for query, params in cursor.queries if query.startswith("UPDATE"))
        self.assertEqual(update[0], SECRET)
        self.assertEqual(connection.commits, 1)

    def test_preview_requires_a_saved_key_and_does_not_call_gemini(self):
        connection, _cursor = self.connection([
            (self.portfolio_id, 3),
            (self.usdt_id,),
            (None, "gemini-2.5-flash"),
        ])
        with patch("app.routes.ai.get_db_connection", return_value=connection), \
             patch("app.routes.ai.GeminiClient") as client:
            with self.assertRaises(HTTPException) as raised:
                preview_operations(text="comprei btc", upload=None, user_id=self.user_id)
        self.assertEqual(raised.exception.detail["error"]["code"], "AI_NOT_CONFIGURED")
        client.assert_not_called()
        self.assertEqual(connection.commits, 0)

    def test_preview_returns_a_proposal_without_the_api_key(self):
        connection, _cursor = self.connection(
            [(self.portfolio_id, 3), (self.usdt_id,), (SECRET, "gemini-2.5-flash")],
            [(self.btc_id, "BTC", "Bitcoin"), (self.usdt_id, "USDT", "Tether")],
        )

        class FakeGemini:
            def __init__(self, api_key, model):
                self.api_key = api_key

            def generate(self, instruction, material, image, schema):
                self.instruction = instruction
                return {"items": [{
                    "kind": "buy", "symbol": "BTC", "occurred_at": "2026-10-02T12:00:00Z",
                    "quantity": "0.1", "unit_price_usd": "80000", "fee_usdt": "0",
                }]}

        with patch("app.routes.ai.get_db_connection", return_value=connection), \
             patch("app.routes.ai.GeminiClient", FakeGemini):
            body = preview_operations(text="compra de btc", upload=None, user_id=self.user_id)
        self.assertTrue(body["items"][0]["ready"])
        self.assertEqual(body["items"][0]["asset_id"], str(self.btc_id))
        self.assertNotIn(SECRET, json.dumps(body))
        self.assertEqual(connection.commits, 0)
