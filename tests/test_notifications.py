import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.notifications import NotificationService


class NotificationCursor:
    def __init__(self, *, notification=None, history_rows=None):
        self.notification = notification
        self.result = None
        self.rowcount = 0
        self.sql = ""
        self.params = None
        self.history_rows = history_rows or []

    def execute(self, query, params=None):
        self.sql = " ".join(query.lower().split())
        self.params = params or ()
        self.rowcount = 0
        if self.sql.startswith("insert into portfolio_private.price_notifications"):
            self.rowcount = 1
            self.result = None
        elif self.sql.startswith("update portfolio_private.price_notifications"):
            if self.notification is None:
                self.result = None
                return
            current = self.params[0]
            if "read_at=coalesce" in self.sql:
                self.notification[2] = self.notification[2] or current
                self.notification[3] = self.notification[3] or current
            else:
                self.notification[2] = self.notification[2] or current
            self.result = tuple(self.notification)
        elif self.sql.startswith("select n.id"):
            self.result = self.history_rows
        else:
            raise AssertionError(f"SQL não esperado: {self.sql}")

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result or []


class NotificationServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = NotificationService()
        self.portfolio_id, self.notification_id = uuid4(), uuid4()
        self.now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)

    def test_create_is_limited_to_active_matching_inside_evaluation_and_deduplicated(self):
        cur = NotificationCursor()
        self.assertTrue(self.service.create_for_evaluation(cur, self.portfolio_id, uuid4()))
        self.assertIn("e.result='inside'", cur.sql)
        self.assertIn("t.active=true and t.version=e.target_version", cur.sql)
        self.assertIn("on conflict (evaluation_id) do nothing", cur.sql)

    def test_displayed_ack_keeps_first_server_timestamp(self):
        created = self.now - timedelta(minutes=1)
        self._seed_notification(created)
        cur = NotificationCursor(notification=self.notification)
        first = self.service.acknowledge_displayed(
            cur, self.portfolio_id, self.notification_id, now=self.now
        )
        second_time = self.now + timedelta(minutes=2)
        second = self.service.acknowledge_displayed(
            cur, self.portfolio_id, self.notification_id, now=second_time
        )
        self.assertEqual(first["displayed_at"], second["displayed_at"])
        self.assertEqual(first["displayed_at"], self.now.isoformat())
        self.assertIsNone(second["read_at"])

    def test_read_ack_also_satisfies_displayed_constraint_and_is_idempotent(self):
        created = self.now - timedelta(minutes=1)
        self._seed_notification(created)
        cur = NotificationCursor(notification=self.notification)
        first = self.service.acknowledge_read(cur, self.portfolio_id, self.notification_id, now=self.now)
        second = self.service.acknowledge_read(
            cur, self.portfolio_id, self.notification_id, now=self.now + timedelta(minutes=1)
        )
        self.assertEqual(first["displayed_at"], self.now.isoformat())
        self.assertEqual(first["read_at"], self.now.isoformat())
        self.assertEqual(first, second)
        self.assertIn("displayed_at=coalesce(displayed_at,%s)", cur.sql)
        self.assertIn("read_at=coalesce(read_at,%s)", cur.sql)

    def test_history_has_strict_30_day_filter_and_cursor_pagination(self):
        first_id, second_id = uuid4(), uuid4()
        older = self.now - timedelta(hours=1)
        rows = [self._history_row(first_id, self.now), self._history_row(second_id, older)]
        cur = NotificationCursor(history_rows=rows)
        result = self.service.list_history(cur, self.portfolio_id, limit=1, now=self.now)
        self.assertEqual(len(result["items"]), 1)
        self.assertIsNotNone(result["next_cursor"])
        self.assertIn("n.created_at > %s", cur.sql)
        self.assertEqual(cur.params[-1], 2)
        self.assertEqual(cur.params[1], self.now - timedelta(days=30))

        cur.history_rows = [rows[1]]
        next_page = self.service.list_history(
            cur, self.portfolio_id, limit=1, cursor=result["next_cursor"], now=self.now
        )
        self.assertEqual(next_page["items"][0]["id"], str(second_id))
        self.assertIn("n.created_at < %s or (n.created_at = %s and n.id < %s)", cur.sql)

    def test_expired_ack_is_not_found(self):
        cur = NotificationCursor()
        with self.assertRaises(LookupError):
            self.service.acknowledge_displayed(
                cur, self.portfolio_id, self.notification_id, now=self.now
            )
        self.assertIn("created_at > %s", cur.sql)

    def test_cycle_delivery_query_filters_notifications_for_changed_targets(self):
        cur = NotificationCursor()
        self.service.list_history(
            cur, self.portfolio_id, cycle_id=uuid4(), current_targets_only=True, now=self.now
        )
        self.assertIn("e.result='inside'", cur.sql)
        self.assertIn("t.active=true", cur.sql)
        self.assertIn("t.version=e.target_version", cur.sql)

    def _seed_notification(self, created_at):
        self.notification = [self.notification_id, created_at, None, None]

    def _history_row(self, notification_id, created_at):
        return (
            notification_id, uuid4(), created_at, None, None,
            uuid4(), uuid4(), 1, "100", "buy", None, "10", "95",
            created_at, created_at, "5", "inside", None,
            uuid4(), "asset-1", "BTC", "Bitcoin",
        )


if __name__ == "__main__":
    unittest.main()
