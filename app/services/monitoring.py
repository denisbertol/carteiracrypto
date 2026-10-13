"""Durable cycle scheduling, quota gating, and per-portfolio deduplication."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable
from uuid import UUID, uuid4

from app.config import get_settings as get_app_settings, provider_configured
from app.db import get_db_connection
from app.domain.monitoring import classify_target
from app.services.coingecko import CoinGeckoClient, PriceBatch, ProviderQuote
from app.services.cryptoprices import CryptoPricesClient
from app.services.notifications import NotificationService
from app.services.portfolio import compute_request_hash
from app.services.price_history import record_live_price
from app.services.price_targets import PriceTargetService
from app.services.provider_budget import BudgetDecision, ProviderBudgetService


CYCLE_INTERVAL_SECONDS = 300
CYCLE_LEASE_SECONDS = 60
PROVIDER = "coingecko"
CRYPTOPRICES_KEY = "cryptoprices"


@dataclass(frozen=True)
class CycleReservation:
    state: str
    http_status: int
    cycle_id: UUID | None = None
    next_due_at: datetime | None = None
    next_retry_at: datetime | None = None
    reason: str | None = None
    lease_token: UUID | None = None
    replayed: bool = False


@dataclass(frozen=True)
class CycleRunResult:
    cycle_id: UUID
    status: str
    error_code: str | None = None
    evaluations: int = 0
    quotes_updated: int = 0
    completed_at: datetime | None = None


class MonitoringCycleService:
    def __init__(self, budget_service: ProviderBudgetService | None = None):
        self.budgets = budget_service or ProviderBudgetService()

    @staticmethod
    def _blocked(decision: BudgetDecision) -> CycleReservation:
        http_status = 429 if decision.reason in {
            "quota_exhausted", "provider_cooldown", "provider_window_changed"
        } else 503
        return CycleReservation(
            state="blocked",
            http_status=http_status,
            reason=decision.reason or "config_required",
            next_retry_at=decision.next_retry_at,
        )

    @staticmethod
    def _receipt(cur: Any, portfolio_id: UUID, client_request_id: UUID):
        request_hash = compute_request_hash(
            "POST",
            "/api/v1/monitoring/cycles",
            {"client_request_id": str(client_request_id)},
            1,
        )
        previous = PriceTargetService._find_receipt(
            cur, portfolio_id, client_request_id, request_hash
        )
        if previous is None:
            return request_hash, None
        body, status = previous
        return request_hash, CycleReservation(
            state=body.get("status", "reserved"),
            http_status=status,
            cycle_id=UUID(body["cycle_id"]) if body.get("cycle_id") else None,
            next_due_at=datetime.fromisoformat(body["next_due_at"]) if body.get("next_due_at") else None,
            reason=body.get("reason"),
            replayed=True,
        )

    @staticmethod
    def _save_cycle_receipt(
        cur: Any,
        portfolio_id: UUID,
        client_request_id: UUID,
        request_hash: str,
        response_status: int,
        body: dict[str, Any],
    ) -> None:
        PriceTargetService._save_receipt(
            cur,
            portfolio_id,
            client_request_id,
            request_hash,
            response_status,
            body,
        )

    @staticmethod
    def reconcile_expired_cycle(
        cur: Any,
        portfolio_id: UUID,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Fail an expired lease and invalidate its token; never backfill work."""
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now deve conter timezone.")
        current = current.astimezone(timezone.utc)
        cur.execute(
            "SELECT current_cycle_id, lease_until FROM portfolio_private.monitoring_state "
            "WHERE portfolio_id=%s FOR UPDATE;",
            (str(portfolio_id),),
        )
        state = cur.fetchone()
        if state is None or state[0] is None:
            return False
        if state[1] is not None and state[1] > current:
            return False
        cycle_id = state[0]
        cur.execute(
            "UPDATE portfolio_private.monitoring_cycles SET status='failed', completed_at=%s, "
            "error_code='interrupted', lease_token=%s "
            "WHERE portfolio_id=%s AND id=%s AND status IN ('reserved','running');",
            (current, str(uuid4()), str(portfolio_id), str(cycle_id)),
        )
        cycle_changed = cur.rowcount == 1
        cur.execute(
            "UPDATE portfolio_private.monitoring_state SET current_cycle_id=NULL, lease_until=NULL "
            "WHERE portfolio_id=%s AND current_cycle_id=%s;",
            (str(portfolio_id), str(cycle_id)),
        )
        return cycle_changed

    def reserve_cycle(
        self,
        cur: Any,
        portfolio_id: UUID,
        client_request_id: UUID,
        *,
        now: datetime | None = None,
        force: bool = False,
    ) -> CycleReservation:
        """Lock, gate configuration/quota, then persist one cycle before HTTP."""
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now deve conter timezone.")
        current = current.astimezone(timezone.utc)

        # A transaction-scoped advisory lock also serializes the first request,
        # when monitoring_state does not yet exist and therefore cannot be row-locked.
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0));",
            (str(portfolio_id),),
        )
        request_hash, replay = self._receipt(cur, portfolio_id, client_request_id)
        if replay is not None:
            return replay

        cur.execute(
            "SELECT next_due_at, current_cycle_id, lease_until "
            "FROM portfolio_private.monitoring_state WHERE portfolio_id=%s FOR UPDATE;",
            (str(portfolio_id),),
        )
        state = cur.fetchone()
        next_due_at = state[0] if state else None
        current_cycle_id = state[1] if state else None
        lease_until = state[2] if state else None
        if current_cycle_id is not None and lease_until is not None and lease_until > current:
            return CycleReservation(
                "in_progress", 202, cycle_id=UUID(str(current_cycle_id)), next_due_at=next_due_at
            )
        if current_cycle_id is not None:
            # The same lock protects this recovery from the periodic reconciler.
            self.reconcile_expired_cycle(cur, portfolio_id, now=current)

        # cryptoprices has no quota, so a manual check may skip the interval.
        skip_interval = force and getattr(get_app_settings(), "quote_mode", None) == "cryptoprices"
        if next_due_at is not None and next_due_at > current and not skip_interval:
            cur.execute(
                "SELECT id, status FROM portfolio_private.monitoring_cycles "
                "WHERE portfolio_id=%s ORDER BY started_at DESC, id DESC LIMIT 1;",
                (str(portfolio_id),),
            )
            latest = cur.fetchone()
            return CycleReservation(
                "reused" if latest else "not_due",
                200 if latest else 202,
                cycle_id=UUID(str(latest[0])) if latest else None,
                next_due_at=next_due_at,
            )

        settings = get_app_settings()
        if not provider_configured(settings, current):
            return self._blocked(BudgetDecision(False, "config_required"))

        cur.execute(
            "SELECT proximity_percent, revision FROM portfolio_private.monitoring_settings "
            "WHERE portfolio_id=%s;",
            (str(portfolio_id),),
        )
        settings_row = cur.fetchone()
        settings_revision = int(settings_row[1]) if settings_row else 1

        cur.execute(
            "SELECT m.asset_id, m.provider_coin_id, m.version "
            "FROM portfolio_private.asset_price_mappings m "
            "JOIN portfolio_private.assets a ON a.id=m.asset_id AND a.portfolio_id=m.portfolio_id "
            "WHERE m.portfolio_id=%s AND m.provider=%s AND m.status='valid' "
            "AND a.active=true AND a.symbol <> 'USDT' ORDER BY m.asset_id;",
            (str(portfolio_id), PROVIDER),
        )
        mappings = cur.fetchall()
        cryptoprices = getattr(settings, "quote_mode", None) == "cryptoprices"
        if cryptoprices:
            request_count = len(mappings)
            api_key = CRYPTOPRICES_KEY
        else:
            provider_ids = [str(row[1]) for row in mappings]
            api_key = settings.coingecko_demo_api_key.get_secret_value()
            with CoinGeckoClient(api_key) as provider_client:
                request_count = len(provider_client.plan_batches(provider_ids)[0])

        if request_count and not cryptoprices:
            decision = self.budgets.reserve(
                cur,
                provider=PROVIDER,
                api_key=api_key,
                window_start=settings.coingecko_window_start,
                window_end=settings.coingecko_window_end,
                configured_limit=settings.coingecko_call_limit,
                request_count=request_count,
                now=current,
            )
            if not decision.allowed:
                return self._blocked(decision)

        cycle_id, lease_token = uuid4(), uuid4()
        key_fingerprint = self.budgets.key_fingerprint(api_key)
        next_due = current + timedelta(seconds=CYCLE_INTERVAL_SECONDS)
        lease_until = current + timedelta(seconds=CYCLE_LEASE_SECONDS)
        cur.execute(
            "INSERT INTO portfolio_private.monitoring_cycles "
            "(id, portfolio_id, started_at, status, lease_token, settings_revision, "
            "provider_key_fingerprint, reserved_request_count, provider_window_start, "
            "provider_window_end, provider_call_limit) "
            "VALUES (%s, %s, %s, 'reserved', %s, %s, %s, %s, %s, %s, %s);",
            (
                str(cycle_id), str(portfolio_id), current, str(lease_token),
                settings_revision, key_fingerprint, request_count,
                settings.coingecko_window_start, settings.coingecko_window_end,
                settings.coingecko_call_limit,
            ),
        )
        cur.execute(
            "INSERT INTO portfolio_private.monitoring_state "
            "(portfolio_id, next_due_at, current_cycle_id, lease_until) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (portfolio_id) DO UPDATE SET "
            "next_due_at=EXCLUDED.next_due_at, current_cycle_id=EXCLUDED.current_cycle_id, "
            "lease_until=EXCLUDED.lease_until;",
            (str(portfolio_id), next_due, str(cycle_id), lease_until),
        )
        body = {
            "cycle_id": str(cycle_id),
            "status": "reserved",
            "started_at": current.isoformat(),
            "completed_at": None,
            "next_due_at": next_due.isoformat(),
            "reason": None,
        }
        self._save_cycle_receipt(cur, portfolio_id, client_request_id, request_hash, 201, body)
        return CycleReservation(
            "reserved", 201, cycle_id=cycle_id, next_due_at=next_due, lease_token=lease_token
        )

    @staticmethod
    def _terminal_failure(
        cur: Any,
        portfolio_id: UUID,
        cycle_id: UUID,
        error_code: str,
        now: datetime,
    ) -> None:
        cur.execute(
            "UPDATE portfolio_private.monitoring_cycles SET status='failed', completed_at=%s, "
            "error_code=%s, lease_token=%s WHERE portfolio_id=%s AND id=%s "
            "AND status IN ('reserved','running');",
            (now, error_code, str(uuid4()), str(portfolio_id), str(cycle_id)),
        )
        cur.execute(
            "UPDATE portfolio_private.monitoring_state SET current_cycle_id=NULL, lease_until=NULL "
            "WHERE portfolio_id=%s AND current_cycle_id=%s;",
            (str(portfolio_id), str(cycle_id)),
        )

    def _begin_cycle(
        self,
        cur: Any,
        portfolio_id: UUID,
        cycle_id: UUID,
        lease_token: UUID,
        settings: Any,
        now: datetime,
    ) -> dict[str, Any] | None:
        cur.execute(
            "SELECT c.status, c.lease_token, c.settings_revision, c.reserved_request_count, "
            "c.provider_key_fingerprint, c.provider_window_start, c.provider_window_end, "
            "c.provider_call_limit, s.current_cycle_id, s.lease_until "
            "FROM portfolio_private.monitoring_cycles c "
            "JOIN portfolio_private.monitoring_state s ON s.portfolio_id=c.portfolio_id "
            "WHERE c.portfolio_id=%s AND c.id=%s FOR UPDATE OF c, s;",
            (str(portfolio_id), str(cycle_id)),
        )
        row = cur.fetchone()
        if row is None:
            return None
        status, stored_token, settings_revision, reserved_count = row[:4]
        fingerprint, window_start, window_end, call_limit = row[4:8]
        current_cycle_id, lease_until = row[8:10]
        if status != "reserved" or str(stored_token) != str(lease_token):
            return None
        if str(current_cycle_id) != str(cycle_id) or lease_until is None or lease_until <= now:
            self.reconcile_expired_cycle(cur, portfolio_id, now=now)
            return None

        cur.execute(
            "SELECT proximity_percent, revision FROM portfolio_private.monitoring_settings "
            "WHERE portfolio_id=%s;",
            (str(portfolio_id),),
        )
        settings_row = cur.fetchone()
        proximity = Decimal(str(settings_row[0])) if settings_row else Decimal("10.00")
        current_revision = int(settings_row[1]) if settings_row else 1
        if getattr(settings, "quote_mode", None) == "cryptoprices":
            config_matches = (
                provider_configured(settings, now)
                and self.budgets.key_fingerprint(CRYPTOPRICES_KEY) == str(fingerprint).strip()
            )
        else:
            api_key = settings.coingecko_demo_api_key.get_secret_value()
            config_matches = (
                provider_configured(settings, now)
                and self.budgets.key_fingerprint(api_key) == str(fingerprint).strip()
                and settings.coingecko_window_start == window_start
                and settings.coingecko_window_end == window_end
                and int(settings.coingecko_call_limit) == int(call_limit)
            )
        if not config_matches:
            self._terminal_failure(cur, portfolio_id, cycle_id, "config_changed", now)
            return {"state": "failed", "error_code": "config_changed"}
        if current_revision != int(settings_revision):
            self._terminal_failure(cur, portfolio_id, cycle_id, "settings_changed", now)
            return {"state": "failed", "error_code": "settings_changed"}

        cur.execute(
            "SELECT a.id, a.external_id, a.symbol, a.active, m.provider, m.provider_coin_id, "
            "m.status, m.version FROM portfolio_private.assets a "
            "LEFT JOIN portfolio_private.asset_price_mappings m "
            "ON m.portfolio_id=a.portfolio_id AND m.asset_id=a.id "
            "WHERE a.portfolio_id=%s AND a.symbol <> 'USDT' ORDER BY a.id;",
            (str(portfolio_id),),
        )
        asset_rows = cur.fetchall()
        assets = []
        for asset in asset_rows:
            assets.append({
                "asset_id": str(asset[0]),
                "external_id": asset[1],
                "symbol": asset[2],
                "active": bool(asset[3]),
                "provider": asset[4] or PROVIDER,
                "provider_coin_id": asset[5],
                "mapping_status": asset[6] or "pending",
                "mapping_version": int(asset[7]) if asset[7] is not None else 0,
            })
        cur.execute(
            "SELECT id, asset_id, kind, price_usd, active, orientation, version "
            "FROM portfolio_private.price_targets WHERE portfolio_id=%s AND active=true "
            "ORDER BY id;",
            (str(portfolio_id),),
        )
        targets = [
            {
                "id": str(target[0]),
                "asset_id": str(target[1]),
                "kind": target[2],
                "price_usd": Decimal(str(target[3])),
                "active": bool(target[4]),
                "orientation": target[5],
                "version": int(target[6]),
            }
            for target in cur.fetchall()
        ]
        cur.execute(
            "UPDATE portfolio_private.monitoring_cycles SET status='running' "
            "WHERE portfolio_id=%s AND id=%s AND status='reserved' AND lease_token=%s;",
            (str(portfolio_id), str(cycle_id), str(lease_token)),
        )
        if cur.rowcount != 1:
            return None
        return {
            "assets": assets,
            "targets": targets,
            "proximity_percent": proximity,
            "settings_revision": current_revision,
            "reserved_request_count": int(reserved_count),
            "provider_key_fingerprint": str(fingerprint).strip(),
            "lease_until": lease_until,
            "started_at": now,
        }

    @staticmethod
    def _target_unchanged(snapshot: dict[str, Any], current: dict[str, Any] | None) -> bool:
        return bool(
            current
            and current["active"]
            and current["asset_id"] == snapshot["asset_id"]
            and current["kind"] == snapshot["kind"]
            and current["price_usd"] == snapshot["price_usd"]
            and current["orientation"] == snapshot["orientation"]
            and current["version"] == snapshot["version"]
        )

    @staticmethod
    def _mapping_unchanged(snapshot: dict[str, Any], current: dict[str, Any] | None) -> bool:
        return bool(
            current
            and current["active"] == snapshot["active"]
            and current["symbol"] == snapshot["symbol"]
            and current["provider"] == snapshot["provider"]
            and current["provider_coin_id"] == snapshot["provider_coin_id"]
            and current["mapping_status"] == snapshot["mapping_status"]
            and current["mapping_version"] == snapshot["mapping_version"]
        )

    def _finish_cycle(
        self,
        cur: Any,
        portfolio_id: UUID,
        cycle_id: UUID,
        lease_token: UUID,
        snapshot: dict[str, Any],
        price_batch: PriceBatch,
        api_key: str,
        now: datetime,
    ) -> CycleRunResult:
        # Mutations of targets, mappings, and settings take the same lock. This
        # makes revalidation plus publication a single serialized decision.
        PriceTargetService._lock_portfolio(cur, portfolio_id)
        cur.execute(
            "SELECT c.status, c.lease_token, s.current_cycle_id, s.lease_until "
            "FROM portfolio_private.monitoring_cycles c "
            "JOIN portfolio_private.monitoring_state s ON s.portfolio_id=c.portfolio_id "
            "WHERE c.portfolio_id=%s AND c.id=%s FOR UPDATE OF c, s;",
            (str(portfolio_id), str(cycle_id)),
        )
        locked = cur.fetchone()
        if locked is None:
            return CycleRunResult(cycle_id, "interrupted", "lease_lost")
        status, stored_token, current_cycle_id, lease_until = locked
        if (
            status != "running" or str(stored_token) != str(lease_token)
            or str(current_cycle_id) != str(cycle_id)
        ):
            return CycleRunResult(cycle_id, "interrupted", "lease_lost")
        if lease_until is None or lease_until <= now:
            self.reconcile_expired_cycle(cur, portfolio_id, now=now)
            return CycleRunResult(cycle_id, "interrupted", "lease_expired")

        cur.execute(
            "SELECT proximity_percent, revision FROM portfolio_private.monitoring_settings "
            "WHERE portfolio_id=%s FOR SHARE;",
            (str(portfolio_id),),
        )
        setting_row = cur.fetchone()
        current_settings_revision = int(setting_row[1]) if setting_row else 1
        settings_changed = current_settings_revision != snapshot["settings_revision"]

        cur.execute(
            "SELECT a.id, a.symbol, a.active, m.provider, m.provider_coin_id, m.status, m.version "
            "FROM portfolio_private.assets a LEFT JOIN portfolio_private.asset_price_mappings m "
            "ON m.portfolio_id=a.portfolio_id AND m.asset_id=a.id "
            "WHERE a.portfolio_id=%s AND a.symbol <> 'USDT' FOR SHARE OF a;",
            (str(portfolio_id),),
        )
        current_assets: dict[str, dict[str, Any]] = {}
        for row in cur.fetchall():
            current_assets[str(row[0])] = {
                "asset_id": str(row[0]), "symbol": row[1], "active": bool(row[2]),
                "provider": row[3] or PROVIDER, "provider_coin_id": row[4],
                "mapping_status": row[5] or "pending",
                "mapping_version": int(row[6]) if row[6] is not None else 0,
            }
        snapshot_assets = {asset["asset_id"]: asset for asset in snapshot["assets"]}
        mapping_valid: dict[str, bool] = {}
        for asset_id, asset in snapshot_assets.items():
            mapping_valid[asset_id] = self._mapping_unchanged(asset, current_assets.get(asset_id))

        cur.execute(
            "SELECT id, asset_id, kind, price_usd, active, orientation, version "
            "FROM portfolio_private.price_targets WHERE portfolio_id=%s FOR SHARE;",
            (str(portfolio_id),),
        )
        current_targets: dict[str, dict[str, Any]] = {}
        for target in cur.fetchall():
            current_targets[str(target[0])] = {
                "id": str(target[0]), "asset_id": str(target[1]), "kind": target[2],
                "price_usd": Decimal(str(target[3])), "active": bool(target[4]),
                "orientation": target[5], "version": int(target[6]),
            }

        quote_updates = 0
        asset_errors: dict[str, str] = {}
        for asset_id, asset in snapshot_assets.items():
            if not asset["active"]:
                continue
            if not mapping_valid[asset_id]:
                asset_errors[asset_id] = "mapping_changed"
                continue
            if asset["mapping_status"] != "valid" or not asset["provider_coin_id"]:
                asset_errors[asset_id] = "mapping_unsupported" if asset["mapping_status"] == "unsupported" else "mapping_pending"
                continue
            coin_id = asset["provider_coin_id"]
            quote = price_batch.quotes.get(coin_id)
            if quote is None:
                asset_errors[asset_id] = price_batch.errors.get(coin_id, "provider_missing_result")
                cur.execute(
                    "UPDATE portfolio_private.latest_quotes SET last_attempt_at=%s, last_error=%s "
                    "WHERE portfolio_id=%s AND asset_id=%s;",
                    (now, asset_errors[asset_id], str(portfolio_id), asset_id),
                )
                continue
            cur.execute(
                "INSERT INTO portfolio_private.latest_quotes "
                "(portfolio_id, asset_id, price_usd, quoted_at, fetched_at, provider, source_cycle_id, "
                "last_attempt_at, last_error) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NULL) "
                "ON CONFLICT (portfolio_id, asset_id) DO UPDATE SET "
                "price_usd=EXCLUDED.price_usd, quoted_at=EXCLUDED.quoted_at, fetched_at=EXCLUDED.fetched_at, "
                "provider=EXCLUDED.provider, source_cycle_id=EXCLUDED.source_cycle_id, "
                "last_attempt_at=EXCLUDED.last_attempt_at, last_error=NULL "
                "WHERE EXCLUDED.quoted_at >= portfolio_private.latest_quotes.quoted_at;",
                (
                    str(portfolio_id), asset_id, str(quote.price_usd), quote.quoted_at,
                    quote.fetched_at,
                    CRYPTOPRICES_KEY if api_key == CRYPTOPRICES_KEY else PROVIDER,
                    str(cycle_id), now,
                ),
            )
            quote_updates += cur.rowcount
            record_live_price(cur, portfolio_id, asset_id, quote.price_usd, quote.quoted_at, now)

        evaluation_count = 0
        for target in snapshot["targets"]:
            target_id = target["id"]
            asset_id = target["asset_id"]
            asset = snapshot_assets.get(asset_id)
            target_unchanged = self._target_unchanged(target, current_targets.get(target_id))
            if not target_unchanged:
                result, error_code, quote = "superseded", "target_changed", None
            elif settings_changed:
                result, error_code, quote = "superseded", "settings_changed", None
            elif asset is None or not mapping_valid.get(asset_id, False):
                result, error_code, quote = "superseded", "mapping_changed", None
            elif asset["mapping_status"] != "valid" or not asset["provider_coin_id"]:
                result = "error"
                error_code = "mapping_unsupported" if asset["mapping_status"] == "unsupported" else "mapping_pending"
                quote = None
            else:
                coin_id = asset["provider_coin_id"]
                quote = price_batch.quotes.get(coin_id)
                if quote is None:
                    result, error_code = "error", price_batch.errors.get(coin_id, "provider_missing_result")
                else:
                    classification = classify_target(
                        target["price_usd"], quote.price_usd, snapshot["proximity_percent"]
                    )
                    result, error_code = classification.result, None
            distance = None
            price = None
            quoted_at = None
            if quote is not None:
                price = quote.price_usd
                quoted_at = quote.quoted_at
                distance = classify_target(
                    target["price_usd"], quote.price_usd, snapshot["proximity_percent"]
                ).distance_percent
            evaluation_id = uuid4()
            cur.execute(
                "INSERT INTO portfolio_private.price_evaluations "
                "(id, portfolio_id, cycle_id, target_id, target_version, target_price_usd, target_kind, "
                "target_orientation, proximity_percent, price_usd, quoted_at, evaluated_at, "
                "distance_percent, result, error_code) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);",
                (
                    str(evaluation_id), str(portfolio_id), str(cycle_id), target_id, target["version"],
                    str(target["price_usd"]), target["kind"], target["orientation"],
                    str(snapshot["proximity_percent"]), str(price) if price is not None else None,
                    quoted_at, now, str(distance) if distance is not None else None,
                    result, error_code,
                ),
            )
            reached = (
                quote is not None
                and target["kind"] == "buy"
                and quote.price_usd <= target["price_usd"]
            )
            if reached:
                NotificationService.notify_buy_reached(
                    cur, portfolio_id, evaluation_id, asset_id
                )
            evaluation_count += 1

        active_asset_ids = [asset_id for asset_id, asset in snapshot_assets.items() if asset["active"]]
        successful_assets = sum(
            1 for asset_id in active_asset_ids
            if mapping_valid[asset_id]
            and snapshot_assets[asset_id]["mapping_status"] == "valid"
            and snapshot_assets[asset_id]["provider_coin_id"] in price_batch.quotes
        )
        failed_assets = len(active_asset_ids) - successful_assets
        if failed_assets == 0:
            cycle_status, overall_error = "completed", None
        elif successful_assets:
            cycle_status, overall_error = "partial", "partial_results"
        else:
            cycle_status = "failed"
            overall_error = next(iter(asset_errors.values()), "no_valid_quotes")

        if any(error == "provider_rate_limited" for error in price_batch.errors.values()):
            delay = price_batch.retry_after_seconds if price_batch.retry_after_seconds is not None else 300
            self.budgets.set_cooldown(
                cur,
                provider=PROVIDER,
                api_key=api_key,
                cooldown_until=now + timedelta(seconds=max(0, delay)),
                now=now,
            )
        cur.execute(
            "UPDATE portfolio_private.monitoring_cycles SET status=%s, completed_at=%s, error_code=%s "
            "WHERE portfolio_id=%s AND id=%s AND status='running' AND lease_token=%s;",
            (cycle_status, now, overall_error, str(portfolio_id), str(cycle_id), str(lease_token)),
        )
        if cur.rowcount != 1:
            return CycleRunResult(cycle_id, "interrupted", "lease_lost")
        cur.execute(
            "UPDATE portfolio_private.monitoring_state SET current_cycle_id=NULL, lease_until=NULL "
            "WHERE portfolio_id=%s AND current_cycle_id=%s;",
            (str(portfolio_id), str(cycle_id)),
        )
        return CycleRunResult(
            cycle_id, cycle_status, overall_error, evaluation_count, quote_updates, now
        )

    def run_reserved_cycle(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        cycle_id: UUID,
        lease_token: UUID,
        *,
        connection_factory: Callable = get_db_connection,
        client_factory: Callable = CoinGeckoClient,
        clock: Callable[[], datetime] | None = None,
    ) -> CycleRunResult:
        """Commit the snapshot, fetch outside SQL, then revalidate and commit atomically."""
        current_time = clock or (lambda: datetime.now(timezone.utc))
        started = current_time().astimezone(timezone.utc)
        settings = get_app_settings()
        try:
            with connection_factory(user_id) as conn:
                with conn.cursor() as cur:
                    snapshot = self._begin_cycle(
                        cur, portfolio_id, cycle_id, lease_token, settings, started
                    )
                conn.commit()
        except Exception:
            return CycleRunResult(cycle_id, "failed", "cycle_start_failed")
        if snapshot is None:
            return CycleRunResult(cycle_id, "interrupted", "lease_lost")
        if snapshot.get("state") == "failed":
            return CycleRunResult(cycle_id, "failed", snapshot["error_code"])

        cryptoprices = getattr(settings, "quote_mode", None) == "cryptoprices"
        api_key = CRYPTOPRICES_KEY if cryptoprices else settings.coingecko_demo_api_key.get_secret_value()
        if ProviderBudgetService.key_fingerprint(api_key) != snapshot["provider_key_fingerprint"]:
            with connection_factory(user_id) as conn:
                with conn.cursor() as cur:
                    self._terminal_failure(cur, portfolio_id, cycle_id, "config_changed", current_time())
                conn.commit()
            return CycleRunResult(cycle_id, "failed", "config_changed")

        ids = [
            asset["provider_coin_id"] for asset in snapshot["assets"]
            if asset["active"] and asset["mapping_status"] == "valid" and asset["provider_coin_id"]
        ]
        price_batch = PriceBatch()
        if cryptoprices:
            fetched_at = current_time().astimezone(timezone.utc)
            try:
                with CryptoPricesClient() as provider_client:
                    for asset in snapshot["assets"]:
                        if not asset["active"] or asset["mapping_status"] != "valid" or not asset["provider_coin_id"]:
                            continue
                        coin_id = asset["provider_coin_id"]
                        price, error = provider_client.fetch(asset["symbol"], now=fetched_at)
                        if error or price is None:
                            price_batch.errors[coin_id] = error or "provider_invalid_price"
                        else:
                            price_batch.quotes[coin_id] = ProviderQuote(
                                coin_id, price, fetched_at, fetched_at
                            )
                        price_batch.request_count += 1
            except Exception:
                price_batch.errors.update({coin_id: "provider_client_error" for coin_id in ids})
            finished = current_time().astimezone(timezone.utc)
            try:
                with connection_factory(user_id) as conn:
                    with conn.cursor() as cur:
                        result = self._finish_cycle(
                            cur, portfolio_id, cycle_id, lease_token, snapshot,
                            price_batch, api_key, finished,
                        )
                    conn.commit()
                    return result
            except Exception:
                return CycleRunResult(cycle_id, "running", "commit_failed")
        try:
            with client_factory(api_key) as provider_client:
                batches, planning_errors = provider_client.plan_batches(ids)
                if len(batches) > snapshot["reserved_request_count"]:
                    price_batch.errors.update({coin_id: "mapping_changed" for coin_id in ids})
                    result = CycleRunResult(cycle_id, "failed", "mapping_changed")
                    with connection_factory(user_id) as conn:
                        with conn.cursor() as cur:
                            self._terminal_failure(
                                cur, portfolio_id, cycle_id, "mapping_changed", current_time()
                            )
                        conn.commit()
                    return result
                price_batch.errors.update(planning_errors)
                if batches:
                    fetched = provider_client.fetch_prices(ids)
                    price_batch.quotes.update(fetched.quotes)
                    price_batch.errors.update(fetched.errors)
                    price_batch.retry_after_seconds = fetched.retry_after_seconds
                    price_batch.request_count = fetched.request_count
        except Exception:
            price_batch.errors.update({coin_id: "provider_client_error" for coin_id in ids})

        finished = current_time().astimezone(timezone.utc)
        try:
            with connection_factory(user_id) as conn:
                with conn.cursor() as cur:
                    result = self._finish_cycle(
                        cur, portfolio_id, cycle_id, lease_token, snapshot,
                        price_batch, api_key, finished,
                    )
                conn.commit()
                return result
        except Exception:
            # A failed transaction cannot leave half-written quotes/evaluations.
            return CycleRunResult(cycle_id, "running", "commit_failed")
