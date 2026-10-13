"""Dashboard consistency checks; PostgreSQL case requires TEST_DATABASE_URL."""

import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import Response

from app.routes.dashboard import get_dashboard

try:
    import psycopg
except ImportError:  # pragma: no cover - optional for local unit suite
    psycopg = None


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
ROOT = Path(__file__).resolve().parents[1]


class DashboardCursor:
    def __init__(self, portfolio_id):
        self.portfolio_id = portfolio_id
        self.result = None
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        sql = " ".join(query.lower().split())
        self.statements.append((sql, params))
        if "select id from portfolio_private.portfolios" in sql:
            self.result = (self.portfolio_id,) if self.portfolio_id is not None else None

    def fetchone(self):
        return self.result

    def fetchall(self):
        return []


class DashboardConnection:
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


class DashboardRouteTests(unittest.TestCase):
    def test_dashboard_uses_one_quote_snapshot_and_read_only_repeatable_transaction(self):
        user_id, portfolio_id = uuid4(), uuid4()
        cursor = DashboardCursor(portfolio_id)
        connection = DashboardConnection(cursor)
        captured = {}
        snapshot_at = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        portfolio = {
            "revision": 4,
            "positions": [{
                "asset_id": uuid4(), "symbol": "BTC", "quote_usd": Decimal("61000"),
                "quote_at": snapshot_at, "quote_fetched_at": snapshot_at,
                "quote_source": "coingecko", "quote_status": "available",
                "quote_freshness": "available", "quote_error": None,
            }],
            "totals": {"balance_usd": Decimal("61000"), "complete": True, "updated": True},
            "quote_status": "complete", "quote_freshness": "fresh",
            "quote_snapshot_at": snapshot_at,
        }

        class PortfolioStub:
            def get_portfolio_summary(self, cur, requested_portfolio_id):
                captured["summary_calls"] = captured.get("summary_calls", 0) + 1
                captured["portfolio_id"] = requested_portfolio_id
                return portfolio

        class AllocationStub:
            def get_allocation_comparison(self, cur, requested_portfolio_id, *, portfolio_summary):
                captured["same_summary"] = portfolio_summary is portfolio
                return {"complete": True, "updated": True, "total_balance_usd": Decimal("61000")}

        class HistoryStub:
            def get_evolution(self, cur, requested_portfolio_id, *, today_value_usd, now):
                captured["same_cursor"] = cur is cursor
                captured["today_value"] = today_value_usd
                return {"points": [{"day": "2026-09-28", "invested_usd": Decimal("60000.00"),
                                    "value_usd": today_value_usd}]}

        @contextmanager
        def connection_factory(requested_user_id, **options):
            captured["user_id"] = requested_user_id
            captured["options"] = options
            yield connection

        response = Response()
        with patch("app.routes.dashboard.get_db_connection", connection_factory), \
             patch("app.routes.dashboard.portfolio_service", PortfolioStub()), \
             patch("app.routes.dashboard.allocation_service", AllocationStub()), \
             patch("app.routes.dashboard.history_service", HistoryStub()):
            result = get_dashboard(response, user_id=user_id)

        self.assertEqual(captured["options"], {"isolation_level": "REPEATABLE READ", "read_only": True})
        self.assertEqual(captured["user_id"], user_id)
        self.assertTrue(captured["same_summary"])
        self.assertEqual(captured["summary_calls"], 1)
        self.assertEqual(result["portfolio"]["totals"]["balance_usd"], "61000")
        self.assertEqual(result["allocation"]["total_balance_usd"], "61000")
        self.assertTrue(captured["same_cursor"])
        self.assertEqual(captured["today_value"], Decimal("61000"))
        self.assertEqual(result["evolution"]["points"][-1]["value_usd"], "61000")
        self.assertEqual(result["quotes"][0]["price_usd"], "61000")
        self.assertEqual(result["quote_snapshot_at"], snapshot_at.isoformat())
        self.assertEqual(result["portfolio_revision"], 4)
        self.assertEqual(result["freshness"], "fresh")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(cursor.statements[0][0], "select id from portfolio_private.portfolios where owner_id=%s;")

    def test_dashboard_without_portfolio_does_not_create_or_read_financial_rows(self):
        cursor = DashboardCursor(None)
        connection = DashboardConnection(cursor)

        @contextmanager
        def connection_factory(user_id, **options):
            yield connection

        with patch("app.routes.dashboard.get_db_connection", connection_factory), \
             patch("app.routes.dashboard.portfolio_service") as portfolio_service, \
             patch("app.routes.dashboard.allocation_service") as allocation_service:
            result = get_dashboard(Response(), user_id=uuid4())
        self.assertIsNone(result["portfolio"])
        self.assertEqual(result["quotes"], [])
        portfolio_service.get_portfolio_summary.assert_not_called()
        allocation_service.get_allocation_comparison.assert_not_called()
        self.assertEqual(len(cursor.statements), 1)


@unittest.skipUnless(TEST_DATABASE_URL and psycopg, "Não verificado: configure TEST_DATABASE_URL para um PostgreSQL descartável.")
class DashboardPostgresSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with psycopg.connect(TEST_DATABASE_URL) as conn:
            for filename in ("001_initial.sql", "002_allocation_targets.sql", "003_price_monitoring.sql",
                             "004_price_history.sql"):
                conn.execute((ROOT / "migrations" / filename).read_text(encoding="utf-8"))

    def test_concurrent_quote_update_is_invisible_inside_dashboard_snapshot(self):
        owner_id, portfolio_id, asset_id = uuid4(), uuid4(), uuid4()
        now = datetime.now(timezone.utc)
        with psycopg.connect(TEST_DATABASE_URL) as conn:
            conn.execute("SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),))
            conn.execute(
                "INSERT INTO portfolio_private.portfolios (id, owner_id) VALUES (%s, %s)",
                (portfolio_id, owner_id),
            )
            conn.execute(
                "INSERT INTO portfolio_private.assets (id, portfolio_id, external_id, symbol, name) "
                "VALUES (%s, %s, 'snapshot-btc', 'BTC', 'Bitcoin')",
                (asset_id, portfolio_id),
            )
            conn.execute(
                "INSERT INTO portfolio_private.latest_quotes "
                "(portfolio_id, asset_id, price_usd, quoted_at, provider) "
                "VALUES (%s, %s, 61000, %s, 'coingecko')",
                (portfolio_id, asset_id, now),
            )

        try:
            with psycopg.connect(TEST_DATABASE_URL) as reader:
                with reader.transaction():
                    reader.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                    reader.execute("SET LOCAL ROLE carteira_app")
                    reader.execute(
                        "SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),)
                    )
                    first = reader.execute(
                        "SELECT price_usd FROM portfolio_private.latest_quotes WHERE portfolio_id=%s",
                        (portfolio_id,),
                    ).fetchone()[0]
                    with psycopg.connect(TEST_DATABASE_URL) as writer:
                        writer.execute(
                            "SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),)
                        )
                        writer.execute(
                            "UPDATE portfolio_private.latest_quotes SET price_usd=62000 "
                            "WHERE portfolio_id=%s AND asset_id=%s",
                            (portfolio_id, asset_id),
                        )
                    second = reader.execute(
                        "SELECT price_usd FROM portfolio_private.latest_quotes WHERE portfolio_id=%s",
                        (portfolio_id,),
                    ).fetchone()[0]
                    self.assertEqual(first, second)
                    self.assertEqual(str(second), "61000")
        finally:
            with psycopg.connect(TEST_DATABASE_URL) as conn:
                conn.execute(
                    "DELETE FROM portfolio_private.portfolios WHERE id=%s", (portfolio_id,)
                )


if __name__ == "__main__":
    unittest.main()
