import unittest
from datetime import datetime, timedelta, timezone

from app.services.provider_budget import ProviderBudgetService


class BudgetCursor:
    def __init__(self):
        self.row = None
        self.result = None

    def execute(self, query, params=None):
        sql = " ".join(query.lower().split())
        params = params or ()
        if sql.startswith("insert into portfolio_private.provider_budget"):
            if self.row is None:
                self.row = (params[2], params[3], 0, params[4], None)
        elif sql.startswith("select window_start, window_end, attempts"):
            self.result = self.row
        elif "attempts=0" in sql:
            self.row = (params[0], params[1], 0, params[2], None)
        elif "set attempts=%s" in sql:
            self.row = (self.row[0], self.row[1], params[0], params[1], None)
        elif "set cooldown_until = greatest" in sql:
            until = max(filter(None, (self.row[4], params[1])))
            self.row = (*self.row[:4], until)
        else:
            raise AssertionError(f"SQL não esperado: {sql}")

    def fetchone(self):
        return self.result


class ProviderBudgetTests(unittest.TestCase):
    def setUp(self):
        self.service = ProviderBudgetService()
        self.cursor = BudgetCursor()
        self.now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        self.window_start = self.now - timedelta(days=1)
        self.window_end = self.now + timedelta(days=29)

    def reserve(self, **overrides):
        args = {
            "provider": "coingecko",
            "api_key": "unit-test-key-never-stored",
            "window_start": self.window_start,
            "window_end": self.window_end,
            "configured_limit": 2,
            "request_count": 1,
            "now": self.now,
        }
        args.update(overrides)
        return self.service.reserve(self.cursor, **args)

    def test_missing_window_fails_closed_and_key_is_hashed(self):
        denied = self.reserve(window_start=None)
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reason, "config_required")
        self.assertIsNone(self.cursor.row)

        allowed = self.reserve()
        self.assertTrue(allowed.allowed)
        self.assertEqual(self.cursor.row[2], 1)
        self.assertEqual(len(self.cursor.row), 5)
        self.assertNotIn("unit-test-key-never-stored", repr(self.cursor.row))

    def test_quota_is_reserved_before_calls_and_not_refunded(self):
        self.assertTrue(self.reserve().allowed)
        exhausted = self.reserve(request_count=2)
        self.assertFalse(exhausted.allowed)
        self.assertEqual(exhausted.reason, "quota_exhausted")
        self.assertEqual(self.cursor.row[2], 1)
        self.assertTrue(self.reserve().allowed)
        self.assertEqual(self.cursor.row[2], 2)

    def test_active_window_cannot_be_changed_to_reset_quota(self):
        self.assertTrue(self.reserve().allowed)
        changed = self.reserve(window_start=self.window_start - timedelta(days=1))
        self.assertFalse(changed.allowed)
        self.assertEqual(changed.reason, "provider_window_changed")
        self.assertEqual(self.cursor.row[2], 1)

    def test_cooldown_blocks_reservation_until_its_deadline(self):
        self.assertTrue(self.reserve().allowed)
        deadline = self.now + timedelta(minutes=5)
        self.service.set_cooldown(
            self.cursor,
            provider="coingecko",
            api_key="unit-test-key-never-stored",
            cooldown_until=deadline,
            now=self.now,
        )
        denied = self.reserve()
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reason, "provider_cooldown")
        self.assertEqual(denied.next_retry_at, deadline)


if __name__ == "__main__":
    unittest.main()
