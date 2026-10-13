"""Background reconciliation for cycles whose durable lease has expired."""

from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from app.db import get_db_connection
from app.services.monitoring import MonitoringCycleService
from app.services.price_targets import PriceTargetService


def reconcile_expired_cycles(
    user_id: UUID,
    *,
    now: datetime | None = None,
    connection_factory: Callable = get_db_connection,
) -> dict[str, Any]:
    """Fail expired cycles without provider calls or retrospective evaluations."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now deve conter timezone.")
    current = current.astimezone(timezone.utc)
    reconciled = 0

    with connection_factory(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_try_advisory_xact_lock(" 
                "hashtextextended('monitoring_recovery', 0));"
            )
            lock_row = cur.fetchone()
            if not lock_row or not lock_row[0]:
                conn.commit()
                return {"state": "skipped", "reason": "recovery_in_progress", "reconciled": 0}

            cur.execute(
                "SELECT portfolio_id FROM portfolio_private.monitoring_state "
                "WHERE current_cycle_id IS NOT NULL AND lease_until <= %s "
                "ORDER BY portfolio_id;",
                (current,),
            )
            portfolio_ids = [UUID(str(row[0])) for row in cur.fetchall()]
            for portfolio_id in portfolio_ids:
                # Match reservation, finalization, and target mutations' lock order.
                PriceTargetService._lock_portfolio(cur, portfolio_id)
                if MonitoringCycleService.reconcile_expired_cycle(
                    cur, portfolio_id, now=current
                ):
                    reconciled += 1
        conn.commit()

    return {"state": "completed", "reconciled": reconciled}
