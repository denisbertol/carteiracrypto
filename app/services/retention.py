"""Bounded cleanup for expired monitoring history."""

from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID

from app.db import get_db_connection


RETENTION_PERIOD = timedelta(days=30)
MAX_DELETE_BATCH = 1000
RETENTION_DELETE_ORDER = (
    "price_notifications",
    "price_evaluations",
    "monitoring_cycles",
    "monitoring_changes",
)


def is_expired(created_at: datetime, now: datetime) -> bool:
    if created_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("timestamps de retenção devem conter timezone.")
    cutoff = now.astimezone(timezone.utc) - RETENTION_PERIOD
    return created_at.astimezone(timezone.utc) <= cutoff


_DELETE_BATCH_SQL = {
    "price_notifications": (
        "WITH doomed AS ("
        "SELECT id FROM portfolio_private.price_notifications "
        "WHERE created_at <= %s ORDER BY created_at, id LIMIT %s) "
        "DELETE FROM portfolio_private.price_notifications n "
        "USING doomed d WHERE n.id=d.id;"
    ),
    "price_evaluations": (
        "WITH doomed AS ("
        "SELECT e.id FROM portfolio_private.price_evaluations e "
        "WHERE e.created_at <= %s AND NOT EXISTS ("
        "SELECT 1 FROM portfolio_private.price_notifications n "
        "WHERE n.portfolio_id=e.portfolio_id AND n.evaluation_id=e.id AND n.created_at > %s) "
        "ORDER BY e.created_at, e.id LIMIT %s) "
        "DELETE FROM portfolio_private.price_evaluations e "
        "USING doomed d WHERE e.id=d.id;"
    ),
    "monitoring_cycles": (
        "WITH doomed AS ("
        "SELECT c.id FROM portfolio_private.monitoring_cycles c "
        "WHERE c.status IN ('completed','partial','failed') AND c.completed_at <= %s "
        "AND NOT EXISTS (SELECT 1 FROM portfolio_private.monitoring_state s "
        "WHERE s.portfolio_id=c.portfolio_id AND s.current_cycle_id=c.id) "
        "AND NOT EXISTS (SELECT 1 FROM portfolio_private.latest_quotes q "
        "WHERE q.portfolio_id=c.portfolio_id AND q.source_cycle_id=c.id) "
        "AND NOT EXISTS (SELECT 1 FROM portfolio_private.price_evaluations e "
        "WHERE e.portfolio_id=c.portfolio_id AND e.cycle_id=c.id) "
        "ORDER BY c.completed_at, c.id LIMIT %s) "
        "DELETE FROM portfolio_private.monitoring_cycles c "
        "USING doomed d WHERE c.id=d.id;"
    ),
    "monitoring_changes": (
        "WITH doomed AS ("
        "SELECT id FROM portfolio_private.monitoring_changes "
        "WHERE created_at <= %s ORDER BY created_at, id LIMIT %s) "
        "DELETE FROM portfolio_private.monitoring_changes c "
        "USING doomed d WHERE c.id=d.id;"
    ),
}


def _batch_params(table: str, cutoff: datetime, batch_size: int) -> tuple[Any, ...]:
    if table == "price_evaluations":
        return cutoff, cutoff, batch_size
    if table == "monitoring_cycles":
        return cutoff, batch_size
    return cutoff, batch_size


def cleanup_retained_history(
    user_id: UUID,
    *,
    now: datetime | None = None,
    batch_size: int = MAX_DELETE_BATCH,
    connection_factory: Callable = get_db_connection,
) -> dict[str, Any]:
    """Purge expired rows in bounded batches while protecting live references.

    The transaction-scoped advisory lock makes concurrent startup/hourly runs
    collapse to one cleanup. History endpoints independently apply the same
    30-day cutoff, so physical cleanup progress never exposes expired rows.
    """
    if not 1 <= batch_size <= MAX_DELETE_BATCH:
        raise ValueError(f"batch_size deve ficar entre 1 e {MAX_DELETE_BATCH}.")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now deve conter timezone.")
    current = current.astimezone(timezone.utc)
    cutoff = current - RETENTION_PERIOD
    deleted = {table: 0 for table in RETENTION_DELETE_ORDER}

    with connection_factory(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_try_advisory_xact_lock(" 
                "hashtextextended('monitoring_retention_cleanup', 0));"
            )
            lock_row = cur.fetchone()
            if not lock_row or not lock_row[0]:
                conn.commit()
                return {"state": "skipped", "reason": "cleanup_in_progress", "deleted": deleted}

            for table in RETENTION_DELETE_ORDER:
                while True:
                    cur.execute(
                        _DELETE_BATCH_SQL[table],
                        _batch_params(table, cutoff, batch_size),
                    )
                    removed = max(0, int(cur.rowcount))
                    deleted[table] += removed
                    if removed < batch_size:
                        break

            cur.execute(
                "UPDATE portfolio_private.monitoring_state SET last_cleanup_at=%s "
                "WHERE portfolio_id IN ("
                "SELECT id FROM portfolio_private.portfolios "
                "WHERE owner_id=%s);",
                (current, str(user_id)),
            )
        conn.commit()

    return {"state": "completed", "cutoff": cutoff.isoformat(), "deleted": deleted}
