"""Motor contábil puro para reconstrução da carteira e posições crypto."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, getcontext
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

# Configura precisão decimal de 80 dígitos para eliminação de resíduos
getcontext().prec = 80

USDT_SYMBOL = "USDT"
MAX_INPUT_DECIMALS = 18
MAX_INPUT_INTEGER_DIGITS = 18


class OperationKind(str, Enum):
    BUY = "buy"
    SELL = "sell"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    FEE = "fee"


class InsufficientBalanceError(ValueError):
    """Lançado quando uma operação geraria saldo ou quantidade negativos."""
    pass


class InvalidOperationError(ValueError):
    """Lançado quando os parâmetros de uma operação violam as regras contábeis."""
    pass


@dataclass
class LedgerOperation:
    id: UUID
    asset_id: UUID
    asset_symbol: str
    kind: OperationKind
    occurred_at: datetime
    order_index: int
    quantity: Decimal
    unit_price_usd: Optional[Decimal] = None
    fee_usdt: Decimal = Decimal("0")
    transfer_ref: Optional[str] = None
    source_label: Optional[str] = None
    destination_label: Optional[str] = None
    note: Optional[str] = None

    def __post_init__(self) -> None:
        self._validate_limits(self.quantity, "quantity")
        if self.quantity <= 0:
            raise InvalidOperationError("Quantidade deve ser estritamente positiva.")

        if self.fee_usdt is not None:
            self._validate_limits(self.fee_usdt, "fee_usdt")
            if self.fee_usdt < 0:
                raise InvalidOperationError("Taxa em USDT não pode ser negativa.")

        if self.unit_price_usd is not None:
            self._validate_limits(self.unit_price_usd, "unit_price_usd")
            if self.unit_price_usd <= 0:
                raise InvalidOperationError("Preço unitário deve ser estritamente positivo.")

    @staticmethod
    def _validate_limits(val: Decimal, field_name: str) -> None:
        if not val.is_finite():
            raise InvalidOperationError(f"Valor do campo {field_name} não é finito.")
        s = f"{val:f}"
        if "." in s:
            int_part, dec_part = s.split(".")
            if len(dec_part) > MAX_INPUT_DECIMALS:
                raise InvalidOperationError(
                    f"Campo {field_name} excede o limite de {MAX_INPUT_DECIMALS} casas decimais."
                )
        else:
            int_part = s
        if len(int_part.lstrip("-")) > MAX_INPUT_INTEGER_DIGITS:
            raise InvalidOperationError(
                f"Campo {field_name} excede o limite de {MAX_INPUT_INTEGER_DIGITS} dígitos inteiros."
            )


@dataclass
class PositionProjection:
    asset_id: UUID
    symbol: str
    quantity: Decimal = field(default_factory=lambda: Decimal("0"))
    remaining_cost_usd: Decimal = field(default_factory=lambda: Decimal("0"))
    realized_sales_usd: Decimal = field(default_factory=lambda: Decimal("0"))

    @property
    def average_price_usd(self) -> Optional[Decimal]:
        if self.quantity > Decimal("0"):
            return self.remaining_cost_usd / self.quantity
        return None


@dataclass
class PortfolioProjection:
    cash_usdt: Decimal = field(default_factory=lambda: Decimal("0"))
    deposits_usdt: Decimal = field(default_factory=lambda: Decimal("0"))
    withdrawals_usdt: Decimal = field(default_factory=lambda: Decimal("0"))
    standalone_expenses_usdt: Decimal = field(default_factory=lambda: Decimal("0"))
    realized_sales_usd: Decimal = field(default_factory=lambda: Decimal("0"))
    positions: Dict[UUID, PositionProjection] = field(default_factory=dict)

    @property
    def realized_net_usd(self) -> Decimal:
        """Resultado realizado líquido = lucros de vendas - despesas avulsas/transferências."""
        return self.realized_sales_usd - self.standalone_expenses_usdt


class LedgerEngine:
    """Motor contábil puro para reconstrução cronológica da carteira."""

    @staticmethod
    def replay(
        operations: List[LedgerOperation],
        usdt_asset_id: UUID,
    ) -> PortfolioProjection:
        # Ordenação cronológica estrita: occurred_at, order_index, id
        sorted_ops = sorted(
            operations,
            key=lambda op: (op.occurred_at, op.order_index, str(op.id)),
        )

        portfolio = PortfolioProjection()

        for op in sorted_ops:
            pos = portfolio.positions.setdefault(
                op.asset_id,
                PositionProjection(asset_id=op.asset_id, symbol=op.asset_symbol),
            )

            match op.kind:
                case OperationKind.DEPOSIT:
                    if op.asset_id != usdt_asset_id:
                        raise InvalidOperationError("Depósitos externos são permitidos exclusivamente em USDT.")
                    portfolio.cash_usdt += op.quantity
                    portfolio.deposits_usdt += op.quantity

                case OperationKind.WITHDRAWAL:
                    if op.asset_id != usdt_asset_id:
                        raise InvalidOperationError("Saques externos são permitidos exclusivamente em USDT.")
                    if portfolio.cash_usdt < op.quantity:
                        raise InsufficientBalanceError(
                            f"Saldo insuficiente em caixa para saque de {op.quantity} USDT. "
                            f"Caixa atual: {portfolio.cash_usdt} USDT."
                        )
                    portfolio.cash_usdt -= op.quantity
                    portfolio.withdrawals_usdt += op.quantity

                case OperationKind.BUY:
                    if op.asset_id == usdt_asset_id:
                        raise InvalidOperationError("Não é permitido negociar USDT contra USDT.")
                    if op.unit_price_usd is None:
                        raise InvalidOperationError("Operação de compra requer unit_price_usd.")

                    trade_value = op.quantity * op.unit_price_usd
                    total_debit = trade_value + op.fee_usdt

                    if portfolio.cash_usdt < total_debit:
                        raise InsufficientBalanceError(
                            f"Saldo de caixa insuficiente para compra. Requer {total_debit} USDT, "
                            f"disponível {portfolio.cash_usdt} USDT."
                        )

                    portfolio.cash_usdt -= total_debit
                    pos.quantity += op.quantity
                    pos.remaining_cost_usd += total_debit

                case OperationKind.SELL:
                    if op.asset_id == usdt_asset_id:
                        raise InvalidOperationError("Não é permitido vender USDT.")
                    if op.unit_price_usd is None:
                        raise InvalidOperationError("Operação de venda requer unit_price_usd.")
                    if pos.quantity < op.quantity:
                        raise InsufficientBalanceError(
                            f"Quantidade insuficiente do ativo {op.asset_symbol} para venda. "
                            f"Disponível: {pos.quantity}, Solicitado: {op.quantity}."
                        )

                    gross_proceeds = op.quantity * op.unit_price_usd
                    net_proceeds = gross_proceeds - op.fee_usdt

                    # Baixa de custo proporcional
                    if pos.quantity == op.quantity:
                        # Baixa integral de 100% da posição zerando custo residual
                        cost_reduction = pos.remaining_cost_usd
                    else:
                        cost_reduction = pos.remaining_cost_usd * (op.quantity / pos.quantity)

                    realized_gain = net_proceeds - cost_reduction

                    pos.quantity -= op.quantity
                    pos.remaining_cost_usd -= cost_reduction
                    pos.realized_sales_usd += realized_gain

                    portfolio.cash_usdt += net_proceeds
                    portfolio.realized_sales_usd += realized_gain

                case OperationKind.TRANSFER:
                    # Transferência entre carteiras próprias: quantidade e custo não mudam
                    if op.asset_id != usdt_asset_id and pos.quantity < op.quantity:
                        raise InsufficientBalanceError(
                            f"Quantidade insuficiente do ativo {op.asset_symbol} para transferência."
                        )
                    if op.fee_usdt > Decimal("0"):
                        if portfolio.cash_usdt < op.fee_usdt:
                            raise InsufficientBalanceError(
                                f"Saldo insuficiente para taxa de transferência de {op.fee_usdt} USDT."
                            )
                        portfolio.cash_usdt -= op.fee_usdt
                        portfolio.standalone_expenses_usdt += op.fee_usdt

                case OperationKind.FEE:
                    # Despesa avulsa em USDT
                    if portfolio.cash_usdt < op.quantity:
                        raise InsufficientBalanceError(
                            f"Saldo insuficiente para taxa avulsa de {op.quantity} USDT."
                        )
                    portfolio.cash_usdt -= op.quantity
                    portfolio.standalone_expenses_usdt += op.quantity

        return portfolio
