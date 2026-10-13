"""Persistence helpers for in-app price notifications."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.services.price_targets import PriceTargetService


HISTORY_RETENTION = timedelta(days=30)
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else None


def _notification_body(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": str(row[0]),
        "evaluation_id": str(row[1]),
        "created_at": _iso(row[2]),
        "displayed_at": _iso(row[3]),
        "read_at": _iso(row[4]),
        "cycle_id": str(row[5]),
        "target": {
            "id": str(row[6]),
            "version": int(row[7]),
            "price_usd": str(row[8]),
            "kind": row[9],
            "orientation": row[10],
            "proximity_percent": str(row[11]),
        },
        "quote": {
            "price_usd": str(row[12]) if row[12] is not None else None,
            "quoted_at": _iso(row[13]),
            "evaluated_at": _iso(row[14]),
            "distance_percent": str(row[15]) if row[15] is not None else None,
        },
        "result": row[16],
        "error_code": row[17],
        "asset": {
            "id": str(row[18]),
            "external_id": row[19],
            "symbol": row[20],
            "name": row[21],
        },
    }


class NotificationService:
    """Create one notification per eligible evaluation and serve retained history."""

    @staticmethod
    def create_for_evaluation(cur: Any, portfolio_id: UUID, evaluation_id: UUID) -> bool:
        cur.execute(
            "INSERT INTO portfolio_private.price_notifications (portfolio_id, evaluation_id) "
            "SELECT e.portfolio_id, e.id "
            "FROM portfolio_private.price_evaluations e "
            "JOIN portfolio_private.price_targets t "
            "ON t.portfolio_id=e.portfolio_id AND t.id=e.target_id "
            "WHERE e.portfolio_id=%s AND e.id=%s AND e.result='inside' "
            "AND t.active=true AND t.version=e.target_version "
            "ON CONFLICT (evaluation_id) DO NOTHING;",
            (str(portfolio_id), str(evaluation_id)),
        )
        return cur.rowcount == 1

    @staticmethod
    def notify_buy_reached(cur: Any, portfolio_id: UUID, evaluation_id: UUID, asset_id: UUID) -> None:
        """Record a hit, replacing the unread notice of the same asset."""
        cur.execute(
            "SELECT n.id FROM portfolio_private.price_notifications n "
            "JOIN portfolio_private.price_evaluations e "
            "ON e.portfolio_id=n.portfolio_id AND e.id=n.evaluation_id "
            "JOIN portfolio_private.price_targets t "
            "ON t.portfolio_id=e.portfolio_id AND t.id=e.target_id "
            "WHERE n.portfolio_id=%s AND t.asset_id=%s AND n.read_at IS NULL "
            "ORDER BY n.created_at DESC LIMIT 1;",
            (str(portfolio_id), str(asset_id)),
        )
        existing = cur.fetchone()
        if existing is not None:
            cur.execute(
                "UPDATE portfolio_private.price_notifications "
                "SET evaluation_id=%s, created_at=now(), displayed_at=NULL "
                "WHERE portfolio_id=%s AND id=%s AND read_at IS NULL;",
                (str(evaluation_id), str(portfolio_id), str(existing[0])),
            )
            if cur.rowcount == 1:
                return
        cur.execute(
            "INSERT INTO portfolio_private.price_notifications (portfolio_id, evaluation_id) "
            "VALUES (%s, %s) ON CONFLICT (evaluation_id) DO NOTHING;",
            (str(portfolio_id), str(evaluation_id)),
        )

    @staticmethod
    def _history_sql() -> str:
        return (
            "SELECT n.id, n.evaluation_id, n.created_at, n.displayed_at, n.read_at, "
            "e.cycle_id, e.target_id, e.target_version, e.target_price_usd, e.target_kind, "
            "e.target_orientation, e.proximity_percent, e.price_usd, e.quoted_at, "
            "e.evaluated_at, e.distance_percent, e.result, e.error_code, "
            "a.id, a.external_id, a.symbol, a.name "
            "FROM portfolio_private.price_notifications n "
            "JOIN portfolio_private.price_evaluations e "
            "ON e.portfolio_id=n.portfolio_id AND e.id=n.evaluation_id "
            "JOIN portfolio_private.price_targets t "
            "ON t.portfolio_id=e.portfolio_id AND t.id=e.target_id "
            "JOIN portfolio_private.assets a "
            "ON a.portfolio_id=t.portfolio_id AND a.id=t.asset_id "
        )

    def list_history(
        self,
        cur: Any,
        portfolio_id: UUID,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
        cycle_id: UUID | None = None,
        current_targets_only: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not 1 <= limit <= MAX_PAGE_SIZE:
            raise ValueError(f"limit deve ficar entre 1 e {MAX_PAGE_SIZE}.")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now deve conter timezone.")
        cutoff = current.astimezone(timezone.utc) - HISTORY_RETENTION

        conditions = ["n.portfolio_id=%s", "n.created_at > %s"]
        params: list[Any] = [str(portfolio_id), cutoff]
        if cycle_id is not None:
            conditions.append("e.cycle_id=%s")
            params.append(str(cycle_id))
        if current_targets_only:
            conditions.extend(["e.result='inside'", "t.active=true", "t.version=e.target_version"])
        if cursor:
            created_at, notification_id = PriceTargetService._decode_cursor(cursor)
            conditions.append("(n.created_at < %s OR (n.created_at = %s AND n.id < %s))")
            params.extend([created_at, created_at, str(notification_id)])
        params.append(limit + 1)
        cur.execute(
            self._history_sql()
            + "WHERE " + " AND ".join(conditions)
            + " ORDER BY n.created_at DESC, n.id DESC LIMIT %s;",
            tuple(params),
        )
        rows = cur.fetchall()
        has_more = len(rows) > limit
        visible = rows[:limit]
        next_cursor = (
            PriceTargetService._encode_cursor(visible[-1][2], visible[-1][0])
            if has_more and visible else None
        )
        return {"items": [_notification_body(row) for row in visible], "next_cursor": next_cursor}

    @staticmethod
    def _acknowledge(
        cur: Any,
        portfolio_id: UUID,
        notification_id: UUID,
        *,
        field: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if field == "displayed_at":
            assignments = "displayed_at=COALESCE(displayed_at,%s)"
        elif field == "read_at":
            # The table constraint requires a read notification to have been displayed.
            assignments = (
                "displayed_at=COALESCE(displayed_at,%s), read_at=COALESCE(read_at,%s)"
            )
        else:
            raise ValueError("Campo de ACK inválido.")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now deve conter timezone.")
        current = current.astimezone(timezone.utc)
        cur.execute(
            "UPDATE portfolio_private.price_notifications SET " + assignments + " "
            "WHERE portfolio_id=%s AND id=%s AND created_at > %s "
            "RETURNING id, created_at, displayed_at, read_at;",
            (
                (current, current, str(portfolio_id), str(notification_id), current - HISTORY_RETENTION)
                if field == "read_at"
                else (current, str(portfolio_id), str(notification_id), current - HISTORY_RETENTION)
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError("Notificação não encontrada ou expirada.")
        return {
            "id": str(row[0]),
            "created_at": _iso(row[1]),
            "displayed_at": _iso(row[2]),
            "read_at": _iso(row[3]),
        }

    def acknowledge_displayed(
        self,
        cur: Any,
        portfolio_id: UUID,
        notification_id: UUID,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        return self._acknowledge(
            cur, portfolio_id, notification_id, field="displayed_at", now=now
        )

    def acknowledge_read(
        self,
        cur: Any,
        portfolio_id: UUID,
        notification_id: UUID,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        return self._acknowledge(cur, portfolio_id, notification_id, field="read_at", now=now)
