"""Shared, conservative quota accounting for all CoinGecko requests."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str | None = None
    next_retry_at: datetime | None = None
    reserved_count: int = 0


class ProviderBudgetService:
    @staticmethod
    def key_fingerprint(api_key: str) -> str:
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    def reserve(
        self,
        cur: Any,
        *,
        provider: str,
        api_key: str,
        window_start: datetime | None,
        window_end: datetime | None,
        configured_limit: int,
        request_count: int,
        now: datetime | None = None,
    ) -> BudgetDecision:
        """Persist a reservation before HTTP. Failed/unknown calls are not refunded."""
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now deve conter timezone.")
        current = current.astimezone(timezone.utc)
        if (
            not provider or not api_key or window_start is None or window_end is None
            or configured_limit < 1 or request_count < 1
        ):
            return BudgetDecision(False, "config_required")
        if window_start.tzinfo is None or window_end.tzinfo is None or window_start >= window_end:
            return BudgetDecision(False, "config_required")
        start = window_start.astimezone(timezone.utc)
        end = window_end.astimezone(timezone.utc)
        if current < start:
            return BudgetDecision(False, "config_required", start)
        if current >= end:
            return BudgetDecision(False, "config_required")
        if request_count > configured_limit:
            return BudgetDecision(False, "quota_exhausted", end)

        fingerprint = self.key_fingerprint(api_key)
        cur.execute(
            "INSERT INTO portfolio_private.provider_budget "
            "(provider, key_fingerprint, window_start, window_end, attempts, configured_limit, updated_at) "
            "VALUES (%s, %s, %s, %s, 0, %s, %s) "
            "ON CONFLICT (provider, key_fingerprint) DO NOTHING;",
            (provider, fingerprint, start, end, configured_limit, current),
        )
        cur.execute(
            "SELECT window_start, window_end, attempts, configured_limit, cooldown_until "
            "FROM portfolio_private.provider_budget "
            "WHERE provider = %s AND key_fingerprint = %s FOR UPDATE;",
            (provider, fingerprint),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Reserva de orçamento não pôde ser lida.")

        stored_start, stored_end = row[0], row[1]
        attempts = int(row[2])
        cooldown_until = row[4]
        same_window = stored_start == start and stored_end == end
        if not same_window:
            # A changed operator window cannot reset a still-open budget window.
            if stored_end > current:
                return BudgetDecision(False, "provider_window_changed", stored_end)
            cur.execute(
                "UPDATE portfolio_private.provider_budget SET window_start=%s, window_end=%s, "
                "attempts=0, configured_limit=%s, cooldown_until=NULL, updated_at=%s "
                "WHERE provider=%s AND key_fingerprint=%s;",
                (start, end, configured_limit, current, provider, fingerprint),
            )
            attempts = 0
            cooldown_until = None

        if cooldown_until is not None and cooldown_until > current:
            return BudgetDecision(False, "provider_cooldown", cooldown_until)
        if attempts + request_count > configured_limit:
            return BudgetDecision(False, "quota_exhausted", end)

        cur.execute(
            "UPDATE portfolio_private.provider_budget SET attempts=%s, configured_limit=%s, "
            "cooldown_until=NULL, updated_at=%s WHERE provider=%s AND key_fingerprint=%s;",
            (attempts + request_count, configured_limit, current, provider, fingerprint),
        )
        return BudgetDecision(True, reserved_count=request_count)

    def set_cooldown(
        self,
        cur: Any,
        *,
        provider: str,
        api_key: str,
        cooldown_until: datetime,
        now: datetime | None = None,
    ) -> None:
        if not api_key:
            return
        if cooldown_until.tzinfo is None:
            raise ValueError("cooldown_until deve conter timezone.")
        current = now or datetime.now(timezone.utc)
        cur.execute(
            "UPDATE portfolio_private.provider_budget SET "
            "cooldown_until = GREATEST(COALESCE(cooldown_until, %s), %s), updated_at = %s "
            "WHERE provider = %s AND key_fingerprint = %s;",
            (
                cooldown_until.astimezone(timezone.utc),
                cooldown_until.astimezone(timezone.utc),
                current.astimezone(timezone.utc),
                provider,
                self.key_fingerprint(api_key),
            ),
        )
