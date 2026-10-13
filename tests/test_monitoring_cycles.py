import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

from app.services.monitoring import MonitoringCycleService
from app.services.provider_budget import BudgetDecision


class CycleCursor:
    def __init__(self, *, state=None, mappings=None):
        self.state = state
        self.mappings = mappings or []
        self.result = None
        self.rowcount = 0
        self.executed = []

    def execute(self, query, params=None):
        sql = " ".join(query.lower().split())
        self.executed.append(sql)
        self.rowcount = 0
        if "from portfolio_private.mutation_receipts" in sql:
            self.result = None
        elif "from portfolio_private.monitoring_state" in sql and "for update" in sql:
            self.result = self.state
        elif "from portfolio_private.monitoring_settings" in sql:
            self.result = None
        elif "from portfolio_private.asset_price_mappings" in sql:
            self.result = self.mappings
        elif "from portfolio_private.monitoring_cycles" in sql:
            self.result = None
        elif sql.startswith("update portfolio_private.monitoring_cycles"):
            self.rowcount = 1
            self.result = None
        elif sql.startswith("update portfolio_private.monitoring_state"):
            self.rowcount = 1
            self.result = None
        elif sql.startswith("insert into portfolio_private.monitoring_cycles"):
            self.result = None
        elif sql.startswith("insert into portfolio_private.monitoring_state"):
            self.result = None
        elif sql.startswith("insert into portfolio_private.mutation_receipts"):
            self.result = None
        elif sql.startswith("select pg_advisory_xact_lock"):
            self.result = None
        else:
            raise AssertionError(f"SQL não esperado: {sql}")

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result or []


class DeniedBudget:
    def reserve(self, *args, **kwargs):
        return BudgetDecision(False, "quota_exhausted", kwargs["now"] + timedelta(days=1))


class MonitoringCycleTests(unittest.TestCase):
    def test_missing_provider_configuration_blocks_before_any_insert(self):
        cur = CycleCursor()
        service = MonitoringCycleService()
        with patch("app.services.monitoring.get_app_settings", return_value=object()), \
             patch("app.services.monitoring.provider_configured", return_value=False):
            result = service.reserve_cycle(cur, uuid4(), uuid4(), now=datetime.now(timezone.utc))
        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason, "config_required")
        self.assertEqual(result.http_status, 503)
        self.assertFalse(any(sql.startswith("insert into") for sql in cur.executed))

    def test_quota_block_creates_no_cycle_or_state(self):
        cur = CycleCursor(mappings=[(uuid4(), "bitcoin", 1)])
        service = MonitoringCycleService(budget_service=DeniedBudget())
        now = datetime.now(timezone.utc)
        settings = SimpleNamespace(
            coingecko_demo_api_key=SimpleNamespace(get_secret_value=lambda: "test-key"),
            coingecko_window_start=now - timedelta(days=1),
            coingecko_window_end=now + timedelta(days=1),
            coingecko_call_limit=1,
        )
        fake_client = SimpleNamespace(plan_batches=lambda ids: ([["bitcoin"]], {}))
        with patch("app.services.monitoring.get_app_settings", return_value=settings), \
             patch("app.services.monitoring.provider_configured", return_value=True), \
             patch("app.services.monitoring.CoinGeckoClient") as client_cls:
            client_cls.return_value.__enter__.return_value = fake_client
            result = service.reserve_cycle(cur, uuid4(), uuid4(), now=now)
        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason, "quota_exhausted")
        self.assertEqual(result.http_status, 429)
        self.assertFalse(any(sql.startswith("insert into portfolio_private.monitoring_cycles") for sql in cur.executed))
        self.assertFalse(any(sql.startswith("insert into portfolio_private.monitoring_state") for sql in cur.executed))

    def test_expired_lease_is_failed_and_token_is_invalidated(self):
        now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        cycle_id = uuid4()
        cur = CycleCursor(state=(cycle_id, now - timedelta(seconds=1)))
        self.assertTrue(MonitoringCycleService.reconcile_expired_cycle(cur, uuid4(), now=now))
        cycle_updates = [sql for sql in cur.executed if sql.startswith("update portfolio_private.monitoring_cycles")]
        self.assertEqual(len(cycle_updates), 1)
        self.assertIn("error_code='interrupted'", cycle_updates[0])
        self.assertTrue(any(sql.startswith("update portfolio_private.monitoring_state") for sql in cur.executed))


if __name__ == "__main__":
    unittest.main()
