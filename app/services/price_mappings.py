"""Explicit asset/provider mappings and coordinated provider catalog refresh."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any
from uuid import UUID, uuid4

from app.config import get_settings, provider_configured
from app.db import get_db_connection
from app.services.coingecko import CoinGeckoClient
from app.services.portfolio import (
    IdempotencyConflictError,
    RevisionConflictError,
    compute_request_hash,
)
from app.services.provider_budget import ProviderBudgetService
from app.services.price_targets import PriceTargetService, _receipt_body


CATALOG_TTL = timedelta(hours=24)
CATALOG_LEASE = timedelta(seconds=60)
PROVIDER = "coingecko"
_PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,199}$")


@dataclass(frozen=True)
class CatalogClaim:
    state: str
    token: UUID | None = None
    coins: list[dict[str, str]] | None = None
    expires_at: datetime | None = None


class ProviderCatalogService:
    def get_cached(self, cur: Any, *, provider: str = PROVIDER, now: datetime | None = None):
        current = now or datetime.now(timezone.utc)
        cur.execute(
            "SELECT payload, fetched_at, expires_at, version FROM portfolio_private.provider_catalog "
            "WHERE provider = %s;",
            (provider,),
        )
        row = cur.fetchone()
        if not row or row[2] is None or row[2] <= current:
            return None
        payload = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        if not isinstance(payload, list):
            return None
        return {"coins": payload, "fetched_at": row[1], "expires_at": row[2], "version": int(row[3])}

    def claim_refresh(
        self,
        cur: Any,
        *,
        provider: str = PROVIDER,
        now: datetime | None = None,
    ) -> CatalogClaim:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now deve conter timezone.")
        current = current.astimezone(timezone.utc)
        cur.execute(
            "INSERT INTO portfolio_private.provider_catalog (provider) VALUES (%s) "
            "ON CONFLICT (provider) DO NOTHING;",
            (provider,),
        )
        cur.execute(
            "SELECT payload, expires_at, refresh_token, refresh_lease_until "
            "FROM portfolio_private.provider_catalog WHERE provider=%s FOR UPDATE;",
            (provider,),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Estado do catálogo não pôde ser inicializado.")
        payload = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        if row[1] is not None and row[1] > current:
            return CatalogClaim("fresh", coins=payload, expires_at=row[1])
        if row[3] is not None and row[3] > current:
            return CatalogClaim("in_flight", expires_at=row[3])
        token = uuid4()
        cur.execute(
            "UPDATE portfolio_private.provider_catalog SET refresh_token=%s, "
            "refresh_lease_until=%s, updated_at=%s WHERE provider=%s;",
            (str(token), current + CATALOG_LEASE, current, provider),
        )
        return CatalogClaim("claimed", token=token)

    @staticmethod
    def release_refresh(
        cur: Any,
        token: UUID,
        *,
        provider: str = PROVIDER,
        error_code: str | None = None,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(timezone.utc)
        cur.execute(
            "UPDATE portfolio_private.provider_catalog SET refresh_token=NULL, "
            "refresh_lease_until=NULL, last_error=%s, updated_at=%s "
            "WHERE provider=%s AND refresh_token=%s;",
            (error_code, current, provider, str(token)),
        )

    @staticmethod
    def complete_refresh(
        cur: Any,
        token: UUID,
        coins: list[dict[str, str]],
        *,
        provider: str = PROVIDER,
        now: datetime | None = None,
    ) -> bool:
        current = now or datetime.now(timezone.utc)
        cur.execute(
            "UPDATE portfolio_private.provider_catalog SET payload=%s, fetched_at=%s, "
            "expires_at=%s, version=version+1, refresh_token=NULL, refresh_lease_until=NULL, "
            "last_error=NULL, updated_at=%s WHERE provider=%s AND refresh_token=%s "
            "AND refresh_lease_until > %s;",
            (
                json.dumps(coins, ensure_ascii=False), current,
                current + CATALOG_TTL, current, provider, str(token), current,
            ),
        )
        return cur.rowcount == 1


class PriceMappingService:
    def list_mappings(self, cur: Any, portfolio_id: UUID) -> dict[str, Any]:
        cur.execute(
            "SELECT a.id, a.external_id, a.symbol, a.name, m.provider, m.provider_coin_id, "
            "m.status, m.version, m.updated_at "
            "FROM portfolio_private.assets a "
            "LEFT JOIN portfolio_private.asset_price_mappings m "
            "ON m.portfolio_id=a.portfolio_id AND m.asset_id=a.id "
            "WHERE a.portfolio_id=%s AND a.active=true AND a.symbol <> 'USDT' "
            "ORDER BY a.symbol, a.id;",
            (str(portfolio_id),),
        )
        items = []
        for row in cur.fetchall():
            items.append({
                "asset_id": str(row[0]),
                "external_id": row[1],
                "symbol": row[2],
                "name": row[3],
                "provider": row[4] or PROVIDER,
                "provider_coin_id": row[5],
                "status": row[6] or "pending",
                "version": int(row[7]) if row[7] is not None else 0,
                "updated_at": row[8].isoformat() if hasattr(row[8], "isoformat") else None,
            })
        valid = sum(1 for item in items if item["status"] == "valid")
        pending = sum(1 for item in items if item["status"] == "pending")
        unsupported = sum(1 for item in items if item["status"] == "unsupported")
        total = len(items)
        return {
            "items": items,
            "coverage": {
                "total_assets": total,
                "valid_assets": valid,
                "pending_assets": pending,
                "unsupported_assets": unsupported,
                "coverage_percent": (valid * 100 / total) if total else 100.0,
            },
        }

    def put_mapping(
        self,
        cur: Any,
        portfolio_id: UUID,
        actor_id: UUID,
        asset_id: UUID,
        provider_coin_id: str,
        *,
        expected_version: int,
        idempotency_key: UUID,
        catalog_ids: set[str] | None,
    ) -> tuple[dict[str, Any], bool]:
        coin_id = str(provider_coin_id).strip().lower()
        if not _PROVIDER_ID.fullmatch(coin_id):
            raise ValueError("provider_coin_id inválido.")
        path = f"/api/v1/monitoring/mappings/{asset_id}"
        request_body = {"provider_coin_id": coin_id, "expected_version": expected_version}
        request_hash = compute_request_hash("PUT", path, request_body, expected_version)
        PriceTargetService._lock_portfolio(cur, portfolio_id)
        previous = PriceTargetService._find_receipt(cur, portfolio_id, idempotency_key, request_hash)
        if previous:
            return previous[0], True

        cur.execute(
            "SELECT external_id, symbol, active FROM portfolio_private.assets "
            "WHERE portfolio_id=%s AND id=%s FOR UPDATE;",
            (str(portfolio_id), str(asset_id)),
        )
        asset = cur.fetchone()
        if asset is None or not asset[2] or str(asset[1]).upper() == "USDT":
            raise LookupError("Ativo não encontrado, inativo ou não mapeável.")
        cur.execute(
            "SELECT provider_coin_id, status, version, updated_at "
            "FROM portfolio_private.asset_price_mappings "
            "WHERE portfolio_id=%s AND asset_id=%s FOR UPDATE;",
            (str(portfolio_id), str(asset_id)),
        )
        existing = cur.fetchone()
        current_version = int(existing[2]) if existing else 0
        if current_version != expected_version:
            raise RevisionConflictError(f"Conflito de versão; versão atual: {current_version}.")

        status = "pending" if catalog_ids is None else ("valid" if coin_id in catalog_ids else "unsupported")
        version = current_version + 1
        cur.execute(
            "INSERT INTO portfolio_private.asset_price_mappings "
            "(portfolio_id, asset_id, provider, provider_coin_id, status, version, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, now()) "
            "ON CONFLICT (portfolio_id, asset_id) DO UPDATE SET "
            "provider=EXCLUDED.provider, provider_coin_id=EXCLUDED.provider_coin_id, "
            "status=EXCLUDED.status, version=EXCLUDED.version, updated_at=EXCLUDED.updated_at;",
            (str(portfolio_id), str(asset_id), PROVIDER, coin_id, status, version),
        )
        mapping = {
            "asset_id": str(asset_id),
            "external_id": asset[0],  # Existing asset identity is never rewritten.
            "symbol": asset[1],
            "provider": PROVIDER,
            "provider_coin_id": coin_id,
            "status": status,
            "version": version,
        }
        old_value = None
        if existing:
            old_value = {
                "provider_coin_id": existing[0],
                "status": existing[1],
                "version": current_version,
            }
        PriceTargetService._audit(
            cur, portfolio_id, "mapping", asset_id, actor_id, old_value, mapping
        )
        PriceTargetService._save_receipt(cur, portfolio_id, idempotency_key, request_hash, 200, mapping)
        return mapping, False


def ensure_provider_catalog(
    user_id: UUID,
    *,
    now: datetime | None = None,
    connection_factory=get_db_connection,
) -> dict[str, Any]:
    """Use fresh cache or claim, reserve one call, commit, then fetch outside SQL."""
    current = now or datetime.now(timezone.utc)
    settings = get_settings()
    catalogs = ProviderCatalogService()
    budgets = ProviderBudgetService()

    with connection_factory(user_id) as conn:
        with conn.cursor() as cur:
            cached = catalogs.get_cached(cur, now=current)
            if cached is not None:
                return {"state": "fresh", **cached}

    if not provider_configured(settings, current):
        return {"state": "pending", "reason": "config_required"}
    api_key = settings.coingecko_demo_api_key.get_secret_value()

    with connection_factory(user_id) as conn:
        with conn.cursor() as cur:
            claim = catalogs.claim_refresh(cur, now=current)
            if claim.state == "fresh":
                conn.commit()
                return {"state": "fresh", "coins": claim.coins, "expires_at": claim.expires_at}
            if claim.state == "in_flight":
                conn.commit()
                return {"state": "pending", "reason": "refresh_in_progress", "retry_at": claim.expires_at}
            decision = budgets.reserve(
                cur,
                provider=PROVIDER,
                api_key=api_key,
                window_start=settings.coingecko_window_start,
                window_end=settings.coingecko_window_end,
                configured_limit=settings.coingecko_call_limit,
                request_count=1,
                now=current,
            )
            if not decision.allowed:
                catalogs.release_refresh(cur, claim.token, error_code=decision.reason, now=current)
                conn.commit()
                return {
                    "state": "pending",
                    "reason": decision.reason,
                    "retry_at": decision.next_retry_at,
                }
            conn.commit()

    with CoinGeckoClient(api_key) as client:
        result = client.fetch_coin_catalog()

    if result.error_code:
        retry_at = None
        with connection_factory(user_id) as conn:
            with conn.cursor() as cur:
                if result.error_code == "provider_rate_limited":
                    delay = result.retry_after_seconds if result.retry_after_seconds is not None else 300
                    retry_at = current + timedelta(seconds=max(0, delay))
                    budgets.set_cooldown(
                        cur, provider=PROVIDER, api_key=api_key,
                        cooldown_until=retry_at, now=current,
                    )
                catalogs.release_refresh(cur, claim.token, error_code=result.error_code, now=current)
                conn.commit()
        return {"state": "pending", "reason": result.error_code, "retry_at": retry_at}

    with connection_factory(user_id) as conn:
        with conn.cursor() as cur:
            saved = catalogs.complete_refresh(cur, claim.token, result.coins, now=current)
            conn.commit()
    return {
        "state": "fresh" if saved else "pending",
        "coins": result.coins if saved else None,
        "expires_at": current + CATALOG_TTL if saved else None,
        "reason": None if saved else "refresh_lease_expired",
    }
