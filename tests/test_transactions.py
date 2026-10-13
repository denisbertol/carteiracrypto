"""Suíte de testes para idempotência, concorrência e integridade das mutações."""

import unittest
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.services.portfolio import (
    compute_request_hash,
    PortfolioService,
    RevisionConflictError,
    IdempotencyConflictError,
)
from app.services.quotes import QuoteReader, QuoteResult, QuoteStatus


class MockCursor:
    """Cursor simulado em memória para testes de serviço."""
    def __init__(self, portfolio_id, revision, owner_id):
        self.portfolio_id = portfolio_id
        self.revision = revision
        self.owner_id = owner_id
        self.executed_queries = []

    def execute(self, query, params=None):
        self.executed_queries.append((query, params))

    def fetchone(self):
        last_q = self.executed_queries[-1][0].strip().upper()
        if "FROM PORTFOLIO_PRIVATE.PORTFOLIOS WHERE OWNER_ID" in last_q:
            return (str(self.portfolio_id), self.revision)
        if "FROM PORTFOLIO_PRIVATE.PORTFOLIOS WHERE ID" in last_q:
            return (self.revision,)
        if "FROM PORTFOLIO_PRIVATE.PORTFOLIO_PROJECTION" in last_q:
            return ("715.0", "1000.0", "0.0", "2.0", "35.0")
        if "FROM PORTFOLIO_PRIVATE.ASSETS WHERE PORTFOLIO_ID" in last_q:
            return (str(uuid4()),)
        return None

    def fetchall(self):
        last_q = self.executed_queries[-1][0].strip().upper()
        if "FROM PORTFOLIO_PRIVATE.POSITION_PROJECTIONS" in last_q:
            # asset_id, symbol, name, quantity, remaining_cost_usd, realized_sales_usd
            return [
                (str(uuid4()), "BTC", "Bitcoin", "2.0", "320.0", "35.0")
            ]
        return []


class TestTransactions(unittest.TestCase):

    def test_request_hash_determinism(self):
        body1 = {"asset_id": "xyz", "quantity": "2", "kind": "buy"}
        body2 = {"kind": "buy", "quantity": "2", "asset_id": "xyz"}
        h1 = compute_request_hash("POST", "/api/v1/operations", body1, 5)
        h2 = compute_request_hash("POST", "/api/v1/operations", body2, 5)
        self.assertEqual(h1, h2)

        # Alterando a revisão ou corpo deve produzir hash distinto
        h3 = compute_request_hash("POST", "/api/v1/operations", body1, 6)
        self.assertNotEqual(h1, h3)

    def test_get_portfolio_summary_with_fixture(self):
        portfolio_id = uuid4()
        owner_id = uuid4()
        cur = MockCursor(portfolio_id, 3, owner_id)

        service = PortfolioService(QuoteReader(settings=SimpleNamespace(
            quote_mode="fixture", demo_quote_usd=Decimal("180")
        )))
        summary = service.get_portfolio_summary(cur, portfolio_id)

        self.assertEqual(summary["revision"], 3)
        self.assertEqual(len(summary["positions"]), 1)
        btc = summary["positions"][0]
        self.assertEqual(btc["symbol"], "BTC")
        self.assertEqual(btc["quantity"], Decimal("2.0"))
        self.assertEqual(btc["average_price_usd"], Decimal("160.0"))

        totals = summary["totals"]
        self.assertEqual(totals["cash_usdt"], Decimal("715.0"))
        # Com fixture a USD 180: 2 * 180 = 360 USD em crypto
        self.assertEqual(totals["crypto_value_usd"], Decimal("360.0"))
        self.assertEqual(totals["balance_usd"], Decimal("1075.0"))
        self.assertTrue(totals["complete"])


if __name__ == "__main__":
    unittest.main()
