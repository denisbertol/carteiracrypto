import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services.coingecko import PriceBatch, ProviderQuote
from app.services.monitoring import MonitoringCycleService
from app.services.provider_budget import ProviderBudgetService


class ExecutionCursor:
    def __init__(self, *, now, portfolio_id, cycle_id, lease_token, asset_id, target_id, fingerprint, target_changed=False, mapping_changed=False):
        self.now = now
        self.portfolio_id = portfolio_id
        self.cycle_id = cycle_id
        self.lease_token = lease_token
        self.asset_id = asset_id
        self.target_id = target_id
        self.fingerprint = fingerprint
        self.target_changed = target_changed
        self.mapping_changed = mapping_changed
        self.result = None
        self.rowcount = 0
        self.evaluations = []
        self.notifications = []
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        sql = " ".join(query.lower().split())
        self.statements.append((sql, params))
        self.rowcount = 0
        if "from portfolio_private.monitoring_cycles c" in sql and "join portfolio_private.monitoring_state" in sql:
            if "c.status, c.lease_token, c.settings_revision" in sql:
                self.result = (
                    "reserved", self.lease_token, 1, 1, self.fingerprint,
                    self.now - timedelta(days=1), self.now + timedelta(days=29), 100,
                    self.cycle_id, self.now + timedelta(seconds=50),
                )
            else:
                self.result = ("running", self.lease_token, self.cycle_id, self.now + timedelta(seconds=40))
        elif "select proximity_percent, revision from portfolio_private.monitoring_settings" in sql:
            self.result = (Decimal("10.00"), 1)
        elif "select current_cycle_id, lease_until from portfolio_private.monitoring_state" in sql:
            self.result = (self.cycle_id, self.now + timedelta(seconds=40))
        elif "select a.id, a.external_id, a.symbol, a.active, m.provider" in sql:
            self.result = [
                (self.asset_id, "bitcoin", "BTC", True, "coingecko", "bitcoin", "valid", 1)
            ]
        elif "select a.id, a.symbol, a.active, m.provider" in sql:
            mapping_version = 2 if self.mapping_changed else 1
            self.result = [
                (self.asset_id, "BTC", True, "coingecko", "bitcoin", "valid", mapping_version)
            ]
        elif "select id, asset_id, kind, price_usd, active, orientation, version" in sql:
            version = 1 if "and active=true" in sql else (2 if self.target_changed else 1)
            self.result = [
                (self.target_id, self.asset_id, "buy", Decimal("100"), True, None, version)
            ]
        elif sql.startswith("update portfolio_private.monitoring_cycles set status='running'"):
            self.rowcount = 1
            self.result = None
        elif sql.startswith("insert into portfolio_private.latest_quotes"):
            self.rowcount = 1
            self.result = None
        elif sql.startswith("insert into portfolio_private.asset_daily_prices"):
            self.rowcount = 1
            self.result = None
        elif sql.startswith("insert into portfolio_private.price_evaluations"):
            self.evaluations.append(params)
            self.rowcount = 1
            self.result = None
        elif "from portfolio_private.price_notifications n" in sql and "read_at is null" in sql:
            self.result = None
        elif sql.startswith("update portfolio_private.price_notifications"):
            self.rowcount = 0
            self.result = None
        elif sql.startswith("insert into portfolio_private.price_notifications"):
            self.notifications.append(params)
            self.rowcount = 1
            self.result = None
        elif sql.startswith("select pg_advisory_xact_lock"):
            self.result = None
        elif sql.startswith("update portfolio_private.monitoring_cycles set status=%s"):
            self.rowcount = 1
            self.result = None
        elif sql.startswith("update portfolio_private.monitoring_cycles set status='failed'"):
            self.rowcount = 1
            self.result = None
        elif sql.startswith("update portfolio_private.monitoring_state"):
            self.rowcount = 1
            self.result = None
        else:
            raise AssertionError(f"SQL não esperado: {sql}")

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result or []


class ExecutionConnection:
    def __init__(self, cursor, tracker, fail_commit=False):
        self._cursor = cursor
        self.tracker = tracker
        self.fail_commit = fail_commit
        self.tracker["active"] = True
        self.tracker["commits"] += 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.tracker["active"] = False
        if exc_type is not None:
            self.tracker["rollbacks"] += 1
        return False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.tracker["commits"] += 1
        if self.fail_commit:
            raise RuntimeError("simulated commit failure")


class MonitoringExecutionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        self.portfolio_id, self.cycle_id, self.lease_token = uuid4(), uuid4(), uuid4()
        self.asset_id, self.target_id = uuid4(), uuid4()
        self.settings = SimpleNamespace(
            coingecko_demo_api_key=SimpleNamespace(get_secret_value=lambda: "secret-test-key"),
            coingecko_window_start=self.now - timedelta(days=1),
            coingecko_window_end=self.now + timedelta(days=29),
            coingecko_call_limit=100,
        )
        self.fingerprint = ProviderBudgetService.key_fingerprint("secret-test-key")

    def run_cycle(self, *, target_changed=False, mapping_changed=False, fail_finish_commit=False, expire_before_finish=False):
        cur = ExecutionCursor(
            now=self.now, portfolio_id=self.portfolio_id, cycle_id=self.cycle_id,
            lease_token=self.lease_token, asset_id=self.asset_id, target_id=self.target_id,
            fingerprint=self.fingerprint, target_changed=target_changed,
            mapping_changed=mapping_changed,
        )
        tracker = {"active": False, "commits": 0, "rollbacks": 0}
        connections = 0

        def connection_factory(user_id):
            nonlocal connections
            connections += 1
            return ExecutionConnection(cur, tracker, fail_commit=fail_finish_commit and connections == 2)

        class FakeProvider:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def plan_batches(self, ids):
                return ([["bitcoin"]], {})

            def fetch_prices(self, ids):
                if tracker["active"]:
                    raise AssertionError("HTTP ocorreu enquanto conexão SQL estava aberta")
                return PriceBatch(quotes={
                    "bitcoin": ProviderQuote("bitcoin", Decimal("95"), self.now, self.now)
                }, request_count=1)

        FakeProvider.now = self.now
        times = iter([self.now, self.now + timedelta(seconds=61)])
        clock = (lambda: next(times)) if expire_before_finish else (lambda: self.now)
        with patch("app.services.monitoring.get_app_settings", return_value=self.settings), \
             patch("app.services.monitoring.provider_configured", return_value=True):
            result = MonitoringCycleService().run_reserved_cycle(
                uuid4(), self.portfolio_id, self.cycle_id, self.lease_token,
                connection_factory=connection_factory,
                client_factory=lambda key: FakeProvider(),
                clock=clock,
            )
        return result, cur, tracker

    def test_deactivated_or_changed_target_is_superseded_after_fetch(self):
        result, cursor, tracker = self.run_cycle(target_changed=True)
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(cursor.evaluations), 1)
        self.assertEqual(cursor.evaluations[0][-2], "superseded")
        self.assertFalse(tracker["active"])
        self.assertEqual(tracker["commits"], 2)

    def test_failed_final_commit_leaves_cycle_unverified_for_lease_reconciliation(self):
        result, cursor, tracker = self.run_cycle(fail_finish_commit=True)
        self.assertEqual(result.status, "running")
        self.assertEqual(result.error_code, "commit_failed")
        self.assertEqual(len(cursor.evaluations), 1)
        self.assertEqual(len(cursor.notifications), 1)
        self.assertEqual(tracker["rollbacks"], 1)

    def test_each_inside_evaluation_creates_one_notification_in_same_transaction(self):
        result, cursor, tracker = self.run_cycle()
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(cursor.evaluations), 1)
        self.assertEqual(cursor.evaluations[0][-2], "inside")
        self.assertEqual(len(cursor.notifications), 1)
        self.assertEqual(cursor.notifications[0][1], cursor.evaluations[0][0])
        self.assertFalse(tracker["active"])

    def test_published_quote_is_recorded_as_daily_price(self):
        _, cursor, _ = self.run_cycle()
        daily = [params for sql, params in cursor.statements
                 if sql.startswith("insert into portfolio_private.asset_daily_prices")]
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0][3], "95")
        self.assertIn("'live'", next(sql for sql, _ in cursor.statements if "asset_daily_prices" in sql))

    def test_changed_mapping_discards_quote_and_suppresses_evaluation(self):
        result, cursor, _ = self.run_cycle(mapping_changed=True)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.quotes_updated, 0)
        self.assertEqual(cursor.evaluations[0][-2], "superseded")
        self.assertEqual(cursor.notifications, [])
        self.assertFalse(any(sql.startswith("insert into portfolio_private.latest_quotes") for sql, _ in cursor.statements))

    def test_late_finalization_after_expiry_creates_no_quote_or_alert(self):
        result, cursor, tracker = self.run_cycle(expire_before_finish=True)
        self.assertEqual(result.status, "interrupted")
        self.assertEqual(result.error_code, "lease_expired")
        self.assertEqual(cursor.evaluations, [])
        self.assertEqual(cursor.notifications, [])
        self.assertFalse(any(sql.startswith("insert into portfolio_private.latest_quotes") for sql, _ in cursor.statements))
        self.assertFalse(tracker["active"])


if __name__ == "__main__":
    unittest.main()
