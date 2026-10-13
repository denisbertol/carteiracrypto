"""Script utilitário de seed para validação local e demonstração."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.config import get_settings
from app.db import get_db_connection
from app.domain.ledger import LedgerEngine, LedgerOperation, OperationKind
from app.services.portfolio import PortfolioService


def run_seed():
    settings = get_settings()
    owner_id = settings.owner_user_id
    service = PortfolioService()

    print(f"Iniciando seed de dados demonstrativos para owner_id={owner_id}...")

    with get_db_connection(owner_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, revision, usdt_id = service.get_or_create_portfolio(cur, owner_id)

            # Cadastra ativo TEST
            test_asset_id = uuid4()
            cur.execute(
                """
                INSERT INTO portfolio_private.assets (id, portfolio_id, external_id, symbol, name)
                VALUES (%s, %s, 'test_crypto', 'TEST', 'Test Crypto Asset')
                ON CONFLICT (portfolio_id, external_id) DO UPDATE SET active = true
                RETURNING id;
                """,
                (str(test_asset_id), str(portfolio_id)),
            )
            test_asset_id = UUID(str(cur.fetchone()[0]))

            now = datetime.now(timezone.utc)
            demo_ops = [
                LedgerOperation(uuid4(), usdt_id, "USDT", OperationKind.DEPOSIT, now, 0, Decimal("1000")),
                LedgerOperation(uuid4(), test_asset_id, "TEST", OperationKind.BUY, now, 1, Decimal("2"), Decimal("100"), Decimal("10")),
                LedgerOperation(uuid4(), test_asset_id, "TEST", OperationKind.BUY, now, 2, Decimal("1"), Decimal("250"), Decimal("20")),
                LedgerOperation(uuid4(), test_asset_id, "TEST", OperationKind.SELL, now, 3, Decimal("1"), Decimal("200"), Decimal("5")),
                LedgerOperation(uuid4(), test_asset_id, "TEST", OperationKind.TRANSFER, now, 4, Decimal("1"), None, Decimal("2"), transfer_ref="demo-transfer-1"),
            ]

            # Replay contábil
            projection = LedgerEngine.replay(demo_ops, usdt_id)
            print(f"Caixa final USDT: {projection.cash_usdt}")
            print(f"Despesas avulsas USDT: {projection.standalone_expenses_usdt}")
            print(f"Lucro realizado líquido: {projection.realized_net_usd}")

            # Persiste operações no banco
            for op in demo_ops:
                cur.execute(
                    """
                    INSERT INTO portfolio_private.operations
                    (id, portfolio_id, asset_id, kind, occurred_at, order_index, quantity, unit_price_usd, fee_usdt, transfer_ref)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    (
                        str(op.id), str(portfolio_id), str(op.asset_id), op.kind.value,
                        op.occurred_at, op.order_index, str(op.quantity),
                        str(op.unit_price_usd) if op.unit_price_usd else None,
                        str(op.fee_usdt), op.transfer_ref
                    ),
                )

            # Atualiza projeções
            cur.execute(
                """
                UPDATE portfolio_private.portfolio_projection
                SET cash_usdt = %s, deposits_usdt = %s, withdrawals_usdt = %s,
                    standalone_expenses_usdt = %s, realized_sales_usd = %s, revision = %s
                WHERE portfolio_id = %s;
                """,
                (
                    str(projection.cash_usdt), str(projection.deposits_usdt),
                    str(projection.withdrawals_usdt), str(projection.standalone_expenses_usdt),
                    str(projection.realized_sales_usd), revision + 1, str(portfolio_id)
                ),
            )

            conn.commit()
            print("Seed concluído com sucesso!")


if __name__ == "__main__":
    run_seed()
