"""Pure decimal rules for evaluating a price target against a quote."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from typing import Literal


@dataclass(frozen=True)
class TargetEvaluation:
    distance_percent: Decimal
    result: Literal["inside", "outside"]


def _finite_decimal(value: Decimal | int | str, name: str) -> Decimal:
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{name} deve ser um número decimal válido.")
    if not number.is_finite():
        raise ValueError(f"{name} deve ser finito.")
    return number


def classify_target(
    target_price: Decimal | int | str,
    quote_price: Decimal | int | str,
    proximity_percent: Decimal | int | str,
) -> TargetEvaluation:
    """Return distance and proximity result; the boundary belongs to the range."""
    target = _finite_decimal(target_price, "Preço-alvo")
    quote = _finite_decimal(quote_price, "Cotação")
    limit = _finite_decimal(proximity_percent, "Limite de proximidade")

    if target <= 0:
        raise ValueError("Preço-alvo deve ser positivo.")
    if quote <= 0:
        raise ValueError("Cotação deve ser positiva.")
    if not Decimal("0") <= limit <= Decimal("100"):
        raise ValueError("Limite de proximidade deve ficar entre 0 e 100.")

    with localcontext() as context:
        # Preserve room for 18-digit prices and repeating percentages.
        context.prec = max(context.prec, 80)
        distance = abs(quote - target) / target * Decimal("100")

    return TargetEvaluation(
        distance_percent=distance,
        result="inside" if distance <= limit else "outside",
    )
