"""Motor de domínio puro para validação de alocação e cálculo de rebalanceamento."""

from dataclasses import dataclass
from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Dict, List, Optional
from uuid import UUID

getcontext().prec = 80

TARGET_SUM_PERCENT = Decimal("100.00")


class InvalidAllocationSumError(ValueError):
    """Lançado quando a soma dos percentuais da recomendação não atinge 100,00%."""
    pass


@dataclass
class TargetItem:
    asset_id: UUID
    symbol: str
    name: str
    target_percent: Decimal


@dataclass
class CurrentPositionItem:
    asset_id: UUID
    symbol: str
    name: str
    current_value_usd: Decimal


@dataclass
class AllocationComparisonItem:
    asset_id: UUID
    symbol: str
    name: str
    target_percent: Decimal
    current_value_usd: Decimal
    ideal_value_usd: Decimal
    adjustment_usd: Decimal
    deviation_percent: Optional[Decimal]


class AllocationEngine:
    """Motor matemático e contábil de alocação da carteira."""

    @staticmethod
    def validate_sum(targets: List[TargetItem]) -> None:
        total = sum((t.target_percent for t in targets), Decimal("0"))
        # Compara com tolerância centesimal estrita
        if total != TARGET_SUM_PERCENT:
            diff = TARGET_SUM_PERCENT - total
            sign = "+" if diff > 0 else ""
            raise InvalidAllocationSumError(
                f"A soma dos percentuais deve totalizar exatamente 100,00%. "
                f"Soma calculada: {total:.2f}%. Diferença para 100%: {sign}{diff:.2f}%."
            )

    @staticmethod
    def calculate(
        total_balance_usd: Decimal,
        targets: List[TargetItem],
        current_positions: Dict[UUID, CurrentPositionItem],
    ) -> List[AllocationComparisonItem]:
        # Valida a soma dos percentuais cadastrados
        AllocationEngine.validate_sum(targets)

        targets_map = {t.asset_id: t for t in targets}
        all_asset_ids = set(targets_map.keys()).union(set(current_positions.keys()))

        # Etapa 1: Cálculo inicial com maior resto para reconciliação exata de centavos
        unrounded_ideals = {}
        for aid in all_asset_ids:
            target = targets_map.get(aid)
            pct = target.target_percent if target else Decimal("0")
            unrounded_ideals[aid] = (total_balance_usd * pct) / Decimal("100")

        # Se saldo total for zero ou negativo, todos ideais são 0
        if total_balance_usd <= Decimal("0"):
            ideals_rounded = {aid: Decimal("0.00") for aid in all_asset_ids}
        else:
            # Algoritmo do Maior Resto (Largest Remainder) para distribuição de centavos
            # 1. Trunca para 2 casas decimais
            truncated = {}
            remainders = {}
            allocated_cents = Decimal("0")
            for aid, val in unrounded_ideals.items():
                cents = (val * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                # Separa piso de centavos
                floor_cents = (val * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                truncated[aid] = val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                remainders[aid] = val - truncated[aid]
                allocated_cents += truncated[aid]

            discrepancy = total_balance_usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) - allocated_cents
            ideals_rounded = dict(truncated)

            # Ajusta centavos residuais ordenando pelos maiores restos
            if discrepancy != Decimal("0"):
                step = Decimal("0.01") if discrepancy > 0 else Decimal("-0.01")
                num_cents = int(abs(discrepancy * Decimal("100")))
                sorted_by_remainder = sorted(
                    all_asset_ids,
                    key=lambda a: remainders[a],
                    reverse=(discrepancy > 0),
                )
                for i in range(min(num_cents, len(sorted_by_remainder))):
                    ideals_rounded[sorted_by_remainder[i]] += step

        # Etapa 2: Construção da lista comparativa
        comparison_list: List[AllocationComparisonItem] = []

        for aid in sorted(all_asset_ids, key=lambda x: (targets_map.get(x) is None, targets_map.get(x).symbol if targets_map.get(x) else "")):
            target = targets_map.get(aid)
            curr = current_positions.get(aid)

            symbol = target.symbol if target else (curr.symbol if curr else "")
            name = target.name if target else (curr.name if curr else "")
            target_pct = target.target_percent if target else Decimal("0.00")
            current_val = curr.current_value_usd if curr else Decimal("0.00")
            ideal_val = ideals_rounded[aid]

            # Ajuste = Ideal - Atual (positivo = faltante/comprar, negativo = excesso/vender)
            adjustment = ideal_val - current_val

            # Desvio % = (Atual / Ideal) - 1 se Ideal > 0
            if ideal_val > Decimal("0"):
                dev_pct = ((current_val / ideal_val) - Decimal("1")) * Decimal("100")
                dev_pct = dev_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                dev_pct = None

            comparison_list.append(
                AllocationComparisonItem(
                    asset_id=aid,
                    symbol=symbol,
                    name=name,
                    target_percent=target_pct,
                    current_value_usd=current_val,
                    ideal_value_usd=ideal_val,
                    adjustment_usd=adjustment,
                    deviation_percent=dev_pct,
                )
            )

        return comparison_list
