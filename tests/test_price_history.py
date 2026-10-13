import json
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import httpx

from app.domain.ledger import LedgerOperation, OperationKind
from app.services.coingecko import CoinGeckoClient, HistoryBatch
from app.services.provider_budget import BudgetDecision
from app.services.price_history import (
    EvolutionPoint,
    PriceHistoryService,
    build_evolution,
    modified_dietz,
    period_returns,
    price_day,
)


USDT = uuid4()
BTC = uuid4()


def op(kind, asset, day, quantity, price=None, index=0):
    return LedgerOperation(
        id=uuid4(), asset_id=asset, asset_symbol="USDT" if asset == USDT else "BTC",
        kind=kind, occurred_at=datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12),
        order_index=index, quantity=Decimal(quantity),
        unit_price_usd=Decimal(price) if price is not None else None,
    )


class PriceDayTests(unittest.TestCase):
    def test_midnight_point_closes_previous_day(self):
        self.assertEqual(price_day(datetime(2026, 10, 2, tzinfo=timezone.utc)), date(2026, 10, 1))
        self.assertEqual(price_day(datetime(2026, 10, 2, 0, 0, 1, tzinfo=timezone.utc)), date(2026, 10, 2))

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            price_day(datetime(2026, 10, 2))


class BuildEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.d0 = date(2026, 10, 1)
        self.ops = [
            op(OperationKind.DEPOSIT, USDT, self.d0, "1000", index=0),
            op(OperationKind.BUY, BTC, self.d0, "0.01", "50000", index=1),
            op(OperationKind.DEPOSIT, USDT, self.d0 + timedelta(days=2), "500", index=2),
        ]

    def test_daily_points_replay_ledger_and_value_positions(self):
        prices = {BTC: [(self.d0, Decimal("50000")), (self.d0 + timedelta(days=1), Decimal("60000"))]}
        points = build_evolution(self.ops, USDT, prices, self.d0 + timedelta(days=2))
        self.assertEqual([p.invested_usd for p in points], [Decimal("1000.00"), Decimal("1000.00"), Decimal("1500.00")])
        self.assertEqual(points[0].value_usd, Decimal("1000.00"))
        self.assertEqual(points[1].value_usd, Decimal("1100.00"))
        # Day 3 carries the last known price forward.
        self.assertEqual(points[2].value_usd, Decimal("1600.00"))

    def test_missing_price_is_unknown_not_zero(self):
        points = build_evolution(self.ops, USDT, {}, self.d0 + timedelta(days=1))
        self.assertIsNone(points[0].value_usd)
        self.assertIsNone(points[1].value_usd)

    def test_stale_price_beyond_carry_forward_window_is_unknown(self):
        prices = {BTC: [(self.d0, Decimal("50000"))]}
        points = build_evolution(self.ops, USDT, prices, self.d0 + timedelta(days=9))
        self.assertIsNotNone(points[7].value_usd)
        self.assertIsNone(points[8].value_usd)

    def test_today_uses_dashboard_balance_for_reconciliation(self):
        points = build_evolution(self.ops, USDT, {}, self.d0, today_value_usd=Decimal("1234.567"))
        self.assertEqual(points[-1].value_usd, Decimal("1234.57"))

    def test_window_is_capped_but_keeps_prior_state(self):
        prices = {BTC: [(self.d0 + timedelta(days=2), Decimal("40000"))]}
        points = build_evolution(self.ops, USDT, prices, self.d0 + timedelta(days=2), max_days=1)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].invested_usd, Decimal("1500.00"))
        self.assertEqual(points[0].value_usd, Decimal("1400.00"))

    def test_no_operations_yields_no_points(self):
        self.assertEqual(build_evolution([], USDT, {}, self.d0), [])


class ReturnTests(unittest.TestCase):
    def test_single_deposit_return_matches_simple_gain(self):
        points = [EvolutionPoint(date(2026, 1, 1), Decimal("1000"), Decimal("1000")),
                  EvolutionPoint(date(2026, 1, 2), Decimal("1000"), Decimal("1100"))]
        self.assertEqual(modified_dietz(Decimal("0"), Decimal("0"), points), Decimal("10.00"))

    def test_late_deposit_is_weighted_less(self):
        points = [EvolutionPoint(date(2026, 1, d), Decimal("1000"), Decimal("1000")) for d in range(1, 4)]
        points.append(EvolutionPoint(date(2026, 1, 4), Decimal("2000"), Decimal("2100")))
        result = modified_dietz(Decimal("1000"), Decimal("1000"), points)
        self.assertEqual(result, Decimal("8.00"))

    def test_unknown_end_value_has_no_return(self):
        points = [EvolutionPoint(date(2026, 1, 1), Decimal("1000"), None)]
        self.assertIsNone(modified_dietz(Decimal("0"), Decimal("0"), points))

    def test_young_portfolio_uses_total_as_last_12_months(self):
        points = [EvolutionPoint(date(2026, 1, 1), Decimal("1000"), Decimal("1000")),
                  EvolutionPoint(date(2026, 1, 2), Decimal("1000"), Decimal("1200"))]
        returns = period_returns(points, date(2026, 1, 1))
        self.assertEqual(returns["total"], Decimal("20.00"))
        self.assertEqual(returns["last_12m"], Decimal("20.00"))


class FetchDailyHistoryTests(unittest.TestCase):
    NOW = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)

    def client(self, handler):
        return CoinGeckoClient("demo-key", transport=httpx.MockTransport(handler), now=lambda: self.NOW)

    def test_parses_points_and_drops_invalid_or_future_items(self):
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            midnight = int(datetime(2026, 10, 12, tzinfo=timezone.utc).timestamp() * 1000)
            future = int((self.NOW + timedelta(hours=2)).timestamp() * 1000)
            return httpx.Response(200, json={"prices": [
                [midnight, 62000.5], [midnight + 1000, -1], ["bad"], [future, 1], [midnight + 2000, 62100],
            ]})

        with self.client(handler) as client:
            batch = client.fetch_daily_history("bitcoin", 30)
        self.assertIsNone(batch.error_code)
        self.assertEqual(batch.request_count, 1)
        self.assertEqual([price for _, price in batch.points], [Decimal("62000.5"), Decimal("62100")])
        self.assertIn("/coins/bitcoin/market_chart", captured["url"])
        self.assertIn("days=30", captured["url"])
        self.assertIn("interval=daily", captured["url"])

    def test_rate_limit_and_unknown_coin_are_reported(self):
        with self.client(lambda request: httpx.Response(429, headers={"Retry-After": "90"})) as client:
            limited = client.fetch_daily_history("bitcoin")
        self.assertEqual((limited.error_code, limited.retry_after_seconds), ("provider_rate_limited", 90))
        with self.client(lambda request: httpx.Response(404)) as client:
            self.assertEqual(client.fetch_daily_history("bitcoin").error_code, "provider_unknown_coin")

    def test_unsafe_coin_id_never_reaches_http(self):
        def handler(request):
            raise AssertionError("HTTP nÃ£o deveria ocorrer")
        with self.client(handler) as client:
            batch = client.fetch_daily_history("../simple/price")
        self.assertEqual((batch.error_code, batch.request_count), ("invalid_provider_id", 0))


class BackfillCursor:
    def __init__(self, tracker, portfolio_id, asset_id):
        self.tracker = tracker
        self.portfolio_id = portfolio_id
        self.asset_id = asset_id
        self.result = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        sql = " ".join(query.lower().split())
        self.tracker["statements"].append((sql, params))
        if sql.startswith("select id from portfolio_private.portfolios"):
            self.result = (self.portfolio_id,)
        elif sql.startswith("select m.asset_id, m.provider_coin_id"):
            self.rows = [(self.asset_id, "bitcoin")]
        elif sql.startswith("select min(occurred_at)"):
            self.result = (self.tracker["now"] - timedelta(days=10),)
        elif sql.startswith("select count(*)"):
            self.result = (0,)

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.rows


class BackfillConnection:
    def __init__(self, tracker, cursor):
        self.tracker = tracker
        self._cursor = cursor

    def __enter__(self):
        self.tracker["active"] = True
        return self

    def __exit__(self, *args):
        self.tracker["active"] = False
        return False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.tracker["commits"] += 1


class RunBackfillTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        self.settings = SimpleNamespace(
            quote_mode="coingecko",
            coingecko_demo_api_key=SimpleNamespace(get_secret_value=lambda: "demo-key"),
            coingecko_window_start=self.now - timedelta(days=1),
            coingecko_window_end=self.now + timedelta(days=29),
            coingecko_call_limit=100,
        )
        self.tracker = {"statements": [], "commits": 0, "active": False, "now": self.now}
        self.cursor = BackfillCursor(self.tracker, uuid4(), uuid4())

    def connection_factory(self):
        @contextmanager
        def factory(owner_id):
            yield BackfillConnection(self.tracker, self.cursor).__enter__()
            self.tracker["active"] = False
        return factory

    def client_factory(self, batch):
        tracker = self.tracker

        class Client:
            def __init__(self, api_key):
                self.calls = []

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def fetch_daily_history(self, coin_id, days):
                if tracker["active"]:
                    raise AssertionError("HTTP ocorreu com transaÃ§Ã£o aberta")
                tracker["fetch"] = (coin_id, days)
                return batch
        return Client

    def backfill(self, batch, decision=BudgetDecision(True, reserved_count=1)):
        service = PriceHistoryService()
        with patch("app.services.price_history.get_settings", return_value=self.settings), \
             patch.object(service.budgets, "reserve", return_value=decision) as reserve:
            result = service.run_backfill(
                uuid4(), connection_factory=self.connection_factory(),
                client_factory=self.client_factory(batch), now=lambda: self.now,
            )
        return result, reserve

    def test_reserves_quota_before_http_and_publishes_prices(self):
        stamp = datetime(2026, 10, 11, tzinfo=timezone.utc)
        batch = HistoryBatch(points=[(stamp, Decimal("61000")), (self.now, Decimal("62000"))], request_count=1)
        result, reserve = self.backfill(batch)
        self.assertEqual(result, {"state": "completed", "imported_assets": 1, "failed_assets": 0, "pending_assets": 0})
        self.assertEqual(reserve.call_args.kwargs["request_count"], 1)
        self.assertEqual(self.tracker["fetch"], ("bitcoin", 12))
        inserts = [p for s, p in self.tracker["statements"]
                   if s.startswith("insert into portfolio_private.asset_daily_prices")]
        self.assertEqual([p[2] for p in inserts], [date(2026, 10, 10), date(2026, 10, 12)])
        completed = next(p for s, p in self.tracker["statements"] if "set status='completed'" in s)
        self.assertEqual(completed[:3], (date(2026, 10, 10), date(2026, 10, 12), 2))
        self.assertEqual(self.tracker["commits"], 2)

    def test_failure_is_recorded_without_prices(self):
        result, _ = self.backfill(HistoryBatch(error_code="provider_unknown_coin", request_count=1))
        self.assertEqual(result["failed_assets"], 1)
        self.assertFalse(any(s.startswith("insert into portfolio_private.asset_daily_prices")
                             for s, _ in self.tracker["statements"]))
        failed = next(p for s, p in self.tracker["statements"] if "set status='failed'" in s)
        self.assertEqual(failed[0], "provider_unknown_coin")

    def test_exhausted_quota_blocks_without_http(self):
        decision = BudgetDecision(False, "quota_exhausted", self.now + timedelta(hours=3))
        result, _ = self.backfill(HistoryBatch(), decision=decision)
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["reason"], "quota_exhausted")
        self.assertNotIn("fetch", self.tracker)

    def test_unconfigured_provider_is_blocked_before_database(self):
        self.settings.quote_mode = "unavailable"
        result, _ = self.backfill(HistoryBatch())
        self.assertEqual(result, {"state": "blocked", "reason": "config_required"})
        self.assertEqual(self.tracker["statements"], [])


if __name__ == "__main__":
    unittest.main()
