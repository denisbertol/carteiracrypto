"""Serviço de encaminhamento de lançamentos do Telegram para o Ledger da Carteira.

Atende a D-01, D-04, RF-06 e RF-09:
- Usa chave de idempotência determinística baseada no update_id do Telegram.
- Executa replay contábil completo pelo LedgerEngine.
- Lançamento inválido (ex: saldo insuficiente) não altera nada e devolve recusa.
- Operação aceita persiste atômica, limpa rascunho e atualiza projeções.
"""

from datetime import datetime
from decimal import Decimal
import json
from typing import Any, Dict, Optional, Tuple
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from app.db import lock_portfolio_for_update
from app.domain.ledger import (
    LedgerEngine,
    LedgerOperation,
    OperationKind,
    InsufficientBalanceError,
    InvalidOperationError,
)
from app.services.portfolio import PortfolioService, compute_request_hash
from app.services.telegram_draft import clear_draft, record_applied_update


def derive_telegram_idempotency_key(update_id: int) -> UUID:
    """Deriva UUID v5 determinístico para idempotência a partir do update_id do Telegram."""
    return uuid5(NAMESPACE_URL, f"telegram-update-{update_id}")


def execute_telegram_launch(
    cur: Any,
    portfolio_id: UUID,
    owner_id: UUID,
    telegram_user_id: int,
    update_id: int,
    kind: str,
    symbol: str,
    quantity: Decimal,
    unit_price_usd: Optional[Decimal],
    fee_usdt: Decimal,
    occurred_at: datetime,
    note: Optional[str] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Submete uma operação para o ledger oficial da carteira.
    Retorna (sucesso, mensagem_ou_motivo, detalhes_da_operacao).
    """
    # 1. Localiza ativo correspondente na carteira
    cur.execute(
        "SELECT id FROM portfolio_private.assets WHERE portfolio_id = %s AND UPPER(symbol) = UPPER(%s);",
        (str(portfolio_id), symbol),
    )
    asset_row = cur.fetchone()
    if not asset_row:
        return False, f"O ativo {symbol} não está cadastrado na carteira.", None
    asset_id = UUID(str(asset_row[0]))

    # Localiza USDT
    portfolio_service = PortfolioService()
    _, current_rev, usdt_id = portfolio_service.get_or_create_portfolio(cur, owner_id)

    # Lock de linha da carteira
    _, locked_rev = lock_portfolio_for_update(cur, portfolio_id)

    idempotency_key = derive_telegram_idempotency_key(update_id)

    # 2. Carrega histórico de operações para replay
    cur.execute(
        """
        SELECT o.id, o.asset_id, a.symbol, o.kind, o.occurred_at, o.order_index, 
               o.quantity, o.unit_price_usd, o.fee_usdt, o.transfer_ref, 
               o.source_label, o.destination_label, o.note
        FROM portfolio_private.operations o
        JOIN portfolio_private.assets a ON a.id = o.asset_id
        WHERE o.portfolio_id = %s AND o.deleted_at IS NULL
        ORDER BY o.occurred_at ASC, o.order_index ASC, o.id ASC;
        """,
        (str(portfolio_id),),
    )
    existing_rows = cur.fetchall()

    ops_list = []
    for r in existing_rows:
        ops_list.append(LedgerOperation(
            id=UUID(str(r[0])),
            asset_id=UUID(str(r[1])),
            asset_symbol=str(r[2]),
            kind=OperationKind(str(r[3])),
            occurred_at=r[4],
            order_index=int(r[5]),
            quantity=Decimal(str(r[6])),
            unit_price_usd=Decimal(str(r[7])) if r[7] is not None else None,
            fee_usdt=Decimal(str(r[8])),
            transfer_ref=r[9],
            source_label=r[10],
            destination_label=r[11],
            note=r[12],
        ))

    new_op_id = uuid4()
    candidate_op = LedgerOperation(
        id=new_op_id,
        asset_id=asset_id,
        asset_symbol=symbol.upper(),
        kind=OperationKind(kind),
        occurred_at=occurred_at,
        order_index=len(ops_list),
        quantity=quantity,
        unit_price_usd=unit_price_usd,
        fee_usdt=fee_usdt,
        transfer_ref=f"telegram:{update_id}",
        source_label="Telegram",
        destination_label=None,
        note=note or "Registrado via Telegram",
    )
    ops_list.append(candidate_op)

    # 3. Executa Replay Contábil
    try:
        new_projection = LedgerEngine.replay(ops_list, usdt_id)
    except InsufficientBalanceError as e:
        record_applied_update(cur, update_id, portfolio_id, "recusa_saldo_insuficiente")
        return False, f"Operação recusada: saldo insuficiente ({e})", None
    except InvalidOperationError as e:
        record_applied_update(cur, update_id, portfolio_id, "recusa_operacao_invalida")
        return False, f"Operação inválida: {e}", None
    except Exception as e:
        record_applied_update(cur, update_id, portfolio_id, "recusa_erro_contabil")
        return False, f"Não foi possível processar a operação: {e}", None

    # 4. Persiste Operação e Projeções
    new_rev = locked_rev + 1

    cur.execute(
        """
        INSERT INTO portfolio_private.operations
        (id, portfolio_id, asset_id, kind, occurred_at, order_index, quantity, unit_price_usd, fee_usdt, transfer_ref, source_label, destination_label, note)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """,
        (
            str(new_op_id), str(portfolio_id), str(asset_id), kind,
            occurred_at, candidate_op.order_index, str(quantity),
            str(unit_price_usd) if unit_price_usd else None,
            str(fee_usdt), candidate_op.transfer_ref, candidate_op.source_label,
            candidate_op.destination_label, candidate_op.note
        ),
    )

    cur.execute(
        """
        UPDATE portfolio_private.portfolio_projection
        SET cash_usdt = %s, deposits_usdt = %s, withdrawals_usdt = %s, 
            standalone_expenses_usdt = %s, realized_sales_usd = %s, revision = %s
        WHERE portfolio_id = %s;
        """,
        (
            str(new_projection.cash_usdt), str(new_projection.deposits_usdt),
            str(new_projection.withdrawals_usdt), str(new_projection.standalone_expenses_usdt),
            str(new_projection.realized_sales_usd), new_rev, str(portfolio_id)
        ),
    )

    for aid, pos in new_projection.positions.items():
        cur.execute(
            """
            INSERT INTO portfolio_private.position_projections
            (portfolio_id, asset_id, quantity, remaining_cost_usd, realized_sales_usd, revision)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (portfolio_id, asset_id) DO UPDATE
            SET quantity = EXCLUDED.quantity, remaining_cost_usd = EXCLUDED.remaining_cost_usd,
                realized_sales_usd = EXCLUDED.realized_sales_usd, revision = EXCLUDED.revision;
            """,
            (str(portfolio_id), str(aid), str(pos.quantity), str(pos.remaining_cost_usd), str(pos.realized_sales_usd), new_rev),
        )

    cur.execute(
        "UPDATE portfolio_private.portfolios SET revision = %s WHERE id = %s;",
        (new_rev, str(portfolio_id)),
    )

    # Limpa rascunho se houver
    clear_draft(cur, portfolio_id, telegram_user_id)

    # Registra atualização do Telegram
    record_applied_update(cur, update_id, portfolio_id, "lancamento_aceito")

    op_summary = {
        "id": str(new_op_id),
        "kind": kind,
        "symbol": symbol.upper(),
        "quantity": quantity,
        "unit_price_usd": unit_price_usd,
        "fee_usdt": fee_usdt,
        "occurred_at": occurred_at,
    }
    return True, "Lançamento registrado com sucesso!", op_summary

