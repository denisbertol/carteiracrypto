"""One-snapshot authenticated portfolio and allocation response."""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.db import get_db_connection
from app.routes.api import get_current_user_id, portfolio_service
from app.routes.allocations import allocation_service
from app.services.price_history import PriceHistoryService
from app.services.quotes import QuoteReader, QuoteStatus


router = APIRouter(prefix="/api/v1", tags=["dashboard"])
history_service = PriceHistoryService()


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


@router.get("/dashboard")
def get_dashboard(
    response: Response,
    user_id: UUID = Depends(get_current_user_id),
):
    """Read portfolio, cache, and allocation under one repeatable snapshot."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
    computed_at = datetime.now(timezone.utc)
    with get_db_connection(
        user_id, isolation_level="REPEATABLE READ", read_only=True
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM portfolio_private.portfolios WHERE owner_id=%s;",
                (str(user_id),),
            )
            row = cur.fetchone()
            if row is None:
                return {
                    "portfolio": None,
                    "allocation": None,
                    "evolution": None,
                    "quotes": [],
                    "computed_at": computed_at.isoformat(),
                    "portfolio_revision": None,
                    "freshness": "unavailable",
                    "quote_snapshot_at": None,
                }

            portfolio_id = UUID(str(row[0]))
            portfolio = portfolio_service.get_portfolio_summary(cur, portfolio_id)
            allocation = allocation_service.get_allocation_comparison(
                cur, portfolio_id, portfolio_summary=portfolio
            )
            evolution = history_service.get_evolution(
                cur, portfolio_id,
                today_value_usd=portfolio["totals"].get("balance_usd"),
                now=computed_at,
            )
            cur.execute(
                "SELECT asset_id, kind, price_usd FROM portfolio_private.price_targets "
                "WHERE portfolio_id=%s AND active=true AND kind='buy' ORDER BY asset_id;",
                (str(portfolio_id),),
            )
            buy_targets = [
                {"asset_id": row[0], "kind": row[1], "price_usd": row[2]}
                for row in cur.fetchall()
            ]
            quotes = [
                {
                    "asset_id": position["asset_id"],
                    "symbol": position["symbol"],
                    "price_usd": position["quote_usd"],
                    "source": position["quote_source"],
                    "quoted_at": position["quote_at"],
                    "fetched_at": position.get("quote_fetched_at"),
                    "freshness": position.get("quote_freshness", position["quote_status"]),
                    "error_code": position.get("quote_error"),
                }
                for position in portfolio["positions"]
            ]
            cur.execute(
                "SELECT a.id, a.symbol, q.price_usd, q.quoted_at, q.fetched_at, q.provider, q.last_error "
                "FROM portfolio_private.assets a "
                "LEFT JOIN portfolio_private.latest_quotes q "
                "ON q.portfolio_id=a.portfolio_id AND q.asset_id=a.id "
                "WHERE a.portfolio_id=%s AND a.active=true AND a.symbol <> 'USDT';",
                (str(portfolio_id),),
            )
            known_assets = {quote["asset_id"] for quote in quotes}
            for asset_id, symbol, price, quoted_at, fetched_at, provider, error in cur.fetchall():
                if asset_id in known_assets:
                    continue
                freshness = QuoteReader._freshness(quoted_at, computed_at)
                quotes.append({
                    "asset_id": asset_id,
                    "symbol": symbol,
                    "price_usd": price,
                    "source": provider,
                    "quoted_at": quoted_at,
                    "fetched_at": fetched_at,
                    "freshness": freshness.value if price is not None else QuoteStatus.UNAVAILABLE.value,
                    "error_code": error,
                })
            cur.execute(
                "SELECT hidden_columns FROM portfolio_private.portfolios WHERE id=%s;",
                (str(portfolio_id),),
            )
            preference = cur.fetchone()
            raw_columns = preference[0] if preference else []
            hidden_columns = raw_columns if isinstance(raw_columns, list) else []

    snapshot_at = portfolio.get("quote_snapshot_at")
    return {
        "portfolio": _json_value(portfolio),
        "allocation": _json_value(allocation),
        "evolution": _json_value(evolution),
        "quotes": _json_value(quotes),
        "buy_targets": _json_value(buy_targets),
        "hidden_columns": _json_value(hidden_columns),
        "computed_at": computed_at.isoformat(),
        "portfolio_revision": portfolio["revision"],
        "freshness": portfolio.get("quote_freshness", "incomplete"),
        "quote_snapshot_at": _json_value(snapshot_at),
    }
