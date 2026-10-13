"""Carga inicial da carteira: quantidades e caixa, com custo de abertura.

O preço de mercado não é gravado. O valor informado na planilha vira apenas
o custo da compra de abertura, para o preço médio e o caixa baterem com o
snapshot. A cotação atual entra depois pela CoinGecko.
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from app.config import get_settings
from app.db import get_db_connection
from app.domain.ledger import LedgerEngine, LedgerOperation, OperationKind
from app.services.portfolio import PortfolioService

NOTE = "carga-inicial"
CASH_USDT = Decimal("36673.00")

# símbolo, id CoinGecko, nome, quantidade, custo de abertura em USD
HOLDINGS = [
    ("BTC", "bitcoin", "Bitcoin", Decimal("0.3614"), Decimal("29948.50")),
    ("ETH", "ethereum", "Ethereum", Decimal("0.3395"), Decimal("861.56")),
    ("SOL", "solana", "Solana", Decimal("0.3047"), Decimal("33.54")),
    ("LINK", "chainlink", "Chainlink", Decimal("44.81"), Decimal("589.65")),
    ("ONDO", "ondo-finance", "Ondo", Decimal("1076.49"), Decimal("544.74")),
    ("ASTER", "aster-2", "Aster", Decimal("1078.13"), Decimal("761.65")),
    ("RAY", "raydium", "Raydium", Decimal("256.61"), Decimal("574.81")),
]


def run_seed():
    settings = get_settings()
    owner_id = settings.owner_user_id
    service = PortfolioService()
    opened_at = datetime.now(timezone.utc).replace(microsecond=0)

    with get_db_connection(owner_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, revision, usdt_id = service.get_or_create_portfolio(cur, owner_id)
            cur.execute(
                "SELECT COUNT(*) FROM portfolio_private.operations WHERE portfolio_id = %s AND deleted_at IS NULL;",
                (str(portfolio_id),),
            )
            existing = int(cur.fetchone()[0])
            if existing:
                raise SystemExit(
                    f"A carteira já tem {existing} lançamentos. A carga inicial não foi aplicada."
                )

            asset_ids = {}
            for symbol, coin_id, name, _qty, _cost in HOLDINGS:
                cur.execute(
                    """
                    INSERT INTO portfolio_private.assets (id, portfolio_id, external_id, symbol, name)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (portfolio_id, external_id) DO UPDATE SET active = true, symbol = EXCLUDED.symbol, name = EXCLUDED.name
                    RETURNING id;
                    """,
                    (str(uuid4()), str(portfolio_id), coin_id, symbol, name),
                )
                asset_id = cur.fetchone()[0]
                asset_ids[symbol] = asset_id
                cur.execute(
                    """
                    INSERT INTO portfolio_private.asset_price_mappings
                    (portfolio_id, asset_id, provider, provider_coin_id, status, version)
                    VALUES (%s, %s, 'coingecko', %s, 'valid', 1)
                    ON CONFLICT (portfolio_id, asset_id) DO UPDATE SET
                        provider_coin_id = EXCLUDED.provider_coin_id, status = 'valid', updated_at = now();
                    """,
                    (str(portfolio_id), str(asset_id), coin_id),
                )

            debits = []
            for symbol, _coin, _name, quantity, cost in HOLDINGS:
                unit = (cost / quantity).quantize(Decimal("1e-18"), rounding=ROUND_HALF_UP)
                debits.append((symbol, quantity, unit, quantity * unit))
            deposit = (sum(debit for *_rest, debit in debits) + CASH_USDT).quantize(
                Decimal("1e-18"), rounding=ROUND_HALF_UP
            )
            ops = [
                LedgerOperation(
                    uuid4(), usdt_id, "USDT", OperationKind.DEPOSIT, opened_at, 0,
                    deposit, note=NOTE,
                )
            ]
            for index, (symbol, quantity, unit, _debit) in enumerate(debits, start=1):
                ops.append(LedgerOperation(
                    uuid4(), asset_ids[symbol], symbol, OperationKind.BUY, opened_at, index,
                    quantity, unit, note=NOTE,
                ))

            projection = LedgerEngine.replay(ops, usdt_id)
            for op in ops:
                cur.execute(
                    """
                    INSERT INTO portfolio_private.operations
                    (id, portfolio_id, asset_id, kind, occurred_at, order_index, quantity, unit_price_usd, fee_usdt, note)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        str(op.id), str(portfolio_id), str(op.asset_id), op.kind.value,
                        op.occurred_at, op.order_index, str(op.quantity),
                        str(op.unit_price_usd) if op.unit_price_usd is not None else None,
                        str(op.fee_usdt), op.note,
                    ),
                )

            new_rev = revision + 1
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
                    str(projection.realized_sales_usd), new_rev, str(portfolio_id),
                ),
            )
            for asset_id, pos in projection.positions.items():
                cur.execute(
                    """
                    INSERT INTO portfolio_private.position_projections
                    (portfolio_id, asset_id, quantity, remaining_cost_usd, realized_sales_usd, revision)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (portfolio_id, asset_id) DO UPDATE SET
                        quantity = EXCLUDED.quantity, remaining_cost_usd = EXCLUDED.remaining_cost_usd,
                        realized_sales_usd = EXCLUDED.realized_sales_usd, revision = EXCLUDED.revision;
                    """,
                    (str(portfolio_id), str(asset_id), str(pos.quantity), str(pos.remaining_cost_usd), str(pos.realized_sales_usd), new_rev),
                )
            cur.execute(
                "UPDATE portfolio_private.portfolios SET revision = %s WHERE id = %s;",
                (new_rev, str(portfolio_id)),
            )
            conn.commit()
            print(f"Carga aplicada. Caixa USDT: {projection.cash_usdt}")
            for symbol, _coin, _name, quantity, _cost in HOLDINGS:
                pos = projection.positions[asset_ids[symbol]]
                print(f"  {symbol}: {pos.quantity} (esperado {quantity})")


if __name__ == "__main__":
    run_seed()
