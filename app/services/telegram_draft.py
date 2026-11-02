"""Serviço de persistência de rascunhos de operação e idempotência do Telegram.

Atende a D-04, D-05 e migração 007_telegram_agent.sql:
- No máximo um rascunho aberto por conta/carteira.
- Descarte automático ao aceitar a operação ou ao receber 'cancelar'.
- Registro de update_id já aplicado para garantir idempotência.
"""

from datetime import datetime
from decimal import Decimal
import json
from typing import Any, Dict, List, Optional
from uuid import UUID


def get_draft(cur: Any, portfolio_id: UUID, telegram_user_id: int) -> Optional[Dict[str, Any]]:
    """Recupera o rascunho ativo da conta ou None se não houver."""
    cur.execute(
        """
        SELECT kind, symbol, quantity, unit_price_usd, fee_usdt, note, missing_fields, message_time
        FROM portfolio_private.telegram_drafts
        WHERE portfolio_id = %s AND telegram_user_id = %s;
        """,
        (str(portfolio_id), int(telegram_user_id)),
    )
    row = cur.fetchone()
    if not row:
        return None

    missing = row[6]
    if isinstance(missing, str):
        try:
            missing = json.loads(missing)
        except Exception:
            missing = []

    return {
        "kind": row[0],
        "symbol": row[1],
        "quantity": Decimal(str(row[2])) if row[2] is not None else None,
        "unit_price_usd": Decimal(str(row[3])) if row[3] is not None else None,
        "fee_usdt": Decimal(str(row[4])) if row[4] is not None else Decimal("0"),
        "note": row[5],
        "missing_fields": missing or [],
        "message_time": row[7],
    }


def save_draft(cur: Any, portfolio_id: UUID, telegram_user_id: int, draft_data: Dict[str, Any]) -> None:
    """Salva ou atualiza o rascunho de lançamento da conta."""
    missing = draft_data.get("missing_fields") or []
    missing_json = json.dumps(missing)

    cur.execute(
        """
        INSERT INTO portfolio_private.telegram_drafts
        (portfolio_id, telegram_user_id, kind, symbol, quantity, unit_price_usd, fee_usdt, note, missing_fields, message_time, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (portfolio_id, telegram_user_id) DO UPDATE
        SET kind = EXCLUDED.kind,
            symbol = EXCLUDED.symbol,
            quantity = EXCLUDED.quantity,
            unit_price_usd = EXCLUDED.unit_price_usd,
            fee_usdt = EXCLUDED.fee_usdt,
            note = EXCLUDED.note,
            missing_fields = EXCLUDED.missing_fields,
            message_time = EXCLUDED.message_time,
            updated_at = now();
        """,
        (
            str(portfolio_id),
            int(telegram_user_id),
            draft_data.get("kind"),
            draft_data.get("symbol"),
            str(draft_data.get("quantity")) if draft_data.get("quantity") is not None else None,
            str(draft_data.get("unit_price_usd")) if draft_data.get("unit_price_usd") is not None else None,
            str(draft_data.get("fee_usdt")) if draft_data.get("fee_usdt") is not None else "0",
            draft_data.get("note"),
            missing_json,
            draft_data.get("message_time"),
        ),
    )


def clear_draft(cur: Any, portfolio_id: UUID, telegram_user_id: int) -> None:
    """Apaga o rascunho da conta ao finalizar ou cancelar."""
    cur.execute(
        """
        DELETE FROM portfolio_private.telegram_drafts
        WHERE portfolio_id = %s AND telegram_user_id = %s;
        """,
        (str(portfolio_id), int(telegram_user_id)),
    )


def is_update_already_applied(cur: Any, update_id: int) -> bool:
    """Verifica se a atualização do Telegram já foi aplicada anteriormente."""
    cur.execute(
        """
        SELECT result_summary FROM portfolio_private.telegram_updates
        WHERE update_id = %s;
        """,
        (int(update_id),),
    )
    return cur.fetchone() is not None


def record_applied_update(cur: Any, update_id: int, portfolio_id: Optional[UUID], result_summary: str) -> None:
    """Registra uma atualização do Telegram como aplicada."""
    cur.execute(
        """
        INSERT INTO portfolio_private.telegram_updates
        (update_id, portfolio_id, result_summary, applied_at)
        VALUES (%s, %s, %s, now())
        ON CONFLICT (update_id) DO NOTHING;
        """,
        (int(update_id), str(portfolio_id) if portfolio_id else None, str(result_summary)[:50]),
    )

