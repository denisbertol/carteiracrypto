"""Persistence services for versioned price targets and monitoring settings."""

import base64
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from typing import Any
from uuid import UUID, uuid4

from app.services.portfolio import (
    IdempotencyConflictError,
    RevisionConflictError,
    compute_request_hash,
)


DEFAULT_PROXIMITY_PERCENT = Decimal("10.00")
MAX_TARGET_SCALE = 18
MAX_ORIENTATION_LENGTH = 1000


def _decimal(value: Any, field: str, *, positive: bool, scale: int) -> Decimal:
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} deve ser um número decimal válido.")
    if not number.is_finite():
        raise ValueError(f"{field} deve ser finito.")
    if positive and number <= 0:
        raise ValueError(f"{field} deve ser positivo.")
    if not positive and not Decimal("0") <= number <= Decimal("100"):
        raise ValueError(f"{field} deve ficar entre 0 e 100.")
    if max(0, -number.as_tuple().exponent) > scale:
        raise ValueError(f"{field} aceita no máximo {scale} casas decimais.")
    integer_digits = max(0, number.adjusted() + 1) if number else 0
    if integer_digits > 18:
        raise ValueError(f"{field} excede o limite de dígitos inteiros.")
    return number


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value is not None else None)


def _target_body(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": str(row[0]),
        "asset_id": str(row[1]),
        "kind": str(row[2]),
        "price_usd": str(row[3]),
        "active": bool(row[4]),
        "orientation": row[5],
        "version": int(row[6]),
        "created_at": _iso(row[7]),
        "updated_at": _iso(row[8]),
    }


def _settings_body(row: tuple[Any, ...] | None) -> dict[str, Any]:
    if row is None:
        return {
            "proximity_percent": str(DEFAULT_PROXIMITY_PERCENT),
            "interval_seconds": 300,
            "retention_days": 30,
            "version": 1,
        }
    return {
        "proximity_percent": str(row[0]),
        "interval_seconds": 300,
        "retention_days": 30,
        "version": int(row[1]),
    }


def _receipt_body(value: Any) -> dict[str, Any]:
    return json.loads(value) if isinstance(value, str) else value


class PriceTargetService:
    TARGET_COLUMNS = (
        "id, asset_id, kind, price_usd, active, orientation, version, created_at, updated_at"
    )

    @staticmethod
    def _lock_portfolio(cur: Any, portfolio_id: UUID) -> None:
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0));",
            (str(portfolio_id),),
        )

    def list_targets(
        self,
        cur: Any,
        portfolio_id: UUID,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise ValueError("limit deve ficar entre 1 e 100.")
        where_cursor = ""
        params: list[Any] = [str(portfolio_id)]
        if cursor:
            created_at, target_id = self._decode_cursor(cursor)
            where_cursor = "AND (created_at < %s OR (created_at = %s AND id < %s))"
            params.extend([created_at, created_at, str(target_id)])
        params.append(limit + 1)
        cur.execute(
            f"""SELECT {self.TARGET_COLUMNS}
                FROM portfolio_private.price_targets
                WHERE portfolio_id = %s {where_cursor}
                ORDER BY created_at DESC, id DESC
                LIMIT %s;""",
            tuple(params),
        )
        rows = cur.fetchall()
        has_more = len(rows) > limit
        visible = rows[:limit]
        next_cursor = self._encode_cursor(visible[-1][7], visible[-1][0]) if has_more and visible else None
        return {"items": [_target_body(row) for row in visible], "next_cursor": next_cursor}

    @staticmethod
    def _encode_cursor(created_at: Any, target_id: Any) -> str:
        raw = f"{created_at.isoformat()}|{target_id}"
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
        try:
            raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("utf-8")
            created_at_text, target_id_text = raw.rsplit("|", 1)
            created_at = datetime.fromisoformat(created_at_text)
            target_id = UUID(target_id_text)
            if created_at.tzinfo is None:
                raise ValueError("cursor sem timezone")
            return created_at, target_id
        except (ValueError, UnicodeDecodeError):
            raise ValueError("cursor inválido.")

    @staticmethod
    def get_settings(cur: Any, portfolio_id: UUID) -> dict[str, Any]:
        cur.execute(
            "SELECT proximity_percent, revision FROM portfolio_private.monitoring_settings "
            "WHERE portfolio_id = %s;",
            (str(portfolio_id),),
        )
        return _settings_body(cur.fetchone())

    @staticmethod
    def _ensure_settings(cur: Any, portfolio_id: UUID) -> tuple[Any, ...]:
        cur.execute(
            "INSERT INTO portfolio_private.monitoring_settings (portfolio_id) VALUES (%s) "
            "ON CONFLICT (portfolio_id) DO NOTHING;",
            (str(portfolio_id),),
        )
        cur.execute(
            "SELECT proximity_percent, revision FROM portfolio_private.monitoring_settings "
            "WHERE portfolio_id = %s FOR UPDATE;",
            (str(portfolio_id),),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Configuração de monitoramento não pôde ser inicializada.")
        return row

    @staticmethod
    def _find_receipt(cur: Any, portfolio_id: UUID, idempotency_key: UUID, request_hash: str):
        cur.execute(
            "SELECT request_hash, response_status, response_body "
            "FROM portfolio_private.mutation_receipts WHERE portfolio_id = %s AND key = %s;",
            (str(portfolio_id), str(idempotency_key)),
        )
        row = cur.fetchone()
        if not row:
            return None
        if row[0] != request_hash:
            raise IdempotencyConflictError("Chave de idempotência reutilizada com dados diferentes.")
        return _receipt_body(row[2]), int(row[1])

    @staticmethod
    def _save_receipt(
        cur: Any,
        portfolio_id: UUID,
        idempotency_key: UUID,
        request_hash: str,
        response_status: int,
        response_body: dict[str, Any],
    ) -> None:
        cur.execute(
            "INSERT INTO portfolio_private.mutation_receipts "
            "(portfolio_id, key, request_hash, response_status, response_body) "
            "VALUES (%s, %s, %s, %s, %s);",
            (
                str(portfolio_id), str(idempotency_key), request_hash,
                response_status, json.dumps(response_body, ensure_ascii=False),
            ),
        )

    @staticmethod
    def _audit(
        cur: Any,
        portfolio_id: UUID,
        entity_kind: str,
        entity_id: UUID,
        actor_id: UUID,
        old_value: dict[str, Any] | None,
        new_value: dict[str, Any],
    ) -> None:
        cur.execute(
            "INSERT INTO portfolio_private.monitoring_changes "
            "(portfolio_id, entity_kind, entity_id, old_value, new_value, actor_id) "
            "VALUES (%s, %s, %s, %s, %s, %s);",
            (
                str(portfolio_id), entity_kind, str(entity_id),
                json.dumps(old_value, ensure_ascii=False) if old_value is not None else None,
                json.dumps(new_value, ensure_ascii=False), str(actor_id),
            ),
        )

    def create_target(
        self,
        cur: Any,
        portfolio_id: UUID,
        actor_id: UUID,
        *,
        asset_id: UUID,
        kind: str,
        price_usd: Decimal,
        active: bool,
        orientation: str | None,
        idempotency_key: UUID,
    ) -> tuple[dict[str, Any], bool]:
        normalized_kind = str(kind).lower()
        if normalized_kind not in {"buy", "sell"}:
            raise ValueError("kind deve ser buy ou sell.")
        price = _decimal(price_usd, "price_usd", positive=True, scale=MAX_TARGET_SCALE)
        orientation = orientation.strip() if orientation is not None else None
        if orientation == "":
            orientation = None
        if orientation is not None and len(orientation) > MAX_ORIENTATION_LENGTH:
            raise ValueError("orientation excede 1000 caracteres.")
        body = {
            "asset_id": str(asset_id), "kind": normalized_kind,
            "price_usd": str(price), "active": bool(active), "orientation": orientation,
        }
        request_hash = compute_request_hash("POST", "/api/v1/price-targets", body, 1)
        self._lock_portfolio(cur, portfolio_id)
        previous = self._find_receipt(cur, portfolio_id, idempotency_key, request_hash)
        if previous:
            return previous[0], True

        cur.execute(
            "SELECT id FROM portfolio_private.assets WHERE portfolio_id = %s AND id = %s AND active = true;",
            (str(portfolio_id), str(asset_id)),
        )
        if cur.fetchone() is None:
            raise ValueError("Ativo não encontrado ou inativo nesta carteira.")

        target_id = uuid4()
        cur.execute(
            "INSERT INTO portfolio_private.price_targets "
            "(id, portfolio_id, asset_id, kind, price_usd, active, orientation) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s);",
            (str(target_id), str(portfolio_id), str(asset_id), normalized_kind, str(price), bool(active), orientation),
        )
        cur.execute(
            f"SELECT {self.TARGET_COLUMNS} FROM portfolio_private.price_targets WHERE id = %s AND portfolio_id = %s;",
            (str(target_id), str(portfolio_id)),
        )
        target = _target_body(cur.fetchone())
        self._audit(cur, portfolio_id, "target", target_id, actor_id, None, target)
        self._save_receipt(cur, portfolio_id, idempotency_key, request_hash, 201, target)
        return target, False

    def update_target(
        self,
        cur: Any,
        portfolio_id: UUID,
        actor_id: UUID,
        target_id: UUID,
        changes: dict[str, Any],
        *,
        expected_version: int,
        idempotency_key: UUID,
    ) -> tuple[dict[str, Any], bool]:
        allowed = {"kind", "price_usd", "active", "orientation"}
        if not changes or set(changes) - allowed:
            raise ValueError("PATCH exige campos válidos; asset_id é imutável.")
        normalized = dict(changes)
        if "kind" in normalized:
            normalized["kind"] = str(normalized["kind"]).lower()
            if normalized["kind"] not in {"buy", "sell"}:
                raise ValueError("kind deve ser buy ou sell.")
        if "price_usd" in normalized:
            normalized["price_usd"] = str(
                _decimal(normalized["price_usd"], "price_usd", positive=True, scale=MAX_TARGET_SCALE)
            )
        if "active" in normalized and not isinstance(normalized["active"], bool):
            raise ValueError("active deve ser booleano.")
        if "orientation" in normalized:
            orientation = normalized["orientation"]
            if orientation is not None:
                orientation = str(orientation).strip() or None
                if orientation is not None and len(orientation) > MAX_ORIENTATION_LENGTH:
                    raise ValueError("orientation excede 1000 caracteres.")
            normalized["orientation"] = orientation

        path = f"/api/v1/price-targets/{target_id}"
        request_hash = compute_request_hash(
            "PATCH", path, {"changes": normalized, "expected_version": expected_version}, expected_version
        )
        self._lock_portfolio(cur, portfolio_id)
        previous = self._find_receipt(cur, portfolio_id, idempotency_key, request_hash)
        if previous:
            return previous[0], True

        cur.execute(
            f"SELECT {self.TARGET_COLUMNS} FROM portfolio_private.price_targets "
            "WHERE portfolio_id = %s AND id = %s FOR UPDATE;",
            (str(portfolio_id), str(target_id)),
        )
        old_row = cur.fetchone()
        if old_row is None:
            raise LookupError("Alvo não encontrado.")
        old = _target_body(old_row)
        if old["version"] != expected_version:
            raise RevisionConflictError(f"Conflito de versão; versão atual: {old['version']}.")

        new = {**old, **normalized}
        set_columns = []
        values: list[Any] = []
        for key, column in (
            ("kind", "kind"), ("price_usd", "price_usd"),
            ("active", "active"), ("orientation", "orientation"),
        ):
            if key in normalized:
                set_columns.append(f"{column} = %s")
                values.append(normalized[key])
        values.extend([str(portfolio_id), str(target_id), expected_version])
        cur.execute(
            "UPDATE portfolio_private.price_targets SET " + ", ".join(set_columns) +
            ", version = version + 1, updated_at = now() "
            "WHERE portfolio_id = %s AND id = %s AND version = %s;",
            tuple(values),
        )
        if cur.rowcount != 1:
            raise RevisionConflictError("Conflito de versão do alvo.")
        cur.execute(
            f"SELECT {self.TARGET_COLUMNS} FROM portfolio_private.price_targets WHERE id = %s AND portfolio_id = %s;",
            (str(target_id), str(portfolio_id)),
        )
        new = _target_body(cur.fetchone())
        self._audit(cur, portfolio_id, "target", target_id, actor_id, old, new)
        self._save_receipt(cur, portfolio_id, idempotency_key, request_hash, 200, new)
        return new, False

    def delete_target(
        self,
        cur: Any,
        portfolio_id: UUID,
        actor_id: UUID,
        target_id: UUID,
        *,
        expected_version: int | None = None,
        idempotency_key: UUID | None = None,
    ) -> tuple[dict[str, Any], bool]:
        path = f"/api/v1/price-targets/{target_id}"
        request_hash = compute_request_hash(
            "DELETE", path, {"expected_version": expected_version}, expected_version or 1
        )
        self._lock_portfolio(cur, portfolio_id)
        if idempotency_key is not None:
            previous = self._find_receipt(cur, portfolio_id, idempotency_key, request_hash)
            if previous:
                return previous[0], True

        cur.execute(
            f"SELECT {self.TARGET_COLUMNS} FROM portfolio_private.price_targets "
            "WHERE portfolio_id = %s AND id = %s FOR UPDATE;",
            (str(portfolio_id), str(target_id)),
        )
        old_row = cur.fetchone()
        if old_row is None:
            raise LookupError("Alvo não encontrado.")
        old = _target_body(old_row)
        if expected_version is not None and old["version"] != expected_version:
            raise RevisionConflictError(f"Conflito de versão; versão atual: {old['version']}.")

        cur.execute(
            "DELETE FROM portfolio_private.price_targets "
            "WHERE portfolio_id = %s AND id = %s;",
            (str(portfolio_id), str(target_id)),
        )
        result = {"id": str(target_id), "deleted": True}
        self._audit(cur, portfolio_id, "target", target_id, actor_id, old, result)
        if idempotency_key is not None:
            self._save_receipt(cur, portfolio_id, idempotency_key, request_hash, 200, result)
        return result, False


    def update_settings(
        self,
        cur: Any,
        portfolio_id: UUID,
        actor_id: UUID,
        proximity_percent: Decimal,
        *,
        expected_version: int,
        idempotency_key: UUID,
    ) -> tuple[dict[str, Any], bool]:
        percent = _decimal(
            proximity_percent, "proximity_percent", positive=False, scale=2
        )
        request_body = {"proximity_percent": str(percent), "expected_version": expected_version}
        request_hash = compute_request_hash(
            "PATCH", "/api/v1/monitoring/settings", request_body, expected_version
        )
        self._lock_portfolio(cur, portfolio_id)
        previous = self._find_receipt(cur, portfolio_id, idempotency_key, request_hash)
        if previous:
            return previous[0], True

        row = self._ensure_settings(cur, portfolio_id)
        old = _settings_body(row)
        if old["version"] != expected_version:
            raise RevisionConflictError(f"Conflito de versão; versão atual: {old['version']}.")
        cur.execute(
            "UPDATE portfolio_private.monitoring_settings "
            "SET proximity_percent = %s, revision = revision + 1, updated_at = now() "
            "WHERE portfolio_id = %s AND revision = %s;",
            (str(percent), str(portfolio_id), expected_version),
        )
        if cur.rowcount != 1:
            raise RevisionConflictError("Conflito de versão das configurações.")
        cur.execute(
            "SELECT proximity_percent, revision FROM portfolio_private.monitoring_settings WHERE portfolio_id = %s;",
            (str(portfolio_id),),
        )
        new = _settings_body(cur.fetchone())
        self._audit(cur, portfolio_id, "settings", portfolio_id, actor_id, old, new)
        self._save_receipt(cur, portfolio_id, idempotency_key, request_hash, 200, new)
        return new, False
