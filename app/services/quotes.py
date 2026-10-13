"""Read-only quote cache access with explicit freshness and local fixtures."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.config import get_settings


FRESHNESS_WINDOW = timedelta(minutes=30)


class QuoteStatus(str, Enum):
    AVAILABLE = "available"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


@dataclass
class QuoteResult:
    asset_id: UUID
    price_usd: Optional[Decimal]
    quoted_at: Optional[datetime]
    source: str
    status: QuoteStatus
    fetched_at: Optional[datetime] = None
    error_code: Optional[str] = None

    @property
    def is_stale(self) -> bool:
        if not self.quoted_at or self.quoted_at.tzinfo is None:
            return True
        now = datetime.now(timezone.utc)
        return (now - self.quoted_at.astimezone(timezone.utc)) > FRESHNESS_WINDOW


class QuoteReader:
    """Read a portfolio's persisted quote snapshot; never calls a provider."""

    def __init__(self, settings: Any | None = None) -> None:
        self.settings = settings or get_settings()

    @staticmethod
    def _freshness(quoted_at: datetime | None, now: datetime) -> QuoteStatus:
        if quoted_at is None or quoted_at.tzinfo is None:
            return QuoteStatus.UNAVAILABLE
        age = now - quoted_at.astimezone(timezone.utc)
        return QuoteStatus.STALE if age > FRESHNESS_WINDOW else QuoteStatus.AVAILABLE

    def _fixtures(self, asset_ids: List[UUID], now: datetime) -> Dict[UUID, QuoteResult]:
        results: Dict[UUID, QuoteResult] = {}
        stale_mode = self.settings.quote_mode == "mock_stale"
        for asset_id in asset_ids:
            quoted_at = now - timedelta(minutes=45) if stale_mode else now
            results[asset_id] = QuoteResult(
                asset_id=asset_id,
                price_usd=Decimal(str(self.settings.demo_quote_usd)),
                quoted_at=quoted_at,
                source="mock_stale" if stale_mode else "fixture_demo",
                status=QuoteStatus.STALE if stale_mode else QuoteStatus.AVAILABLE,
                fetched_at=now,
            )
        return results

    def _from_cache(
        self,
        cur: Any,
        portfolio_id: UUID,
        asset_ids: List[UUID],
        now: datetime,
    ) -> Dict[UUID, QuoteResult]:
        results: Dict[UUID, QuoteResult] = {}
        if not asset_ids:
            return results
        cur.execute(
            "SELECT a.id, a.symbol, q.price_usd, q.quoted_at, q.fetched_at, "
            "q.provider, q.last_error "
            "FROM portfolio_private.assets a "
            "LEFT JOIN portfolio_private.latest_quotes q "
            "ON q.portfolio_id=a.portfolio_id AND q.asset_id=a.id "
            "WHERE a.portfolio_id=%s AND a.id=ANY(%s);",
            (str(portfolio_id), asset_ids),
        )
        rows = {UUID(str(row[0])): row for row in cur.fetchall()}
        for asset_id in asset_ids:
            row = rows.get(asset_id)
            if row is None:
                results[asset_id] = QuoteResult(
                    asset_id, None, None, "none", QuoteStatus.UNAVAILABLE,
                    error_code="asset_unavailable",
                )
                continue
            if str(row[1]).upper() == "USDT":
                results[asset_id] = QuoteResult(
                    asset_id, Decimal("1"), now, "usd_peg", QuoteStatus.AVAILABLE,
                    fetched_at=now,
                )
                continue
            price = Decimal(str(row[2])) if row[2] is not None else None
            quoted_at, fetched_at = row[3], row[4]
            if price is None:
                results[asset_id] = QuoteResult(
                    asset_id, None, quoted_at, str(row[5] or "none"),
                    QuoteStatus.UNAVAILABLE, fetched_at, row[6] or "quote_unavailable",
                )
                continue
            status = self._freshness(quoted_at, now)
            results[asset_id] = QuoteResult(
                asset_id=asset_id,
                price_usd=price,
                quoted_at=quoted_at,
                source=str(row[5] or "unknown"),
                status=status,
                fetched_at=fetched_at,
                error_code=row[6],
            )
        return results

    def get_quotes(
        self,
        asset_ids: List[UUID],
        *,
        portfolio_id: UUID | None = None,
        cur: Any | None = None,
        now: datetime | None = None,
    ) -> Dict[UUID, QuoteResult]:
        """Return fixture values only in explicit dev/test modes, otherwise cache."""
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now deve conter timezone.")
        current = current.astimezone(timezone.utc)
        if self.settings.quote_mode in {"fixture", "mock_stale"}:
            return self._fixtures(asset_ids, current)
        if portfolio_id is not None and cur is not None:
            return self._from_cache(cur, portfolio_id, asset_ids, current)
        return {
            asset_id: QuoteResult(
                asset_id, None, None, "unconnected", QuoteStatus.UNAVAILABLE,
                error_code="quote_cache_unavailable",
            )
            for asset_id in asset_ids
        }
