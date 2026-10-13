import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.routes.exports import get_allocations_csv, get_results_csv


class ExportCursor:
    def __init__(self, portfolio_id, revision):
        self.portfolio_id = portfolio_id
        self.revision = revision
        self.result = None
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        self.statements.append((" ".join(query.lower().split()), params))
        if "select id, revision from portfolio_private.portfolios" in self.statements[-1][0]:
            self.result = (self.portfolio_id, self.revision)

    def fetchone(self):
        return self.result


class ExportConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return self._cursor


class ExportRouteTests(unittest.TestCase):
    def setUp(self):
        self.user_id, self.portfolio_id = uuid4(), uuid4()
        self.cursor = ExportCursor(self.portfolio_id, 8)
        self.connection = ExportConnection(self.cursor)
        self.snapshot_at = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        self.summary = {
            "revision": 8,
            "positions": [],
            "totals": {
                "complete": True, "updated": False, "freshness": "stale",
                "quote_snapshot_at": self.snapshot_at, "balance_usd": Decimal("50"),
            },
            "quote_snapshot_at": self.snapshot_at,
            "quote_freshness": "stale",
        }

    def factory(self, captured):
        @contextmanager
        def connection_factory(user_id, **options):
            captured["user_id"] = user_id
            captured["options"] = options
            yield self.connection
        return connection_factory

    def test_results_csv_uses_repeatable_read_and_exports_snapshot_freshness(self):
        captured = {}
        portfolio_stub = SimpleNamespace(
            get_portfolio_summary=lambda cur, portfolio_id: self.summary
        )
        with patch("app.routes.exports.get_db_connection", self.factory(captured)), \
             patch("app.routes.exports.portfolio_service", portfolio_stub):
            response = get_results_csv(user_id=self.user_id)
        self.assertEqual(captured["options"], {"isolation_level": "REPEATABLE READ", "read_only": True})
        self.assertEqual(captured["user_id"], self.user_id)
        self.assertIn("quote_snapshot_at", response.body.decode())
        self.assertIn("stale", response.body.decode())
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_allocation_csv_uses_same_summary_snapshot_once(self):
        captured = {}
        calls = {"summary": 0}

        def get_summary(cur, portfolio_id):
            calls["summary"] += 1
            return self.summary

        expected_summary = self.summary
        expected_snapshot_at = self.snapshot_at
        class AllocationStub:
            def get_allocation_comparison(self, cur, portfolio_id, *, portfolio_summary):
                self_summary_is_same = portfolio_summary is expected_summary
                calls["same_summary"] = self_summary_is_same
                return {
                    "version": 2, "items": [], "complete": True, "updated": False,
                    "freshness": "stale", "quote_snapshot_at": expected_snapshot_at,
                }

        portfolio_stub = SimpleNamespace(get_portfolio_summary=get_summary)
        allocation_stub = AllocationStub()
        with patch("app.routes.exports.get_db_connection", self.factory(captured)), \
             patch("app.routes.exports.portfolio_service", portfolio_stub), \
             patch("app.routes.exports.allocation_service", allocation_stub):
            response = get_allocations_csv(user_id=self.user_id)
        self.assertEqual(calls["summary"], 1)
        self.assertTrue(calls["same_summary"])
        self.assertEqual(captured["options"]["isolation_level"], "REPEATABLE READ")
        self.assertIn("quote_snapshot_at", response.body.decode())
        self.assertEqual(response.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
