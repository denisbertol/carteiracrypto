import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.retention import (
    MAX_DELETE_BATCH,
    RETENTION_DELETE_ORDER,
    cleanup_retained_history,
    is_expired,
)


class RetentionCursor:
    def __init__(self, *, lock_available=True, counts=None):
        self.lock_available = lock_available
        self.counts = counts or {}
        self.result = None
        self.rowcount = 0
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        sql = " ".join(query.lower().split())
        params = params or ()
        self.statements.append((sql, params))
        self.rowcount = 0
        if sql.startswith("select pg_try_advisory_xact_lock"):
            self.result = (self.lock_available,)
        elif sql.startswith("with doomed as"):
            if "delete from portfolio_private.price_notifications" in sql:
                table = "price_notifications"
            elif "delete from portfolio_private.price_evaluations" in sql:
                table = "price_evaluations"
            elif "delete from portfolio_private.monitoring_cycles" in sql:
                table = "monitoring_cycles"
            elif "delete from portfolio_private.monitoring_changes" in sql:
                table = "monitoring_changes"
            else:
                raise AssertionError(f"DELETE sem tabela esperada: {sql}")
            sequence = self.counts.get(table, [0])
            self.rowcount = sequence.pop(0) if sequence else 0
            self.result = None
        elif sql.startswith("update portfolio_private.monitoring_state"):
            self.result = None
        else:
            raise AssertionError(f"SQL não esperado: {sql}")

    def fetchone(self):
        return self.result


class RetentionConnection:
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


class MonitoringRetentionTests(unittest.TestCase):
    def test_clock_controlled_retention_boundary_is_thirty_days(self):
        now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        self.assertFalse(is_expired(now - timedelta(days=29), now))
        self.assertTrue(is_expired(now - timedelta(days=30), now))
        self.assertTrue(is_expired(now - timedelta(days=31), now))

    def test_cleanup_order_preserves_current_quotes_and_registrations(self):
        tables = set(RETENTION_DELETE_ORDER)
        self.assertIn("price_notifications", tables)
        self.assertIn("price_evaluations", tables)
        self.assertNotIn("latest_quotes", tables)
        self.assertNotIn("price_targets", tables)
        self.assertNotIn("asset_price_mappings", tables)
        self.assertNotIn("monitoring_settings", tables)
        self.assertNotIn("operations", tables)

    def test_cleanup_deletes_in_bounded_batches_and_respects_live_references(self):
        user_id = uuid4()
        cursor = RetentionCursor(counts={
            "price_notifications": [2, 1],
            "price_evaluations": [0],
            "monitoring_cycles": [0],
            "monitoring_changes": [1],
        })
        connection = RetentionConnection(cursor)
        now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        result = cleanup_retained_history(
            user_id,
            now=now,
            batch_size=2,
            connection_factory=lambda _: connection,
        )

        self.assertEqual(result["state"], "completed")
        self.assertEqual(result["deleted"]["price_notifications"], 3)
        self.assertEqual(result["deleted"]["monitoring_changes"], 1)
        delete_statements = [sql for sql, _ in cursor.statements if sql.startswith("with doomed as")]
        self.assertTrue(all(params[-1] == 2 for sql, params in cursor.statements if sql.startswith("with doomed as")))
        self.assertTrue(any("n.created_at > %s" in sql for sql in delete_statements))
        cycle_delete = next(sql for sql in delete_statements if "delete from portfolio_private.monitoring_cycles" in sql)
        self.assertIn("latest_quotes q", cycle_delete)
        self.assertIn("current_cycle_id=c.id", cycle_delete)
        self.assertEqual(connection.commits, 1)

    def test_cleanup_lock_skips_concurrent_run_without_deleting_rows(self):
        cursor = RetentionCursor(lock_available=False)
        connection = RetentionConnection(cursor)
        result = cleanup_retained_history(
            uuid4(), connection_factory=lambda _: connection
        )
        self.assertEqual(result["state"], "skipped")
        self.assertEqual(result["reason"], "cleanup_in_progress")
        self.assertFalse(any(sql.startswith("with doomed as") for sql, _ in cursor.statements))
        self.assertEqual(connection.commits, 1)

    def test_cleanup_batch_size_cannot_exceed_one_thousand(self):
        with self.assertRaises(ValueError):
            cleanup_retained_history(uuid4(), batch_size=MAX_DELETE_BATCH + 1)


if __name__ == "__main__":
    unittest.main()
