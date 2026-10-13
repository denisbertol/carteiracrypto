"""Daily price history, one-time CoinGecko backfill and portfolio evolution."""

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import UUID

from app.config import get_settings, provider_configured
from app.db import get_db_connection
from app.domain.ledger import LedgerEngine, LedgerOperation, OperationKind
from app.services.coingecko import MAX_HISTORY_DAYS, CoinGeckoClient
from app.services.provider_budget import ProviderBudgetService


PROVIDER = "coingecko"
BACKFILL_LEASE = timedelta(minutes=2)
BACKFILL_RETRY_AFTER = timedelta(hours=1)
MAX_BACKFILL_ASSETS_PER_RUN = 3
MAX_EVOLUTION_DAYS = 1830
PRICE_CARRY_FORWARD_DAYS = 7
CENT = Decimal("0.01")


def price_day(stamp: datetime) -> date:
    """UTC day a quote closes. CoinGecko midnight points close the previous day."""
    if stamp.tzinfo is None:
        raise ValueError("stamp deve conter timezone.")
    return (stamp.astimezone(timezone.utc) - timedelta(microseconds=1)).date()


def record_live_price(
    cur: Any, portfolio_id: UUID, asset_id: Any, price_usd: Decimal, quoted_at: datetime, now: datetime
) -> None:
    cur.execute(
        "INSERT INTO portfolio_private.asset_daily_prices "
        "(portfolio_id, asset_id, day, price_usd, quoted_at, source, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, 'live', %s) "
        "ON CONFLICT (portfolio_id, asset_id, day) DO UPDATE SET "
        "price_usd=EXCLUDED.price_usd, quoted_at=EXCLUDED.quoted_at, source=EXCLUDED.source, "
        "updated_at=EXCLUDED.updated_at "
        "WHERE EXCLUDED.quoted_at >= portfolio_private.asset_daily_prices.quoted_at;",
        (str(portfolio_id), str(asset_id), price_day(quoted_at), str(price_usd), quoted_at, now),
    )


@dataclass(frozen=True)
class EvolutionPoint:
    day: date
    invested_usd: Decimal
    value_usd: Optional[Decimal]


def _sort_key(op: LedgerOperation):
    return (op.occurred_at, op.order_index, str(op.id))


def _op_day(op: LedgerOperation) -> date:
    return op.occurred_at.astimezone(timezone.utc).date()


def build_evolution(
    operations: List[LedgerOperation],
    usdt_asset_id: UUID,
    prices: Dict[UUID, List[Tuple[date, Decimal]]],
    today: date,
    *,
    today_value_usd: Optional[Decimal] = None,
    max_days: int = MAX_EVOLUTION_DAYS,
) -> List[EvolutionPoint]:
    """End-of-day net contributions and market value, replaying the ledger per day.

    A held asset without a price in the last PRICE_CARRY_FORWARD_DAYS days makes
    that day's value unknown instead of silently counting it as zero.
    """
    if not operations:
        return []
    ordered = sorted(operations, key=_sort_key)
    first_day = _op_day(ordered[0])
    start = max(first_day, today - timedelta(days=max_days - 1))
    if start > today:
        return []

    price_days = {asset_id: [item[0] for item in series] for asset_id, series in prices.items()}

    def price_on(asset_id: UUID, day: date) -> Optional[Decimal]:
        days = price_days.get(asset_id)
        if not days:
            return None
        index = bisect_right(days, day) - 1
        if index < 0 or (day - days[index]).days > PRICE_CARRY_FORWARD_DAYS:
            return None
        return prices[asset_id][index][1]

    # Projection after each operation day, keyed by the last op index of that day.
    boundaries: List[Tuple[date, int]] = []
    for index, op in enumerate(ordered):
        day = _op_day(op)
        if boundaries and boundaries[-1][0] == day:
            boundaries[-1] = (day, index + 1)
        else:
            boundaries.append((day, index + 1))

    points: List[EvolutionPoint] = []
    projection = None
    boundary_index = 0
    current = start
    while current <= today:
        advanced = False
        while boundary_index < len(boundaries) and boundaries[boundary_index][0] <= current:
            boundary_index += 1
            advanced = True
        if advanced or projection is None:
            prefix_end = boundaries[boundary_index - 1][1] if boundary_index else 0
            projection = LedgerEngine.replay(ordered[:prefix_end], usdt_asset_id)

        invested = projection.deposits_usdt - projection.withdrawals_usdt
        value: Optional[Decimal] = projection.cash_usdt
        for asset_id, position in projection.positions.items():
            if asset_id == usdt_asset_id or position.quantity <= 0:
                continue
            price = price_on(asset_id, current)
            if price is None:
                value = None
                break
            value += position.quantity * price
        if current == today and today_value_usd is not None:
            value = today_value_usd
        points.append(EvolutionPoint(
            day=current,
            invested_usd=invested.quantize(CENT),
            value_usd=value.quantize(CENT) if value is not None else None,
        ))
        current += timedelta(days=1)
    return points


def modified_dietz(
    start_value: Optional[Decimal], start_invested: Decimal, points: List[EvolutionPoint]
) -> Optional[Decimal]:
    """Money-weighted return in percent, assuming flows at the start of their day."""
    if start_value is None or not points or points[-1].value_usd is None:
        return None
    total_days = len(points)
    net_flow = Decimal("0")
    weighted_flow = Decimal("0")
    previous = start_invested
    for offset, point in enumerate(points):
        flow = point.invested_usd - previous
        previous = point.invested_usd
        if flow:
            net_flow += flow
            weighted_flow += flow * Decimal(total_days - offset) / Decimal(total_days)
    denominator = start_value + weighted_flow
    if denominator <= 0:
        return None
    gain = points[-1].value_usd - start_value - net_flow
    return (gain / denominator * Decimal("100")).quantize(CENT)


def period_returns(points: List[EvolutionPoint], first_operation_day: Optional[date]) -> Dict[str, Optional[Decimal]]:
    if not points or first_operation_day is None:
        return {"total": None, "last_12m": None}
    if points[0].day == first_operation_day:
        total = modified_dietz(Decimal("0"), Decimal("0"), points)
    else:
        total = modified_dietz(points[0].value_usd, points[0].invested_usd, points[1:])
    year_start = points[-1].day - timedelta(days=365)
    if first_operation_day > year_start:
        last_12m = total
    else:
        start_index = next((i for i, point in enumerate(points) if point.day >= year_start), None)
        if start_index is None or start_index >= len(points) - 1:
            last_12m = None
        else:
            anchor = points[start_index]
            last_12m = modified_dietz(anchor.value_usd, anchor.invested_usd, points[start_index + 1:])
    return {"total": total, "last_12m": last_12m}


_PENDING_FILTER = (
    "FROM portfolio_private.asset_price_mappings m "
    "JOIN portfolio_private.assets a ON a.id=m.asset_id AND a.portfolio_id=m.portfolio_id "
    "LEFT JOIN portfolio_private.price_history_backfills b "
    "ON b.portfolio_id=m.portfolio_id AND b.asset_id=m.asset_id "
    "WHERE m.portfolio_id=%s AND m.provider=%s AND m.status='valid' AND a.symbol <> 'USDT' "
    "AND EXISTS (SELECT 1 FROM portfolio_private.operations o WHERE o.portfolio_id=m.portfolio_id "
    "AND o.asset_id=m.asset_id AND o.deleted_at IS NULL) "
    "AND (b.asset_id IS NULL OR b.provider_coin_id <> m.provider_coin_id "
    "OR (b.status='failed' AND b.attempted_at <= %s) "
    "OR (b.status='running' AND b.lease_until <= %s))"
)


class PriceHistoryService:
    def __init__(self, budget_service: ProviderBudgetService | None = None) -> None:
        self.budgets = budget_service or ProviderBudgetService()

    @staticmethod
    def _load_operations(cur: Any, portfolio_id: UUID) -> List[LedgerOperation]:
        cur.execute(
            "SELECT o.id, o.asset_id, a.symbol, o.kind, o.occurred_at, o.order_index, o.quantity, "
            "o.unit_price_usd, o.fee_usdt, o.transfer_ref "
            "FROM portfolio_private.operations o "
            "JOIN portfolio_private.assets a ON a.id=o.asset_id "
            "WHERE o.portfolio_id=%s AND o.deleted_at IS NULL "
            "ORDER BY o.occurred_at, o.order_index, o.id;",
            (str(portfolio_id),),
        )
        return [
            LedgerOperation(
                id=UUID(str(row[0])), asset_id=UUID(str(row[1])), asset_symbol=str(row[2]),
                kind=OperationKind(str(row[3])), occurred_at=row[4], order_index=int(row[5]),
                quantity=Decimal(str(row[6])),
                unit_price_usd=Decimal(str(row[7])) if row[7] is not None else None,
                fee_usdt=Decimal(str(row[8])), transfer_ref=row[9],
            )
            for row in cur.fetchall()
        ]

    @staticmethod
    def _usdt_id(cur: Any, portfolio_id: UUID) -> Optional[UUID]:
        cur.execute(
            "SELECT id FROM portfolio_private.assets WHERE portfolio_id=%s AND symbol='USDT';",
            (str(portfolio_id),),
        )
        row = cur.fetchone()
        return UUID(str(row[0])) if row else None

    @staticmethod
    def count_pending(cur: Any, portfolio_id: UUID, now: datetime) -> int:
        cur.execute(
            "SELECT COUNT(*) " + _PENDING_FILTER + ";",
            (str(portfolio_id), PROVIDER, now - BACKFILL_RETRY_AFTER, now),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def get_evolution(
        self,
        cur: Any,
        portfolio_id: UUID,
        *,
        today_value_usd: Optional[Decimal] = None,
        now: datetime | None = None,
    ) -> Dict[str, Any]:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        today = current.date()
        operations = self._load_operations(cur, portfolio_id)
        usdt_id = self._usdt_id(cur, portfolio_id)
        first_day = _op_day(min(operations, key=_sort_key)) if operations else None

        prices: Dict[UUID, List[Tuple[date, Decimal]]] = {}
        if operations:
            since = max(first_day, today - timedelta(days=MAX_EVOLUTION_DAYS)) - timedelta(days=PRICE_CARRY_FORWARD_DAYS)
            cur.execute(
                "SELECT asset_id, day, price_usd FROM portfolio_private.asset_daily_prices "
                "WHERE portfolio_id=%s AND day >= %s ORDER BY asset_id, day;",
                (str(portfolio_id), since),
            )
            for asset_id, day, price in cur.fetchall():
                prices.setdefault(UUID(str(asset_id)), []).append((day, Decimal(str(price))))

        points = (
            build_evolution(operations, usdt_id, prices, today, today_value_usd=today_value_usd)
            if operations and usdt_id is not None else []
        )
        returns = period_returns(points, first_day)
        settings = get_settings()
        return {
            "points": [
                {"day": p.day.isoformat(), "invested_usd": p.invested_usd, "value_usd": p.value_usd}
                for p in points
            ],
            "first_operation_day": first_day.isoformat() if first_day else None,
            "invested_usd": points[-1].invested_usd if points else Decimal("0.00"),
            "return_total_percent": returns["total"],
            "return_12m_percent": returns["last_12m"],
            "backfill": {
                "pending_assets": self.count_pending(cur, portfolio_id, current),
                "provider_configured": provider_configured(settings, current),
            },
        }

    def run_backfill(
        self,
        owner_id: UUID,
        *,
        connection_factory: Callable = get_db_connection,
        client_factory: Callable = CoinGeckoClient,
        now: Callable[[], datetime] | None = None,
    ) -> Dict[str, Any]:
        """Reserve quota and lease up to N assets, call HTTP outside the transaction, then publish."""
        clock = now or (lambda: datetime.now(timezone.utc))
        started = clock().astimezone(timezone.utc)
        settings = get_settings()
        if not provider_configured(settings, started):
            return {"state": "blocked", "reason": "config_required"}
        api_key = settings.coingecko_demo_api_key.get_secret_value()

        with connection_factory(owner_id) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM portfolio_private.portfolios WHERE owner_id=%s;", (str(owner_id),)
                )
                row = cur.fetchone()
                if row is None:
                    return {"state": "completed", "imported_assets": 0, "failed_assets": 0, "pending_assets": 0}
                portfolio_id = UUID(str(row[0]))
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0));",
                    (f"price-history:{portfolio_id}",),
                )
                cur.execute(
                    "SELECT m.asset_id, m.provider_coin_id " + _PENDING_FILTER + " ORDER BY m.asset_id LIMIT %s;",
                    (str(portfolio_id), PROVIDER, started - BACKFILL_RETRY_AFTER, started,
                     MAX_BACKFILL_ASSETS_PER_RUN),
                )
                candidates = [(str(r[0]), str(r[1])) for r in cur.fetchall()]
                if not candidates:
                    conn.commit()
                    return {"state": "completed", "imported_assets": 0, "failed_assets": 0, "pending_assets": 0}
                cur.execute(
                    "SELECT MIN(occurred_at) FROM portfolio_private.operations "
                    "WHERE portfolio_id=%s AND deleted_at IS NULL;",
                    (str(portfolio_id),),
                )
                first_at = cur.fetchone()[0]
                span = (started.date() - first_at.astimezone(timezone.utc).date()).days + 2
                days = max(1, min(MAX_HISTORY_DAYS, span))

                decision = self.budgets.reserve(
                    cur,
                    provider=PROVIDER,
                    api_key=api_key,
                    window_start=settings.coingecko_window_start,
                    window_end=settings.coingecko_window_end,
                    configured_limit=settings.coingecko_call_limit,
                    request_count=len(candidates),
                    now=started,
                )
                if not decision.allowed:
                    conn.commit()
                    return {
                        "state": "blocked",
                        "reason": decision.reason,
                        "next_retry_at": decision.next_retry_at.isoformat() if decision.next_retry_at else None,
                    }
                for asset_id, coin_id in candidates:
                    cur.execute(
                        "INSERT INTO portfolio_private.price_history_backfills "
                        "(portfolio_id, asset_id, provider_coin_id, status, lease_until, attempted_at, error_code) "
                        "VALUES (%s, %s, %s, 'running', %s, %s, NULL) "
                        "ON CONFLICT (portfolio_id, asset_id) DO UPDATE SET "
                        "provider_coin_id=EXCLUDED.provider_coin_id, status='running', "
                        "lease_until=EXCLUDED.lease_until, attempted_at=EXCLUDED.attempted_at, error_code=NULL;",
                        (str(portfolio_id), asset_id, coin_id, started + BACKFILL_LEASE, started),
                    )
                conn.commit()

        results: List[Tuple[str, str, Any]] = []
        retry_after: Optional[int] = None
        with client_factory(api_key) as client:
            for asset_id, coin_id in candidates:
                if retry_after is not None:
                    results.append((asset_id, coin_id, "provider_rate_limited"))
                    continue
                batch = client.fetch_daily_history(coin_id, days)
                if batch.error_code == "provider_rate_limited":
                    retry_after = batch.retry_after_seconds or 60
                results.append((asset_id, coin_id, batch))

        finished = clock().astimezone(timezone.utc)
        imported = failed = 0
        with connection_factory(owner_id) as conn:
            with conn.cursor() as cur:
                if retry_after is not None:
                    self.budgets.set_cooldown(
                        cur, provider=PROVIDER, api_key=api_key,
                        cooldown_until=finished + timedelta(seconds=retry_after), now=finished,
                    )
                for asset_id, coin_id, outcome in results:
                    error_code = outcome if isinstance(outcome, str) else outcome.error_code
                    if error_code is None:
                        days_written = set()
                        for stamp, price in outcome.points:
                            day = price_day(stamp)
                            days_written.add(day)
                            cur.execute(
                                "INSERT INTO portfolio_private.asset_daily_prices "
                                "(portfolio_id, asset_id, day, price_usd, quoted_at, source, updated_at) "
                                "VALUES (%s, %s, %s, %s, %s, 'backfill', %s) "
                                "ON CONFLICT (portfolio_id, asset_id, day) DO UPDATE SET "
                                "price_usd=EXCLUDED.price_usd, quoted_at=EXCLUDED.quoted_at, "
                                "source=EXCLUDED.source, updated_at=EXCLUDED.updated_at "
                                "WHERE EXCLUDED.quoted_at >= portfolio_private.asset_daily_prices.quoted_at;",
                                (str(portfolio_id), asset_id, day, str(price), stamp, finished),
                            )
                        cur.execute(
                            "UPDATE portfolio_private.price_history_backfills SET status='completed', "
                            "lease_until=NULL, first_day=%s, last_day=%s, point_count=%s, error_code=NULL "
                            "WHERE portfolio_id=%s AND asset_id=%s AND provider_coin_id=%s AND status='running';",
                            (min(days_written), max(days_written), len(days_written),
                             str(portfolio_id), asset_id, coin_id),
                        )
                        imported += 1
                    else:
                        cur.execute(
                            "UPDATE portfolio_private.price_history_backfills SET status='failed', "
                            "lease_until=NULL, error_code=%s "
                            "WHERE portfolio_id=%s AND asset_id=%s AND provider_coin_id=%s AND status='running';",
                            (error_code[:80], str(portfolio_id), asset_id, coin_id),
                        )
                        failed += 1
                pending = self.count_pending(cur, portfolio_id, finished)
                conn.commit()
        return {
            "state": "completed",
            "imported_assets": imported,
            "failed_assets": failed,
            "pending_assets": pending,
        }
