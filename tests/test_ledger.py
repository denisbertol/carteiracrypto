"""Suíte de testes para o motor contábil cobrindo os cenários de aceitação CA-01 a CA-16."""

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.ledger import (
    LedgerEngine,
    LedgerOperation,
    OperationKind,
    InsufficientBalanceError,
    InvalidOperationError,
)

USDT_ID = uuid4()
BTC_ID = uuid4()
ETH_ID = uuid4()


def create_op(
    kind: OperationKind,
    asset_id=BTC_ID,
    asset_symbol="BTC",
    quantity="1",
    unit_price="100",
    fee="0",
    hour=12,
    order_index=0,
) -> LedgerOperation:
    return LedgerOperation(
        id=uuid4(),
        asset_id=asset_id,
        asset_symbol=asset_symbol,
        kind=kind,
        occurred_at=datetime(2026, 9, 1, hour, 0, 0, tzinfo=timezone.utc),
        order_index=order_index,
        quantity=Decimal(str(quantity)),
        unit_price_usd=Decimal(str(unit_price)) if unit_price is not None else None,
        fee_usdt=Decimal(str(fee)),
    )


class TestLedgerEngine(unittest.TestCase):

    def test_ca03_ca04_compras_vendas_e_lucro(self):
        """Valida o exemplo oficial do roadmap/onboarding:
        1. Depósito de 1000 USDT
        2. Compra de 2 TEST a USD 100 com taxa 10 USDT
        3. Compra de 1 TEST a USD 250 com taxa 20 USDT
        -> Esperado: 3 TEST, custo USD 480, média USD 160, caixa 520 USDT
        4. Venda de 1 TEST a USD 200 com taxa 5 USDT
        -> Esperado: 2 TEST, custo USD 320, lucro realizado USD 35, caixa 715 USDT
        """
        ops = [
            create_op(OperationKind.DEPOSIT, asset_id=USDT_ID, asset_symbol="USDT", quantity="1000", unit_price=None, hour=10),
            create_op(OperationKind.BUY, quantity="2", unit_price="100", fee="10", hour=11),
            create_op(OperationKind.BUY, quantity="1", unit_price="250", fee="20", hour=12),
        ]

        p = LedgerEngine.replay(ops, USDT_ID)
        pos = p.positions[BTC_ID]
        self.assertEqual(p.cash_usdt, Decimal("520"))
        self.assertEqual(pos.quantity, Decimal("3"))
        self.assertEqual(pos.remaining_cost_usd, Decimal("480"))
        self.assertEqual(pos.average_price_usd, Decimal("160"))

        # Passo 4: Venda
        ops.append(create_op(OperationKind.SELL, quantity="1", unit_price="200", fee="5", hour=13))
        p2 = LedgerEngine.replay(ops, USDT_ID)
        pos2 = p2.positions[BTC_ID]
        self.assertEqual(p2.cash_usdt, Decimal("715"))
        self.assertEqual(pos2.quantity, Decimal("2"))
        self.assertEqual(pos2.remaining_cost_usd, Decimal("320"))
        self.assertEqual(pos2.average_price_usd, Decimal("160"))
        self.assertEqual(pos2.realized_sales_usd, Decimal("35"))
        self.assertEqual(p2.realized_sales_usd, Decimal("35"))
        self.assertEqual(p2.realized_net_usd, Decimal("35"))

    def test_ca05_venda_total_zerando_custo_residual(self):
        """Liquidação de 100% da posição deve zerar custo residual."""
        ops = [
            create_op(OperationKind.DEPOSIT, asset_id=USDT_ID, asset_symbol="USDT", quantity="500", unit_price=None, hour=10),
            create_op(OperationKind.BUY, quantity="3", unit_price="100", fee="1", hour=11),
            create_op(OperationKind.SELL, quantity="3", unit_price="120", fee="2", hour=12),
        ]
        p = LedgerEngine.replay(ops, USDT_ID)
        pos = p.positions[BTC_ID]
        self.assertEqual(pos.quantity, Decimal("0"))
        self.assertEqual(pos.remaining_cost_usd, Decimal("0"))
        self.assertIsNone(pos.average_price_usd)
        # Lucro: (3*120 - 2) - 301 = 358 - 301 = 57
        self.assertEqual(pos.realized_sales_usd, Decimal("57"))

    def test_ca08_ca09_transferencias_internas_com_e_sem_taxa(self):
        """Transferência entre carteiras próprias não altera quantidade nem custo da cripto."""
        ops = [
            create_op(OperationKind.DEPOSIT, asset_id=USDT_ID, asset_symbol="USDT", quantity="1000", unit_price=None, hour=10),
            create_op(OperationKind.BUY, quantity="2", unit_price="100", fee="0", hour=11),
            # Transferência de 1 BTC com taxa de 2 USDT
            create_op(OperationKind.TRANSFER, quantity="1", unit_price=None, fee="2", hour=12),
        ]
        p = LedgerEngine.replay(ops, USDT_ID)
        pos = p.positions[BTC_ID]
        self.assertEqual(pos.quantity, Decimal("2"))
        self.assertEqual(pos.remaining_cost_usd, Decimal("200"))
        self.assertEqual(p.cash_usdt, Decimal("798"))  # 1000 - 200 - 2
        self.assertEqual(p.standalone_expenses_usdt, Decimal("2"))
        self.assertEqual(p.realized_net_usd, Decimal("-2"))

    def test_ca10_taxa_avulsa(self):
        """Taxa avulsa debita caixa e contabiliza despesa realizada."""
        ops = [
            create_op(OperationKind.DEPOSIT, asset_id=USDT_ID, asset_symbol="USDT", quantity="100", unit_price=None, hour=10),
            create_op(OperationKind.FEE, asset_id=USDT_ID, asset_symbol="USDT", quantity="15", unit_price=None, fee="0", hour=11),
        ]
        p = LedgerEngine.replay(ops, USDT_ID)
        self.assertEqual(p.cash_usdt, Decimal("85"))
        self.assertEqual(p.standalone_expenses_usdt, Decimal("15"))
        self.assertEqual(p.realized_net_usd, Decimal("-15"))

    def test_ca11_rejeicao_saldo_negativo(self):
        """Qualquer operação que gere saldo de caixa ou cripto negativo deve falhar."""
        ops = [
            create_op(OperationKind.DEPOSIT, asset_id=USDT_ID, asset_symbol="USDT", quantity="50", unit_price=None, hour=10),
            create_op(OperationKind.BUY, quantity="1", unit_price="100", fee="0", hour=11),  # Falta caixa
        ]
        with self.assertRaises(InsufficientBalanceError):
            LedgerEngine.replay(ops, USDT_ID)

        ops2 = [
            create_op(OperationKind.DEPOSIT, asset_id=USDT_ID, asset_symbol="USDT", quantity="50", unit_price=None, hour=10),
            create_op(OperationKind.WITHDRAWAL, asset_id=USDT_ID, asset_symbol="USDT", quantity="60", unit_price=None, hour=11),
        ]
        with self.assertRaises(InsufficientBalanceError):
            LedgerEngine.replay(ops2, USDT_ID)

    def test_ca12_reordenacao_e_empate_temporal(self):
        """Operações no mesmo timestamp seguem order_index."""
        t = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
        op_dep = LedgerOperation(uuid4(), USDT_ID, "USDT", OperationKind.DEPOSIT, t, 0, Decimal("200"))
        op_buy = LedgerOperation(uuid4(), BTC_ID, "BTC", OperationKind.BUY, t, 1, Decimal("1"), Decimal("100"), Decimal("0"))
        op_sell = LedgerOperation(uuid4(), BTC_ID, "BTC", OperationKind.SELL, t, 2, Decimal("1"), Decimal("150"), Decimal("0"))

        p = LedgerEngine.replay([op_sell, op_dep, op_buy], USDT_ID)
        self.assertEqual(p.positions[BTC_ID].quantity, Decimal("0"))
        self.assertEqual(p.cash_usdt, Decimal("250"))

    def test_ca16_conservacao_contabil(self):
        """Total - Aportes Líquidos = Resultado Realizado Líquido + Não Realizado."""
        ops = [
            create_op(OperationKind.DEPOSIT, asset_id=USDT_ID, asset_symbol="USDT", quantity="1000", unit_price=None, hour=10),
            create_op(OperationKind.BUY, quantity="2", unit_price="100", fee="10", hour=11),
            create_op(OperationKind.BUY, quantity="1", unit_price="250", fee="20", hour=12),
            create_op(OperationKind.SELL, quantity="1", unit_price="200", fee="5", hour=13),
            create_op(OperationKind.TRANSFER, quantity="1", unit_price=None, fee="2", hour=14),
        ]
        p = LedgerEngine.replay(ops, USDT_ID)

        quote_btc = Decimal("180")
        crypto_value = p.positions[BTC_ID].quantity * quote_btc
        crypto_cost = p.positions[BTC_ID].remaining_cost_usd
        unrealized = crypto_value - crypto_cost

        total_patrimonio = p.cash_usdt + crypto_value
        aportes_liquidos = p.deposits_usdt - p.withdrawals_usdt

        resultado_total = p.realized_net_usd + unrealized
        self.assertEqual(total_patrimonio - aportes_liquidos, resultado_total)


if __name__ == "__main__":
    unittest.main()
