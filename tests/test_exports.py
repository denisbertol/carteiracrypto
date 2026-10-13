"""Suíte de testes para exportações CSV e proteção contra formula injection."""

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.services.exports import (
    sanitize_text,
    export_assets_csv,
    export_operations_csv,
    export_results_csv,
    export_allocations_csv,
)


class TestExports(unittest.TestCase):

    def test_formula_injection_sanitization(self):
        self.assertEqual(sanitize_text("=cmd|' /C calc'!A0"), "'=cmd|' /C calc'!A0")
        self.assertEqual(sanitize_text("+12345"), "'+12345")
        self.assertEqual(sanitize_text("@SUM(A1:A10)"), "'@SUM(A1:A10)")
        self.assertEqual(sanitize_text("  -dangerous"), "'  -dangerous")
        self.assertEqual(sanitize_text("normal_text"), "normal_text")
        self.assertEqual(sanitize_text(""), "")
        self.assertEqual(sanitize_text(None), "")

    def test_export_assets_csv(self):
        assets = [
            {"id": uuid4(), "external_id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "active": True},
            {"id": uuid4(), "external_id": "=malicious", "symbol": "MAL", "name": "Malicious", "active": False},
        ]
        csv_text = export_assets_csv(assets)
        self.assertIn("\r\n", csv_text)
        self.assertIn("id,external_id,symbol,name,active", csv_text)
        self.assertIn("BTC,Bitcoin,true", csv_text)
        self.assertIn("MAL,Malicious,false", csv_text)
        self.assertIn("'=malicious", csv_text)

    def test_export_operations_csv_precision(self):
        ops = [
            {
                "id": uuid4(),
                "kind": "buy",
                "asset_id": uuid4(),
                "occurred_at": datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc),
                "order_index": 0,
                "quantity": Decimal("0.000000000000000001"),
                "unit_price_usd": Decimal("65432.123456789012345678"),
                "fee_usdt": Decimal("1.5"),
                "transfer_ref": None,
                "source_label": None,
                "destination_label": None,
                "note": "Compra fracionada",
                "created_at": datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc),
            }
        ]
        csv_text = export_operations_csv(ops)
        self.assertIn("0.000000000000000001", csv_text)
        self.assertIn("65432.123456789012345678", csv_text)

    def test_export_results_csv(self):
        positions = [
            {
                "asset_id": uuid4(),
                "quantity": Decimal("2"),
                "remaining_cost_usd": Decimal("320"),
                "average_price_usd": Decimal("160"),
                "realized_sales_usd": Decimal("35"),
                "quote_usd": Decimal("180"),
                "quote_at": datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc),
                "quote_source": "fixture",
                "quote_status": "stale",
                "quote_fetched_at": datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc),
                "quote_error": "provider_timeout",
                "quote_freshness": "stale",
                "current_value_usd": Decimal("360"),
                "unrealized_usd": Decimal("40"),
            }
        ]
        totals = {
            "realized_sales_usd": Decimal("35"),
            "crypto_value_usd": Decimal("360"),
            "unrealized_usd": Decimal("40"),
            "cash_usdt": Decimal("715"),
            "expenses_usd": Decimal("0"),
            "realized_net_usd": Decimal("35"),
            "balance_usd": Decimal("1075"),
            "cash_percent": Decimal("66.51"),
            "complete": True,
            "updated": False,
            "freshness": "stale",
            "quote_snapshot_at": datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc),
        }
        csv_text = export_results_csv(revision=5, positions=positions, totals=totals)
        self.assertIn("position,", csv_text)
        self.assertIn("total,", csv_text)
        self.assertIn("1075", csv_text)
        self.assertIn("quote_snapshot_at", csv_text)
        self.assertIn("provider_timeout", csv_text)
        self.assertIn("false,stale", csv_text)

    def test_export_allocations_preserves_existing_columns_and_appends_freshness(self):
        csv_text = export_allocations_csv(
            version=3,
            items=[{
                "symbol": "BTC", "name": "Bitcoin", "target_percent": Decimal("80"),
                "current_value_usd": Decimal("800"), "ideal_value_usd": Decimal("800"),
                "adjustment_usd": Decimal("0"), "deviation_percent": Decimal("0"),
            }],
            complete=True,
            updated=False,
            freshness="stale",
            quote_snapshot_at=datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        self.assertIn("deviation_percent,complete,updated,freshness,quote_snapshot_at", csv_text)
        self.assertIn("BTC,Bitcoin,80,800,800,0,0,true,false,stale,", csv_text)


if __name__ == "__main__":
    unittest.main()
