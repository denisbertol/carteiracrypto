"""Gerenciamento de acesso e vínculo da conta do Telegram com a carteira.

Atende a D-07, RF-08 e aula do Prof. Sandeco:
- Whitelist de usuários autorizados (TELEGRAM_ALLOWED_USERS).
- Vínculo exclusivo da primeira conta Telegram à carteira de Denis.
- Bloqueio e recusa para qualquer conta diferente sem expor dados financeiros.
"""

from enum import Enum
from typing import Any, Optional, Set
from uuid import UUID


class AccessCheckResult(str, Enum):
    AUTHORIZED_LINKED = "authorized_linked"
    AUTHORIZED_EXISTING = "authorized_existing"
    REJECTED_NOT_WHITELISTED = "rejected_not_whitelisted"
    REJECTED_DIFFERENT_ACCOUNT = "rejected_different_account"


class TelegramAccessManager:
    def __init__(self, allowed_users_raw: Optional[str] = None):
        self.allowed_users: Set[int] = set()
        if allowed_users_raw:
            for item in allowed_users_raw.split(","):
                cleaned = item.strip()
                if cleaned.isdigit():
                    self.allowed_users.add(int(cleaned))

    def verify_or_link_account(
        self,
        cur: Any,
        portfolio_id: UUID,
        telegram_user_id: int,
    ) -> AccessCheckResult:
        """Verifica se o remetente está na whitelist e se é o dono vinculado da carteira."""
        # 1. Checa Whitelist se configurada
        if self.allowed_users and telegram_user_id not in self.allowed_users:
            return AccessCheckResult.REJECTED_NOT_WHITELISTED

        # 2. Busca conta já vinculada para esta carteira
        cur.execute(
            """
            SELECT telegram_user_id FROM portfolio_private.telegram_accounts
            WHERE portfolio_id = %s;
            """,
            (str(portfolio_id),),
        )
        row = cur.fetchone()

        if row is None:
            # Primeira conta se vinculando
            cur.execute(
                """
                INSERT INTO portfolio_private.telegram_accounts
                (portfolio_id, telegram_user_id, linked_at)
                VALUES (%s, %s, now());
                """,
                (str(portfolio_id), int(telegram_user_id)),
            )
            return AccessCheckResult.AUTHORIZED_LINKED

        linked_user_id = int(row[0])
        if linked_user_id == telegram_user_id:
            return AccessCheckResult.AUTHORIZED_EXISTING

        return AccessCheckResult.REJECTED_DIFFERENT_ACCOUNT

