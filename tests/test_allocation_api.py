"""Testes de integração para os serviços e API de alocação."""

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.allocation import InvalidAllocationSumError
from app.services.allocation import AllocationService


class MockCursorAllocation:
    def __init__(self, portfolio_id, usdt_id, btc_id):
        self.portfolio_id = portfolio_id
        self.usdt_id = usdt_id
        self.btc_id = btc_id
        self.executed = []
        self.active_version = 1

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        last_q = self.executed[-1][0].strip().upper()
        if "COALESCE(MAX(VERSION)" in last_q:
            return (self.active_version + 1,)
        if "FROM PORTFOLIO_PRIVATE.ALLOCATION_TARGETS" in last_q:
            return (str(uuid4()), self.active_version, datetime.now(timezone.utc))
        if "SELECT ID FROM PORTFOLIO_PRIVATE.ASSETS WHERE" in last_q and "SYMBOL = 'USDT'" in last_q:
            return (str(self.usdt_id),)
        return None

    def fetchall(self):
        last_q = self.executed[-1][0].strip().upper()
        if "FROM PORTFOLIO_PRIVATE.ASSETS WHERE PORTFOLIO_ID" in last_q:
            return [
                (str(self.usdt_id), "USDT", "Tether USD"),
                (str(self.btc_id), "BTC", "Bitcoin"),
            ]
        if "FROM PORTFOLIO_PRIVATE.ALLOCATION_TARGET_ITEMS" in last_q:
            return [
                (str(self.usdt_id), "USDT", "Tether USD", "20.00"),
                (str(self.btc_id), "BTC", "Bitcoin", "80.00"),
            ]
        return []


class TestAllocationService(unittest.TestCase):

    def test_create_orientation_sum_validation(self):
        p_id = uuid4()
        usdt_id = uuid4()
        btc_id = uuid4()
        cur = MockCursorAllocation(p_id, usdt_id, btc_id)
        service = AllocationService()

        # Inválido: soma 90%
        invalid_items = [
            {"asset_id": usdt_id, "target_percent": "20.00"},
            {"asset_id": btc_id, "target_percent": "70.00"},
        ]
        with self.assertRaises(InvalidAllocationSumError):
            service.create_orientation(cur, p_id, invalid_items)

        # Válido: soma 100%
        valid_items = [
            {"asset_id": usdt_id, "target_percent": "20.00"},
            {"asset_id": btc_id, "target_percent": "80.00"},
        ]
        oid, ver = service.create_orientation(cur, p_id, valid_items)
        self.assertEqual(ver, 2)
        self.assertIsNotNone(oid)

    def test_comparison_propagates_quote_completeness_and_freshness(self):
        p_id, usdt_id, btc_id = uuid4(), uuid4(), uuid4()
        cur = MockCursorAllocation(p_id, usdt_id, btc_id)
        snapshot_at = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)

        class CachedPortfolio:
            def get_portfolio_summary(self, cursor, portfolio_id):
                return {
                    "totals": {
                        "balance_usd": Decimal("1000"),
                        "cash_usdt": Decimal("200"),
                        "complete": True,
                        "updated": False,
                        "freshness": "stale",
                        "quote_snapshot_at": snapshot_at,
                    },
                    "positions": [{
                        "asset_id": btc_id,
                        "symbol": "BTC",
                        "name": "Bitcoin",
                        "current_value_usd": Decimal("800"),
                    }],
                }

        result = AllocationService(portfolio_service=CachedPortfolio()).get_allocation_comparison(
            cur, p_id
        )
        self.assertTrue(result["complete"])
        self.assertFalse(result["updated"])
        self.assertEqual(result["freshness"], "stale")
        self.assertEqual(result["quote_snapshot_at"], snapshot_at)


if __name__ == "__main__":
    unittest.main()
