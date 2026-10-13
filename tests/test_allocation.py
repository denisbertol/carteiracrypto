"""Suíte de testes unitários para o motor de alocação e rebalanceamento."""

import unittest
from decimal import Decimal
from uuid import uuid4

from app.domain.allocation import (
    AllocationEngine,
    TargetItem,
    CurrentPositionItem,
    InvalidAllocationSumError,
)

BTC_ID = uuid4()
ETH_ID = uuid4()
SOL_ID = uuid4()
USDT_ID = uuid4()


class TestAllocationEngine(unittest.TestCase):

    def test_ca01_valid_sum_and_ideal_calculation(self):
        """Valida alocação com soma 100% (BTC 50%, ETH 30%, USDT 20%) para saldo de 10.000 USD."""
        targets = [
            TargetItem(BTC_ID, "BTC", "Bitcoin", Decimal("50.00")),
            TargetItem(ETH_ID, "ETH", "Ethereum", Decimal("30.00")),
            TargetItem(USDT_ID, "USDT", "Tether", Decimal("20.00")),
        ]
        current_positions = {
            BTC_ID: CurrentPositionItem(BTC_ID, "BTC", "Bitcoin", Decimal("4500.00")),
            ETH_ID: CurrentPositionItem(ETH_ID, "ETH", "Ethereum", Decimal("3500.00")),
            USDT_ID: CurrentPositionItem(USDT_ID, "USDT", "Tether", Decimal("2000.00")),
        }
        total_balance = Decimal("10000.00")

        results = AllocationEngine.calculate(total_balance, targets, current_positions)
        res_map = {r.asset_id: r for r in results}

        self.assertEqual(res_map[BTC_ID].ideal_value_usd, Decimal("5000.00"))
        self.assertEqual(res_map[ETH_ID].ideal_value_usd, Decimal("3000.00"))
        self.assertEqual(res_map[USDT_ID].ideal_value_usd, Decimal("2000.00"))

    def test_ca02_invalid_sum_rejection(self):
        """Rejeita somatório diferente de 100,00% (ex: 95% ou 100.05%)."""
        targets_under = [
            TargetItem(BTC_ID, "BTC", "Bitcoin", Decimal("50.00")),
            TargetItem(ETH_ID, "ETH", "Ethereum", Decimal("30.00")),
            TargetItem(USDT_ID, "USDT", "Tether", Decimal("15.00")),
        ]
        with self.assertRaises(InvalidAllocationSumError) as cm:
            AllocationEngine.validate_sum(targets_under)
        self.assertIn("95.00%", str(cm.exception))
        self.assertIn("+5.00%", str(cm.exception))

        targets_over = [
            TargetItem(BTC_ID, "BTC", "Bitcoin", Decimal("60.00")),
            TargetItem(USDT_ID, "USDT", "Tether", Decimal("40.05")),
        ]
        with self.assertRaises(InvalidAllocationSumError):
            AllocationEngine.validate_sum(targets_over)

    def test_ca03_adjustment_and_deviation_calculation(self):
        """BTC 50% em 10.000 USD (ideal 5.000 USD), atual 4.500 USD -> ajuste +500 USD, desvio -10,00%."""
        targets = [
            TargetItem(BTC_ID, "BTC", "Bitcoin", Decimal("50.00")),
            TargetItem(USDT_ID, "USDT", "Tether", Decimal("50.00")),
        ]
        current_positions = {
            BTC_ID: CurrentPositionItem(BTC_ID, "BTC", "Bitcoin", Decimal("4500.00")),
            USDT_ID: CurrentPositionItem(USDT_ID, "USDT", "Tether", Decimal("5500.00")),
        }
        total_balance = Decimal("10000.00")

        results = AllocationEngine.calculate(total_balance, targets, current_positions)
        res_map = {r.asset_id: r for r in results}

        btc = res_map[BTC_ID]
        self.assertEqual(btc.adjustment_usd, Decimal("500.00"))
        self.assertEqual(btc.deviation_percent, Decimal("-10.00"))

        usdt = res_map[USDT_ID]
        self.assertEqual(usdt.adjustment_usd, Decimal("-500.00"))
        self.assertEqual(usdt.deviation_percent, Decimal("10.00"))

    def test_ca04_asset_with_zero_target(self):
        """Ativo mantido com meta 0% deve ter ideal USD 0,00, ajuste -atual e desvio N/A."""
        targets = [
            TargetItem(BTC_ID, "BTC", "Bitcoin", Decimal("80.00")),
            TargetItem(USDT_ID, "USDT", "Tether", Decimal("20.00")),
        ]
        # Possui SOL em carteira, mas SOL não tem meta recomendada (0%)
        current_positions = {
            BTC_ID: CurrentPositionItem(BTC_ID, "BTC", "Bitcoin", Decimal("8000.00")),
            USDT_ID: CurrentPositionItem(USDT_ID, "USDT", "Tether", Decimal("1000.00")),
            SOL_ID: CurrentPositionItem(SOL_ID, "SOL", "Solana", Decimal("1000.00")),
        }
        total_balance = Decimal("10000.00")

        results = AllocationEngine.calculate(total_balance, targets, current_positions)
        res_map = {r.asset_id: r for r in results}

        self.assertIn(SOL_ID, res_map)
        sol = res_map[SOL_ID]
        self.assertEqual(sol.target_percent, Decimal("0.00"))
        self.assertEqual(sol.ideal_value_usd, Decimal("0.00"))
        self.assertEqual(sol.adjustment_usd, Decimal("-1000.00"))
        self.assertIsNone(sol.deviation_percent)

    def test_ca05_new_asset_with_no_current_position(self):
        """Novo ativo recomendado sem saldo deve aparecer com atual 0,00 USD e ajuste +ideal."""
        targets = [
            TargetItem(BTC_ID, "BTC", "Bitcoin", Decimal("70.00")),
            TargetItem(SOL_ID, "SOL", "Solana", Decimal("10.00")),
            TargetItem(USDT_ID, "USDT", "Tether", Decimal("20.00")),
        ]
        current_positions = {
            BTC_ID: CurrentPositionItem(BTC_ID, "BTC", "Bitcoin", Decimal("8000.00")),
            USDT_ID: CurrentPositionItem(USDT_ID, "USDT", "Tether", Decimal("2000.00")),
        }
        total_balance = Decimal("10000.00")

        results = AllocationEngine.calculate(total_balance, targets, current_positions)
        res_map = {r.asset_id: r for r in results}

        self.assertIn(SOL_ID, res_map)
        sol = res_map[SOL_ID]
        self.assertEqual(sol.current_value_usd, Decimal("0.00"))
        self.assertEqual(sol.ideal_value_usd, Decimal("1000.00"))
        self.assertEqual(sol.adjustment_usd, Decimal("1000.00"))

    def test_ca06_reconciliation_exact_cent_sum(self):
        """Reconciliação da soma das posições ideais com o saldo total (sem resíduo de centavos)."""
        targets = [
            TargetItem(BTC_ID, "BTC", "Bitcoin", Decimal("33.33")),
            TargetItem(ETH_ID, "ETH", "Ethereum", Decimal("33.33")),
            TargetItem(USDT_ID, "USDT", "Tether", Decimal("33.34")),
        ]
        current_positions = {}
        total_balance = Decimal("1000.00")

        results = AllocationEngine.calculate(total_balance, targets, current_positions)
        sum_ideals = sum((r.ideal_value_usd for r in results), Decimal("0"))
        self.assertEqual(sum_ideals, total_balance)


if __name__ == "__main__":
    unittest.main()
