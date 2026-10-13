import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.services.quotes import QuoteReader, QuoteStatus
from app.services.portfolio import PortfolioService


class QuoteCursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.params = None

    def execute(self, query, params=None):
        self.query = " ".join(query.lower().split())
        self.params = params

    def fetchall(self):
        return self.rows


class PortfolioSummaryCursor:
    def __init__(self, asset_id, now):
        self.asset_id = asset_id
        self.now = now
        self.query = ""
        self.result = None

    def execute(self, query, params=None):
        self.query = " ".join(query.lower().split())
        if "select revision from portfolio_private.portfolios" in self.query:
            self.result = (7,)
        elif "from portfolio_private.portfolio_projection" in self.query:
            self.result = ("0", "0", "0", "0", "0")

    def fetchone(self):
        return self.result

    def fetchall(self):
        if "from portfolio_private.position_projections" in self.query:
            return [(self.asset_id, "BTC", "Bitcoin", "2", "100", "0")]
        if "from portfolio_private.assets a" in self.query and "latest_quotes" in self.query:
            return [(
                self.asset_id, "BTC", Decimal("70"), self.now - timedelta(minutes=40),
                self.now - timedelta(minutes=40), "coingecko", None,
            )]
        return []


class QuoteReaderTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        self.portfolio_id = uuid4()
        self.btc_id, self.eth_id, self.new_id, self.usdt_id = [uuid4() for _ in range(4)]
        self.settings = SimpleNamespace(quote_mode="coingecko", demo_quote_usd=Decimal("180"))

    def test_reads_portfolio_cache_and_reports_fresh_stale_missing_and_usdt(self):
        cur = QuoteCursor([
            (self.btc_id, "BTC", Decimal("60000"), self.now - timedelta(minutes=10),
             self.now - timedelta(minutes=10), "coingecko", None),
            (self.eth_id, "ETH", Decimal("3000"), self.now - timedelta(minutes=31),
             self.now - timedelta(minutes=31), "coingecko", "provider_timeout"),
            (self.new_id, "NEW", None, None, None, None, None),
            (self.usdt_id, "USDT", None, None, None, None, None),
        ])
        reader = QuoteReader(settings=self.settings)
        quotes = reader.get_quotes(
            [self.btc_id, self.eth_id, self.new_id, self.usdt_id],
            portfolio_id=self.portfolio_id,
            cur=cur,
            now=self.now,
        )

        self.assertIn("latest_quotes", cur.query)
        self.assertEqual(cur.params[0], str(self.portfolio_id))
        self.assertEqual(quotes[self.btc_id].status, QuoteStatus.AVAILABLE)
        self.assertEqual(quotes[self.btc_id].price_usd, Decimal("60000"))
        self.assertEqual(quotes[self.btc_id].source, "coingecko")
        self.assertEqual(quotes[self.btc_id].fetched_at, self.now - timedelta(minutes=10))
        self.assertEqual(quotes[self.eth_id].status, QuoteStatus.STALE)
        self.assertEqual(quotes[self.eth_id].error_code, "provider_timeout")
        self.assertEqual(quotes[self.new_id].status, QuoteStatus.UNAVAILABLE)
        self.assertEqual(quotes[self.usdt_id].price_usd, Decimal("1"))
        self.assertEqual(quotes[self.usdt_id].source, "usd_peg")

    def test_fixture_mode_is_ephemeral_and_does_not_query_or_write_cache(self):
        class NoQueryCursor:
            def execute(self, *args, **kwargs):
                raise AssertionError("fixture não deve consultar o cache")

        reader = QuoteReader(settings=SimpleNamespace(
            quote_mode="fixture", demo_quote_usd=Decimal("180")
        ))
        result = reader.get_quotes(
            [self.btc_id], portfolio_id=self.portfolio_id, cur=NoQueryCursor(), now=self.now
        )
        self.assertEqual(result[self.btc_id].price_usd, Decimal("180"))
        self.assertEqual(result[self.btc_id].source, "fixture_demo")

    def test_missing_database_context_never_falls_back_to_http(self):
        reader = QuoteReader(settings=self.settings)
        result = reader.get_quotes([self.btc_id], now=self.now)
        self.assertEqual(result[self.btc_id].status, QuoteStatus.UNAVAILABLE)
        self.assertEqual(result[self.btc_id].error_code, "quote_cache_unavailable")

    def test_portfolio_summary_keeps_stale_values_but_marks_snapshot_not_updated(self):
        cur = PortfolioSummaryCursor(self.btc_id, self.now)
        service = PortfolioService(QuoteReader(settings=self.settings))
        summary = service.get_portfolio_summary(cur, self.portfolio_id)
        self.assertTrue(summary["totals"]["complete"])
        self.assertFalse(summary["totals"]["updated"])
        self.assertEqual(summary["quote_status"], "complete")
        self.assertEqual(summary["quote_freshness"], "stale")
        self.assertEqual(summary["positions"][0]["quote_status"], "stale")
        self.assertEqual(summary["positions"][0]["current_value_usd"], Decimal("140"))


if __name__ == "__main__":
    unittest.main()
