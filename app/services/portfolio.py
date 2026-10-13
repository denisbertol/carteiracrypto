"""Serviço central de gerenciamento da carteira, transações atômicas e projeções."""

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from app.domain.ledger import (
    LedgerEngine,
    LedgerOperation,
    OperationKind,
    InsufficientBalanceError,
    InvalidOperationError,
)
from app.services.quotes import QuoteReader, QuoteStatus


class RevisionConflictError(Exception):
    """Conflito de versão otimista da carteira."""
    pass


class IdempotencyConflictError(Exception):
    """Chave de idempotência reutilizada com payload diferente."""
    pass


class PortfolioNotFoundError(Exception):
    """Carteira não encontrada."""
    pass


def compute_request_hash(method: str, path: str, body: Dict[str, Any], revision: int) -> str:
    """Calcula hash SHA-256 canônico da intenção de mutação."""
    canonical_body = json.dumps(body, sort_keys=True, ensure_ascii=False)
    raw = f"{method.upper()}:{path}:{revision}:{canonical_body}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class PortfolioService:
    def __init__(self, quote_reader: Optional[QuoteReader] = None) -> None:
        self.quotes = quote_reader or QuoteReader()

    def get_or_create_portfolio(self, cur: Any, owner_id: UUID) -> Tuple[UUID, int, UUID]:
        """
        Retorna (portfolio_id, revision, usdt_asset_id).
        Cria a carteira e o ativo USDT se ainda não existirem.
        """
        cur.execute(
            "SELECT id, revision FROM portfolio_private.portfolios WHERE owner_id = %s;",
            (str(owner_id),),
        )
        row = cur.fetchone()
        if row:
            portfolio_id = UUID(str(row[0]))
            revision = int(row[1])
        else:
            portfolio_id = uuid4()
            revision = 1
            cur.execute(
                """
                INSERT INTO portfolio_private.portfolios (id, owner_id, revision)
                VALUES (%s, %s, %s);
                """,
                (str(portfolio_id), str(owner_id), revision),
            )
            # Inicializa projeção consolidada
            cur.execute(
                """
                INSERT INTO portfolio_private.portfolio_projection 
                (portfolio_id, revision) VALUES (%s, %s);
                """,
                (str(portfolio_id), revision),
            )

        # Garante a existência do ativo USDT na carteira
        cur.execute(
            """
            SELECT id FROM portfolio_private.assets 
            WHERE portfolio_id = %s AND symbol = 'USDT';
            """,
            (str(portfolio_id),),
        )
        usdt_row = cur.fetchone()
        if usdt_row:
            usdt_id = UUID(str(usdt_row[0]))
        else:
            usdt_id = uuid4()
            cur.execute(
                """
                INSERT INTO portfolio_private.assets (id, portfolio_id, external_id, symbol, name)
                VALUES (%s, %s, 'tether', 'USDT', 'Tether USD');
                """,
                (str(usdt_id), str(portfolio_id)),
            )

        return portfolio_id, revision, usdt_id

    def get_portfolio_summary(self, cur: Any, portfolio_id: UUID) -> Dict[str, Any]:
        """Lê projeções persistidas e enriquece com cotações a mercado."""
        # Lê revisão da carteira
        cur.execute(
            "SELECT revision FROM portfolio_private.portfolios WHERE id = %s;",
            (str(portfolio_id),),
        )
        row = cur.fetchone()
        if not row:
            raise PortfolioNotFoundError("Carteira não encontrada.")
        revision = int(row[0])

        # Lê projeção consolidada
        cur.execute(
            """
            SELECT cash_usdt, deposits_usdt, withdrawals_usdt, standalone_expenses_usdt, realized_sales_usd
            FROM portfolio_private.portfolio_projection
            WHERE portfolio_id = %s;
            """,
            (str(portfolio_id),),
        )
        proj_row = cur.fetchone()
        if proj_row:
            cash = Decimal(str(proj_row[0]))
            deposits = Decimal(str(proj_row[1]))
            withdrawals = Decimal(str(proj_row[2]))
            expenses = Decimal(str(proj_row[3]))
            realized_sales = Decimal(str(proj_row[4]))
        else:
            cash = deposits = withdrawals = expenses = realized_sales = Decimal("0")

        # Lê posições por ativo
        cur.execute(
            """
            SELECT p.asset_id, a.symbol, a.name, p.quantity, p.remaining_cost_usd, p.realized_sales_usd
            FROM portfolio_private.position_projections p
            JOIN portfolio_private.assets a ON a.id = p.asset_id
            WHERE p.portfolio_id = %s AND a.symbol != 'USDT' AND p.quantity > 0;
            """,
            (str(portfolio_id),),
        )
        pos_rows = cur.fetchall()

        asset_ids = [UUID(str(r[0])) for r in pos_rows]
        quotes_map = self.quotes.get_quotes(
            asset_ids, portfolio_id=portfolio_id, cur=cur
        )

        positions_summary = []
        crypto_cost_total = Decimal("0")
        crypto_value_total = Decimal("0")
        is_complete = True
        is_updated = True
        quote_fetch_times = []

        for r in pos_rows:
            aid = UUID(str(r[0]))
            symbol = str(r[1])
            name = str(r[2])
            qty = Decimal(str(r[3]))
            cost = Decimal(str(r[4]))
            sales = Decimal(str(r[5]))
            avg_price = (cost / qty) if qty > 0 else None

            quote = quotes_map.get(aid)
            current_val: Optional[Decimal] = None
            unrealized: Optional[Decimal] = None

            if quote and quote.status != QuoteStatus.UNAVAILABLE and quote.price_usd is not None:
                current_val = qty * quote.price_usd
                unrealized = current_val - cost
                crypto_value_total += current_val
                if quote.status != QuoteStatus.AVAILABLE:
                    is_updated = False
            else:
                is_complete = False
                is_updated = False

            if quote and quote.fetched_at is not None:
                quote_fetch_times.append(quote.fetched_at)

            crypto_cost_total += cost

            positions_summary.append({
                "asset_id": aid,
                "symbol": symbol,
                "name": name,
                "quantity": qty,
                "remaining_cost_usd": cost,
                "average_price_usd": avg_price,
                "realized_sales_usd": sales,
                "quote_usd": quote.price_usd if quote else None,
                "quote_at": quote.quoted_at if quote else None,
                "quote_fetched_at": quote.fetched_at if quote else None,
                "quote_source": quote.source if quote else "none",
                "quote_status": quote.status.value if quote else "unavailable",
                "quote_freshness": quote.status.value if quote else "unavailable",
                "quote_error": quote.error_code if quote else "quote_unavailable",
                "current_value_usd": current_val,
                "unrealized_usd": unrealized,
            })

        balance_usd = (cash + crypto_value_total) if is_complete else None
        cash_percent = (cash / balance_usd * Decimal("100")) if (balance_usd and balance_usd > 0) else None

        totals = {
            "invested_usd": deposits - withdrawals,
            "cash_usdt": cash,
            "crypto_cost_usd": crypto_cost_total,
            "crypto_value_usd": crypto_value_total if is_complete else None,
            "balance_usd": balance_usd,
            "cash_percent": cash_percent,
            "realized_sales_usd": realized_sales,
            "expenses_usd": expenses,
            "realized_net_usd": realized_sales - expenses,
            "unrealized_usd": (crypto_value_total - crypto_cost_total) if is_complete else None,
            "complete": is_complete,
            "updated": is_updated,
            "freshness": "fresh" if is_updated else ("stale" if is_complete else "incomplete"),
            "quote_snapshot_at": max(quote_fetch_times) if quote_fetch_times else None,
        }

        return {
            "revision": revision,
            "positions": positions_summary,
            "totals": totals,
            "quote_status": "complete" if is_complete else "incomplete",
            "quotes_updated": is_updated,
            "quote_freshness": totals["freshness"],
            "quote_snapshot_at": totals["quote_snapshot_at"],
        }
