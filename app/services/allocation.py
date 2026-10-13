"""Serviço de persistência e orquestração de alocação de ativos."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from app.domain.allocation import (
    AllocationEngine,
    AllocationComparisonItem,
    CurrentPositionItem,
    TargetItem,
    InvalidAllocationSumError,
)
from app.services.portfolio import PortfolioService


class AllocationService:
    def __init__(self, portfolio_service: Optional[PortfolioService] = None) -> None:
        self.portfolio_service = portfolio_service or PortfolioService()

    def create_orientation(
        self,
        cur: Any,
        portfolio_id: UUID,
        items: List[Dict[str, Any]],
    ) -> Tuple[UUID, int]:
        """
        Registra uma nova recomendação de alocação atômica.
        Valida que a soma é 100,00%, inativa a orientação anterior e ativa a nova imediatamente.
        """
        # Carrega dados dos ativos para validação de símbolo e existência
        cur.execute(
            "SELECT id, symbol, name FROM portfolio_private.assets WHERE portfolio_id = %s;",
            (str(portfolio_id),),
        )
        assets_map = {UUID(str(r[0])): (r[1], r[2]) for r in cur.fetchall()}

        target_items: List[TargetItem] = []
        for it in items:
            aid = UUID(str(it["asset_id"]))
            if aid not in assets_map:
                raise ValueError(f"Ativo ID {aid} não cadastrado nesta carteira.")
            sym, name = assets_map[aid]
            pct = Decimal(str(it["target_percent"]))
            target_items.append(TargetItem(asset_id=aid, symbol=sym, name=name, target_percent=pct))

        # Validação estrita do somatório
        AllocationEngine.validate_sum(target_items)

        # Determina o próximo número de versão
        cur.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM portfolio_private.allocation_targets WHERE portfolio_id = %s;",
            (str(portfolio_id),),
        )
        new_version = int(cur.fetchone()[0])

        # Inativa qualquer orientação vigente anterior
        cur.execute(
            "UPDATE portfolio_private.allocation_targets SET active = false WHERE portfolio_id = %s AND active = true;",
            (str(portfolio_id),),
        )

        # Insere nova orientação como ativa
        orientation_id = uuid4()
        now = datetime.now(timezone.utc)
        cur.execute(
            """
            INSERT INTO portfolio_private.allocation_targets (id, portfolio_id, version, effective_at, active)
            VALUES (%s, %s, %s, %s, true);
            """,
            (str(orientation_id), str(portfolio_id), new_version, now),
        )

        # Insere os itens
        for t in target_items:
            cur.execute(
                """
                INSERT INTO portfolio_private.allocation_target_items (orientation_id, asset_id, target_percent)
                VALUES (%s, %s, %s);
                """,
                (str(orientation_id), str(t.asset_id), str(t.target_percent)),
            )

        return orientation_id, new_version

    def get_allocation_comparison(
        self,
        cur: Any,
        portfolio_id: UUID,
        *,
        portfolio_summary: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Calcula e retorna a comparação detalhada de rebalanceamento."""
        # 1. Obtém a orientação ativa
        cur.execute(
            """
            SELECT id, version, effective_at 
            FROM portfolio_private.allocation_targets 
            WHERE portfolio_id = %s AND active = true;
            """,
            (str(portfolio_id),),
        )
        target_row = cur.fetchone()

        if not target_row:
            return {
                "active_orientation": None,
                "complete": True,
                "updated": True,
                "freshness": "fresh",
                "quote_snapshot_at": None,
                "total_balance_usd": Decimal("0.00"),
                "items": [],
            }

        orientation_id = UUID(str(target_row[0]))
        version = int(target_row[1])
        effective_at = target_row[2]

        # Carrega itens da orientação
        cur.execute(
            """
            SELECT i.asset_id, a.symbol, a.name, i.target_percent
            FROM portfolio_private.allocation_target_items i
            JOIN portfolio_private.assets a ON a.id = i.asset_id
            WHERE i.orientation_id = %s;
            """,
            (str(orientation_id),),
        )
        targets = [
            TargetItem(
                asset_id=UUID(str(r[0])),
                symbol=str(r[1]),
                name=str(r[2]),
                target_percent=Decimal(str(r[3])),
            )
            for r in cur.fetchall()
        ]

        # 2. Obtém posições e saldos da carteira
        summary = portfolio_summary or self.portfolio_service.get_portfolio_summary(cur, portfolio_id)
        totals = summary["totals"]
        total_balance = totals["balance_usd"] or Decimal("0.00")
        is_complete = totals["complete"]

        # Monta posições atuais (incluindo USDT como caixa)
        current_positions: Dict[UUID, CurrentPositionItem] = {}

        # Busca ID do USDT
        cur.execute("SELECT id FROM portfolio_private.assets WHERE portfolio_id = %s AND symbol = 'USDT';", (str(portfolio_id),))
        usdt_id = UUID(str(cur.fetchone()[0]))
        current_positions[usdt_id] = CurrentPositionItem(
            asset_id=usdt_id,
            symbol="USDT",
            name="Tether USD",
            current_value_usd=totals["cash_usdt"],
        )

        for pos in summary["positions"]:
            if pos["current_value_usd"] is not None:
                current_positions[pos["asset_id"]] = CurrentPositionItem(
                    asset_id=pos["asset_id"],
                    symbol=pos["symbol"],
                    name=pos["name"],
                    current_value_usd=pos["current_value_usd"],
                )

        # 3. Executa o cálculo pelo motor
        comparison_items = AllocationEngine.calculate(
            total_balance_usd=total_balance,
            targets=targets,
            current_positions=current_positions,
        )

        return {
            "orientation_id": orientation_id,
            "version": version,
            "effective_at": effective_at,
            "total_balance_usd": total_balance,
            "complete": is_complete,
            "updated": bool(totals.get("updated", is_complete)),
            "freshness": totals.get("freshness", "fresh" if is_complete else "incomplete"),
            "quote_snapshot_at": totals.get("quote_snapshot_at"),
            "items": [
                {
                    "asset_id": it.asset_id,
                    "symbol": it.symbol,
                    "name": it.name,
                    "target_percent": it.target_percent,
                    "current_value_usd": it.current_value_usd,
                    "ideal_value_usd": it.ideal_value_usd,
                    "adjustment_usd": it.adjustment_usd,
                    "deviation_percent": it.deviation_percent,
                }
                for it in comparison_items
            ],
        }

    def get_history(self, cur: Any, portfolio_id: UUID) -> List[Dict[str, Any]]:
        """Lista todas as versões de orientações arquivadas para histórico."""
        cur.execute(
            """
            SELECT id, version, effective_at, active, created_at
            FROM portfolio_private.allocation_targets
            WHERE portfolio_id = %s
            ORDER BY version DESC;
            """,
            (str(portfolio_id),),
        )
        return [
            {
                "id": str(r[0]),
                "version": r[1],
                "effective_at": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
                "active": r[3],
                "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
            }
            for r in cur.fetchall()
        ]
