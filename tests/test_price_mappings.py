import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

from app.services.price_mappings import (
    CATALOG_TTL,
    PriceMappingService,
    ProviderCatalogService,
    ensure_provider_catalog,
)
from app.services.provider_budget import BudgetDecision


class CatalogCursor:
    def __init__(self):
        self.exists = False
        self.payload = []
        self.fetched_at = None
        self.expires_at = None
        self.version = 0
        self.token = None
        self.lease_until = None
        self.last_error = None
        self.result = None
        self.rowcount = 0
        self.mapping = None
        self.asset = ("bitcoin", "BTC", True)
        self.receipt = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        sql = " ".join(query.lower().split())
        params = params or ()
        self.rowcount = 0
        if sql.startswith("select pg_advisory_xact_lock"):
            self.result = None
        elif "select payload, fetched_at, expires_at, version" in sql:
            self.result = (self.payload, self.fetched_at, self.expires_at, self.version) if self.exists else None
        elif sql.startswith("insert into portfolio_private.provider_catalog"):
            self.exists = True
            self.result = None
        elif "select payload, expires_at, refresh_token, refresh_lease_until" in sql:
            self.result = (self.payload, self.expires_at, self.token, self.lease_until)
        elif "set refresh_token=%s, refresh_lease_until=%s" in sql:
            self.token, self.lease_until = params[0], params[1]
            self.result = None
        elif "set refresh_token=null" in sql:
            if self.token == params[3]:
                self.token, self.lease_until, self.last_error = None, None, params[0]
                self.rowcount = 1
        elif "set payload=%s, fetched_at=%s" in sql:
            if self.token == params[5] and self.lease_until > params[6]:
                self.payload = json.loads(params[0])
                self.fetched_at, self.expires_at = params[1], params[2]
                self.version += 1
                self.token, self.lease_until, self.last_error = None, None, None
                self.rowcount = 1
        elif "from portfolio_private.mutation_receipts" in sql:
            self.result = self.receipt
        elif "select external_id, symbol, active" in sql:
            self.result = self.asset
        elif "select provider_coin_id, status, version" in sql:
            self.result = self.mapping
        elif sql.startswith("insert into portfolio_private.asset_price_mappings"):
            self.mapping = (params[3], params[4], params[5], None)
            self.result = None
        elif sql.startswith("insert into portfolio_private.monitoring_changes"):
            self.result = None
        elif sql.startswith("insert into portfolio_private.mutation_receipts"):
            self.receipt = (params[2], params[3], json.loads(params[4]))
            self.result = None
        else:
            raise AssertionError(f"SQL não esperado: {sql}")

    def fetchone(self):
        return self.result


class MappingListCursor:
    def execute(self, query, params=None):
        self.result = [
            (uuid4(), "bitcoin", "BTC", "Bitcoin", "coingecko", "bitcoin", "valid", 2, None),
            (uuid4(), "ethereum", "ETH", "Ethereum", "coingecko", "ethereum", "pending", 1, None),
            (uuid4(), "dogecoin", "DOGE", "Dogecoin", "coingecko", "dogecoin", "unsupported", 1, None),
        ]

    def fetchall(self):
        return self.result


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1


class ProviderCatalogTests(unittest.TestCase):
    def setUp(self):
        self.service = ProviderCatalogService()
        self.cursor = CatalogCursor()
        self.now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)

    def test_concurrent_refresh_claim_is_unique_and_cache_expires_after_24_hours(self):
        first = self.service.claim_refresh(self.cursor, now=self.now)
        second = self.service.claim_refresh(self.cursor, now=self.now + timedelta(seconds=1))
        self.assertEqual(first.state, "claimed")
        self.assertEqual(second.state, "in_flight")

        coins = [{"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"}]
        self.assertTrue(self.service.complete_refresh(self.cursor, first.token, coins, now=self.now))
        cached = self.service.get_cached(self.cursor, now=self.now + CATALOG_TTL - timedelta(seconds=1))
        self.assertEqual(cached["coins"], coins)
        self.assertIsNone(self.service.get_cached(self.cursor, now=self.now + CATALOG_TTL))
        expired_claim = self.service.claim_refresh(self.cursor, now=self.now + CATALOG_TTL)
        self.assertEqual(expired_claim.state, "claimed")

    def test_mapping_stays_pending_without_catalog_and_preserves_asset_external_id(self):
        asset_id, portfolio_id, user_id = uuid4(), uuid4(), uuid4()
        mapping, replayed = PriceMappingService().put_mapping(
            self.cursor,
            portfolio_id,
            user_id,
            asset_id,
            "bitcoin",
            expected_version=0,
            idempotency_key=uuid4(),
            catalog_ids=None,
        )
        self.assertFalse(replayed)
        self.assertEqual(mapping["status"], "pending")
        self.assertEqual(mapping["external_id"], "bitcoin")
        self.assertEqual(self.cursor.mapping[:3], ("bitcoin", "pending", 1))

    def test_mapping_list_reports_provider_coverage_by_state(self):
        result = PriceMappingService().list_mappings(MappingListCursor(), uuid4())
        self.assertEqual(len(result["items"]), 3)
        self.assertEqual(result["coverage"]["valid_assets"], 1)
        self.assertEqual(result["coverage"]["pending_assets"], 1)
        self.assertEqual(result["coverage"]["unsupported_assets"], 1)
        self.assertEqual(result["coverage"]["coverage_percent"], 100 / 3)

    def test_catalog_quota_denial_returns_pending_without_http_or_losing_lease_state(self):
        cursor = CatalogCursor()
        fake_connection = FakeConnection(cursor)
        settings = SimpleNamespace(
            coingecko_demo_api_key=SimpleNamespace(get_secret_value=lambda: "test-api-key"),
            coingecko_window_start=self.now - timedelta(days=1),
            coingecko_window_end=self.now + timedelta(days=29),
            coingecko_call_limit=10,
        )
        denied = BudgetDecision(False, "quota_exhausted", self.now + timedelta(days=29))
        with patch("app.services.price_mappings.get_settings", return_value=settings), \
             patch("app.services.price_mappings.provider_configured", return_value=True), \
             patch("app.services.price_mappings.ProviderBudgetService") as budget_cls, \
             patch("app.services.price_mappings.CoinGeckoClient") as client_cls:
            budget_cls.return_value.reserve.return_value = denied
            result = ensure_provider_catalog(
                uuid4(),
                now=self.now,
                connection_factory=lambda _: fake_connection,
            )
        self.assertEqual(result["state"], "pending")
        self.assertEqual(result["reason"], "quota_exhausted")
        self.assertIsNone(cursor.token)
        client_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
