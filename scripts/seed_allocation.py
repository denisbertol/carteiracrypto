"""Script utilitário de seed para registrar a recomendação de alocação inicial baseada na planilha de referência."""

from decimal import Decimal
from uuid import UUID, uuid4

from app.config import get_settings
from app.db import get_db_connection
from app.services.allocation import AllocationService
from app.services.portfolio import PortfolioService


def run_seed_allocation():
    settings = get_settings()
    owner_id = settings.owner_user_id
    portfolio_service = PortfolioService()
    allocation_service = AllocationService(portfolio_service)

    print(f"Iniciando seed de alocação recomendada para owner_id={owner_id}...")

    with get_db_connection(owner_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, usdt_id = portfolio_service.get_or_create_portfolio(cur, owner_id)

            # Garante que BTC e ETH estejam cadastrados na carteira
            assets_to_seed = [
                ("bitcoin", "BTC", "Bitcoin"),
                ("ethereum", "ETH", "Ethereum"),
            ]

            seeded_assets = {"USDT": usdt_id}

            for external_id, symbol, name in assets_to_seed:
                cur.execute(
                    """
                    INSERT INTO portfolio_private.assets (id, portfolio_id, external_id, symbol, name)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (portfolio_id, external_id) DO UPDATE SET active = true
                    RETURNING id;
                    """,
                    (str(uuid4()), str(portfolio_id), external_id, symbol, name),
                )
                asset_id = UUID(str(cur.fetchone()[0]))
                seeded_assets[symbol] = asset_id

            # Cria recomendação modelo: 50% BTC, 30% ETH, 20% USDT (Caixa) = 100.00%
            items = [
                {"asset_id": seeded_assets["BTC"], "target_percent": Decimal("50.00")},
                {"asset_id": seeded_assets["ETH"], "target_percent": Decimal("30.00")},
                {"asset_id": seeded_assets["USDT"], "target_percent": Decimal("20.00")},
            ]

            orientation_id, version = allocation_service.create_orientation(cur, portfolio_id, items)
            conn.commit()

            print(f"Orientação de alocação versão {version} cadastrada com sucesso (ID: {orientation_id})!")

            # Exibe comparação calculada
            comparison = allocation_service.get_allocation_comparison(cur, portfolio_id)
            print("\n--- Comparativo de Rebalanceamento Inicial ---")
            print(f"Patrimônio total: ${comparison['total_balance_usd']}")
            for item in comparison["items"]:
                print(
                    f"[{item['symbol']}] Alvo: {item['target_percent']}% | "
                    f"Atual: ${item['current_value_usd']} | "
                    f"Ideal: ${item['ideal_value_usd']} | "
                    f"Ajuste: ${item['adjustment_usd']} ({item['deviation_percent']}%)"
                )


if __name__ == "__main__":
    run_seed_allocation()
