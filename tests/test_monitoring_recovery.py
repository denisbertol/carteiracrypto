import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.monitoring_recovery import reconcile_expired_cycles


class RecoveryCursor:
    def __init__(self, now, *, lock_available=True, states=None):
        self.now = now
        self.lock_available = lock_available
        self.states = states or {}
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
        elif sql.startswith("select portfolio_id from portfolio_private.monitoring_state"):
            self.result = [
                (str(portfolio_id),) for portfolio_id, state in self.states.values()
                if state[0] is not None and state[1] <= params[0]
            ]
        elif sql.startswith("select pg_advisory_xact_lock"):
            self.result = None
        elif sql.startswith("select current_cycle_id, lease_until"):
            self.result = self.states[params[0]][1]
        elif sql.startswith("update portfolio_private.monitoring_cycles set status='failed'"):
            self.rowcount = 1
            self.result = None
        elif sql.startswith("update portfolio_private.monitoring_state"):
            self.rowcount = 1
            record = self.states[params[0]]
            self.states[params[0]] = (record[0], (None, None))
            self.result = None
        else:
            raise AssertionError(f"SQL não esperado: {sql}")

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result or []


class RecoveryConnection:
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


class MonitoringRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)

    def test_reconciles_expired_leases_without_any_provider_or_result_write(self):
        first_portfolio, second_portfolio = uuid4(), uuid4()
        first_cycle, second_cycle = uuid4(), uuid4()
        states = {
            str(first_portfolio): (first_portfolio, (str(first_cycle), self.now - timedelta(seconds=1))),
            str(second_portfolio): (second_portfolio, (str(second_cycle), self.now - timedelta(minutes=2))),
        }
        cursor = RecoveryCursor(self.now, states=states)
        connection = RecoveryConnection(cursor)
        result = reconcile_expired_cycles(
            uuid4(), now=self.now, connection_factory=lambda _: connection
        )
        self.assertEqual(result, {"state": "completed", "reconciled": 2})
        cycle_updates = [sql for sql, _ in cursor.statements if sql.startswith("update portfolio_private.monitoring_cycles")]
        self.assertEqual(len(cycle_updates), 2)
        self.assertTrue(all("error_code='interrupted'" in sql for sql in cycle_updates))
        self.assertFalse(any("price_evaluations" in sql or "price_notifications" in sql for sql, _ in cursor.statements))
        self.assertFalse(any("http" in sql or "coingecko" in sql for sql, _ in cursor.statements))
        self.assertEqual(connection.commits, 1)

    def test_singleton_lock_skips_overlapping_scheduler_run(self):
        cursor = RecoveryCursor(self.now, lock_available=False)
        connection = RecoveryConnection(cursor)
        result = reconcile_expired_cycles(
            uuid4(), now=self.now, connection_factory=lambda _: connection
        )
        self.assertEqual(result["state"], "skipped")
        self.assertFalse(any("current_cycle_id is not null" in sql for sql, _ in cursor.statements))
        self.assertEqual(connection.commits, 1)

    def test_recovery_is_idempotent_when_service_restarts_after_marking_cycle(self):
        portfolio_id, cycle_id = uuid4(), uuid4()
        cursor = RecoveryCursor(
            self.now,
            states={str(portfolio_id): (portfolio_id, (str(cycle_id), self.now - timedelta(seconds=1)))},
        )
        first = reconcile_expired_cycles(
            uuid4(), now=self.now, connection_factory=lambda _: RecoveryConnection(cursor)
        )
        second = reconcile_expired_cycles(
            uuid4(), now=self.now, connection_factory=lambda _: RecoveryConnection(cursor)
        )
        self.assertEqual(first["reconciled"], 1)
        self.assertEqual(second["reconciled"], 0)


if __name__ == "__main__":
    unittest.main()
