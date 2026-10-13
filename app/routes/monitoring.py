"""Authenticated HTTP endpoints for price targets, settings, and mappings."""

from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, StrictStr

from app.db import get_db_connection
from app.routes.api import get_current_user_id, portfolio_service
from app.services.monitoring import MonitoringCycleService
from app.services.notifications import NotificationService
from app.services.portfolio import IdempotencyConflictError, RevisionConflictError
from app.services.price_mappings import (
    PriceMappingService,
    ensure_provider_catalog,
)
from app.services.price_targets import PriceTargetService


router = APIRouter(prefix="/api/v1", tags=["monitoring"])
target_service = PriceTargetService()
mapping_service = PriceMappingService()
cycle_service = MonitoringCycleService()
notification_service = NotificationService()


class CreateTargetInput(BaseModel):
    asset_id: UUID
    kind: StrictStr
    price_usd: StrictStr
    active: bool = True
    orientation: Optional[StrictStr] = Field(None, max_length=1000)


class PatchTargetInput(BaseModel):
    kind: Optional[StrictStr] = None
    price_usd: Optional[StrictStr] = None
    active: Optional[bool] = None
    orientation: Optional[StrictStr] = Field(None, max_length=1000)


class PatchSettingsInput(BaseModel):
    proximity_percent: StrictStr


class PutMappingInput(BaseModel):
    provider_coin_id: StrictStr = Field(min_length=1, max_length=200)


class CreateCycleInput(BaseModel):
    client_request_id: UUID
    force: bool = False


def _error(http_status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={"error": {"code": code, "message": message}},
    )


def _idempotency_key(value: UUID | None) -> UUID:
    if value is None:
        raise _error(
            status.HTTP_428_PRECONDITION_REQUIRED,
            "MISSING_IDEMPOTENCY_KEY",
            "Cabeçalho Idempotency-Key é obrigatório.",
        )
    return value


def _expected_version(value: str | None) -> int:
    if value is None:
        raise _error(
            status.HTTP_428_PRECONDITION_REQUIRED,
            "MISSING_VERSION",
            "Cabeçalho If-Match é obrigatório.",
        )
    raw = value.strip()
    if raw.startswith("W/"):
        raw = raw[2:].strip()
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        raw = raw[1:-1]
    try:
        version = int(raw)
    except ValueError:
        raise _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_VERSION", "If-Match deve conter uma versão inteira.")
    if version < 0:
        raise _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_VERSION", "If-Match não pode ser negativo.")
    return version


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _translate_mutation_error(exc: Exception) -> HTTPException:
    if isinstance(exc, IdempotencyConflictError):
        return _error(status.HTTP_409_CONFLICT, "IDEMPOTENCY_CONFLICT", str(exc))
    if isinstance(exc, RevisionConflictError):
        return _error(status.HTTP_409_CONFLICT, "REVISION_CONFLICT", str(exc))
    if isinstance(exc, LookupError):
        return _error(status.HTTP_404_NOT_FOUND, "RESOURCE_NOT_FOUND", str(exc))
    if isinstance(exc, ValueError):
        return _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_INPUT", str(exc))
    return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE", "Serviço temporariamente indisponível.")


@router.get("/price-targets")
def list_price_targets(
    response: Response,
    limit: int = Query(100, ge=1, le=100),
    cursor: Optional[str] = None,
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            try:
                return target_service.list_targets(cur, portfolio_id, limit=limit, cursor=cursor)
            except ValueError as exc:
                raise _translate_mutation_error(exc)


@router.post("/price-targets", status_code=status.HTTP_201_CREATED)
def create_price_target(
    body: CreateTargetInput,
    response: Response,
    idempotency_key: Optional[UUID] = Header(None, alias="Idempotency-Key"),
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    key = _idempotency_key(idempotency_key)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            try:
                result, replayed = target_service.create_target(
                    cur,
                    portfolio_id,
                    user_id,
                    asset_id=body.asset_id,
                    kind=body.kind,
                    price_usd=body.price_usd,
                    active=body.active,
                    orientation=body.orientation,
                    idempotency_key=key,
                )
            except (ValueError, LookupError, RevisionConflictError, IdempotencyConflictError) as exc:
                conn.rollback()
                raise _translate_mutation_error(exc)
            conn.commit()
    response.status_code = status.HTTP_200_OK if replayed else status.HTTP_201_CREATED
    if replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return result


@router.patch("/price-targets/{target_id}")
def patch_price_target(
    target_id: UUID,
    body: PatchTargetInput,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    idempotency_key: Optional[UUID] = Header(None, alias="Idempotency-Key"),
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    expected = _expected_version(if_match)
    key = _idempotency_key(idempotency_key)
    changes = body.model_dump(exclude_unset=True)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            try:
                result, replayed = target_service.update_target(
                    cur, portfolio_id, user_id, target_id, changes,
                    expected_version=expected, idempotency_key=key,
                )
            except (ValueError, LookupError, RevisionConflictError, IdempotencyConflictError) as exc:
                conn.rollback()
                raise _translate_mutation_error(exc)
            conn.commit()
    if replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return result


@router.get("/monitoring/settings")
def get_monitoring_settings(
    response: Response,
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            return target_service.get_settings(cur, portfolio_id)


@router.patch("/monitoring/settings")
def patch_monitoring_settings(
    body: PatchSettingsInput,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    idempotency_key: Optional[UUID] = Header(None, alias="Idempotency-Key"),
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    expected = _expected_version(if_match)
    key = _idempotency_key(idempotency_key)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            try:
                result, replayed = target_service.update_settings(
                    cur, portfolio_id, user_id, body.proximity_percent,
                    expected_version=expected, idempotency_key=key,
                )
            except (ValueError, LookupError, RevisionConflictError, IdempotencyConflictError) as exc:
                conn.rollback()
                raise _translate_mutation_error(exc)
            conn.commit()
    if replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return result


@router.get("/monitoring/mappings")
def list_price_mappings(
    response: Response,
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            return mapping_service.list_mappings(cur, portfolio_id)


@router.put("/monitoring/mappings/{asset_id}")
def put_price_mapping(
    asset_id: UUID,
    body: PutMappingInput,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    idempotency_key: Optional[UUID] = Header(None, alias="Idempotency-Key"),
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    expected = _expected_version(if_match)
    key = _idempotency_key(idempotency_key)
    catalog = ensure_provider_catalog(user_id)
    catalog_ids = (
        {str(coin["id"]) for coin in catalog.get("coins", []) if isinstance(coin, dict) and "id" in coin}
        if catalog.get("state") == "fresh" else None
    )
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            try:
                result, replayed = mapping_service.put_mapping(
                    cur, portfolio_id, user_id, asset_id, body.provider_coin_id,
                    expected_version=expected,
                    idempotency_key=key,
                    catalog_ids=catalog_ids,
                )
            except (ValueError, LookupError, RevisionConflictError, IdempotencyConflictError) as exc:
                conn.rollback()
                raise _translate_mutation_error(exc)
            conn.commit()
    if replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return result


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else None


def _cycle_snapshot(cur: Any, portfolio_id: UUID, cycle_id: UUID, now: datetime) -> dict[str, Any] | None:
    cutoff = now.astimezone(timezone.utc) - timedelta(days=30)
    cur.execute(
        "SELECT c.id, c.status, c.started_at, c.completed_at, c.error_code, s.next_due_at "
        "FROM portfolio_private.monitoring_cycles c "
        "LEFT JOIN portfolio_private.monitoring_state s ON s.portfolio_id=c.portfolio_id "
        "WHERE c.portfolio_id=%s AND c.id=%s AND c.started_at > %s;",
        (str(portfolio_id), str(cycle_id), cutoff),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "cycle_id": str(row[0]),
        "status": row[1],
        "started_at": _iso(row[2]),
        "completed_at": _iso(row[3]),
        "error_code": row[4],
        "next_due_at": _iso(row[5]),
    }


@router.post("/monitoring/cycles")
def post_monitoring_cycle(
    body: CreateCycleInput,
    response: Response,
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    now = datetime.now(timezone.utc)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            reservation = cycle_service.reserve_cycle(
                cur, portfolio_id, body.client_request_id, now=now, force=body.force
            )
            existing = None
            if reservation.cycle_id is not None and (
                reservation.state != "reserved" or reservation.replayed
            ):
                existing = _cycle_snapshot(cur, portfolio_id, reservation.cycle_id, now)
        conn.commit()

    if reservation.state == "blocked":
        response.status_code = reservation.http_status
        if reservation.next_retry_at is not None:
            retry_seconds = max(0, ceil((reservation.next_retry_at - now).total_seconds()))
            response.headers["Retry-After"] = str(retry_seconds)
        return {
            "state": "blocked",
            "status": "blocked",
            "cycle_id": None,
            "reason": reservation.reason,
            "next_due_at": _iso(reservation.next_due_at),
            "next_retry_at": _iso(reservation.next_retry_at),
        }

    if reservation.state == "reserved" and not reservation.replayed:
        run = cycle_service.run_reserved_cycle(
            user_id,
            portfolio_id,
            reservation.cycle_id,
            reservation.lease_token,
        )
        response.status_code = (
            status.HTTP_201_CREATED
            if run.status in {"completed", "partial", "failed"}
            else status.HTTP_202_ACCEPTED
        )
        return {
            "state": run.status,
            "cycle_id": str(run.cycle_id),
            "started_at": now.isoformat(),
            "completed_at": _iso(run.completed_at),
            "error_code": run.error_code,
            "next_due_at": _iso(reservation.next_due_at),
        }

    if reservation.replayed:
        response.status_code = (
            status.HTTP_200_OK
            if existing and existing["status"] in {"completed", "partial", "failed"}
            else status.HTTP_202_ACCEPTED
        )
    else:
        response.status_code = reservation.http_status
    if existing is None and reservation.cycle_id is not None:
        existing = {
            "cycle_id": str(reservation.cycle_id),
            "status": reservation.state,
            "started_at": None,
            "completed_at": None,
            "error_code": None,
            "next_due_at": _iso(reservation.next_due_at),
        }
    return {
        "state": "reused" if reservation.replayed else reservation.state,
        **(existing or {"cycle_id": None, "started_at": None, "completed_at": None}),
        "next_due_at": _iso(reservation.next_due_at),
        "replayed": reservation.replayed,
    }


@router.get("/monitoring/cycles/{cycle_id}")
def get_monitoring_cycle(
    cycle_id: UUID,
    response: Response,
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    now = datetime.now(timezone.utc)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            cycle = _cycle_snapshot(cur, portfolio_id, cycle_id, now)
    if cycle is None:
        raise _error(status.HTTP_404_NOT_FOUND, "CYCLE_NOT_FOUND", "Ciclo não encontrado ou expirado.")
    return cycle


@router.get("/monitoring/quotes")
def get_monitoring_quotes(
    response: Response,
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    now = datetime.now(timezone.utc)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            cur.execute(
                "SELECT id, external_id, symbol, name FROM portfolio_private.assets "
                "WHERE portfolio_id=%s ORDER BY symbol, id;",
                (str(portfolio_id),),
            )
            assets = cur.fetchall()
            crypto_ids = [UUID(str(row[0])) for row in assets if str(row[2]).upper() != "USDT"]
            quotes = portfolio_service.quotes.get_quotes(
                crypto_ids, portfolio_id=portfolio_id, cur=cur, now=now
            )
    items = []
    for asset in assets:
        asset_id, external_id, symbol, name = asset
        if str(symbol).upper() == "USDT":
            quote = {
                "price_usd": "1",
                "source": "usd_peg",
                "quoted_at": now.isoformat(),
                "fetched_at": now.isoformat(),
                "freshness": "available",
                "error_code": None,
            }
        else:
            quote_result = quotes.get(UUID(str(asset_id)))
            quote = {
                "price_usd": str(quote_result.price_usd) if quote_result and quote_result.price_usd is not None else None,
                "source": quote_result.source if quote_result else "none",
                "quoted_at": _iso(quote_result.quoted_at) if quote_result else None,
                "fetched_at": _iso(quote_result.fetched_at) if quote_result else None,
                "freshness": quote_result.status.value if quote_result else "unavailable",
                "error_code": quote_result.error_code if quote_result else "quote_unavailable",
            }
        items.append({
            "asset_id": str(asset_id),
            "external_id": external_id,
            "symbol": symbol,
            "name": name,
            **quote,
        })
    return {"items": items, "quote_snapshot_at": now.isoformat()}


@router.get("/monitoring/evaluations")
def list_price_evaluations(
    response: Response,
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = None,
    target_id: Optional[UUID] = None,
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    conditions = ["e.portfolio_id=%s", "e.created_at > %s"]
    params: list[Any] = []
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            params.extend([str(portfolio_id), cutoff])
            if target_id is not None:
                conditions.append("e.target_id=%s")
                params.append(str(target_id))
            if cursor:
                try:
                    created_at, evaluation_id = target_service._decode_cursor(cursor)
                except ValueError as exc:
                    raise _translate_mutation_error(exc)
                conditions.append("(e.created_at < %s OR (e.created_at = %s AND e.id < %s))")
                params.extend([created_at, created_at, str(evaluation_id)])
            params.append(limit + 1)
            cur.execute(
                "SELECT e.id, e.cycle_id, e.target_id, e.target_version, e.target_price_usd, "
                "e.target_kind, e.target_orientation, e.proximity_percent, e.price_usd, "
                "e.quoted_at, e.evaluated_at, e.distance_percent, e.result, e.error_code, "
                "e.created_at, a.id, a.external_id, a.symbol, a.name "
                "FROM portfolio_private.price_evaluations e "
                "JOIN portfolio_private.price_targets t ON t.portfolio_id=e.portfolio_id AND t.id=e.target_id "
                "JOIN portfolio_private.assets a ON a.portfolio_id=t.portfolio_id AND a.id=t.asset_id "
                "WHERE " + " AND ".join(conditions) +
                " ORDER BY e.created_at DESC, e.id DESC LIMIT %s;",
                tuple(params),
            )
            rows = cur.fetchall()
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = (
        target_service._encode_cursor(visible[-1][14], visible[-1][0])
        if has_more and visible else None
    )
    items = [{
        "id": str(row[0]),
        "cycle_id": str(row[1]),
        "target": {
            "id": str(row[2]),
            "version": int(row[3]),
            "price_usd": str(row[4]),
            "kind": row[5],
            "orientation": row[6],
            "proximity_percent": str(row[7]),
        },
        "quote": {
            "price_usd": str(row[8]) if row[8] is not None else None,
            "quoted_at": _iso(row[9]),
            "evaluated_at": _iso(row[10]),
            "distance_percent": str(row[11]) if row[11] is not None else None,
        },
        "result": row[12],
        "error_code": row[13],
        "created_at": _iso(row[14]),
        "asset": {
            "id": str(row[15]),
            "external_id": row[16],
            "symbol": row[17],
            "name": row[18],
        },
    } for row in visible]
    return {"items": items, "next_cursor": next_cursor}


@router.get("/notifications")
def list_price_notifications(
    response: Response,
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = None,
    cycle_id: Optional[UUID] = None,
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    now = datetime.now(timezone.utc)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            try:
                return notification_service.list_history(
                    cur, portfolio_id, limit=limit, cursor=cursor, cycle_id=cycle_id,
                    current_targets_only=cycle_id is not None, now=now,
                )
            except ValueError as exc:
                raise _translate_mutation_error(exc)


@router.post("/notifications/{notification_id}/displayed")
def acknowledge_notification_displayed(
    notification_id: UUID,
    response: Response,
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    now = datetime.now(timezone.utc)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            try:
                result = notification_service.acknowledge_displayed(
                    cur, portfolio_id, notification_id, now=now
                )
            except LookupError as exc:
                raise _translate_mutation_error(exc)
        conn.commit()
    return result


@router.post("/notifications/{notification_id}/read")
def acknowledge_notification_read(
    notification_id: UUID,
    response: Response,
    user_id: UUID = Depends(get_current_user_id),
):
    _no_store(response)
    now = datetime.now(timezone.utc)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            try:
                result = notification_service.acknowledge_read(
                    cur, portfolio_id, notification_id, now=now
                )
            except LookupError as exc:
                raise _translate_mutation_error(exc)
        conn.commit()
    return result
