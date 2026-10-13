"""Configuração do Gemini e leitura assistida de lançamentos e alvos."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.routes.api import get_current_user_id, portfolio_service
from app.services.ai_import import (
    DEFAULT_MODEL,
    OPERATION_SCHEMA,
    TARGET_SCHEMA,
    AiImportError,
    GeminiClient,
    fallback_parse_operations,
    fallback_parse_targets,
    key_hint,
    normalize_operations,
    normalize_targets,
    operation_instruction,
    sniff_image,
    target_instruction,
    validate_model,
)

router = APIRouter(prefix="/api/v1/ai", tags=["ia"])

MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_TEXT_CHARS = 80_000
HTTP_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


class AiSettingsInput(BaseModel):
    api_key: str | None = Field(default=None, max_length=300)
    model: str | None = Field(default=None, max_length=80)
    clear_key: bool = False


def _error(http_status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"error": {"code": code, "message": message}})


def _settings_row(cur: Any, portfolio_id: UUID) -> tuple[str | None, str]:
    cur.execute(
        "SELECT gemini_api_key, gemini_model FROM portfolio_private.portfolios WHERE id = %s;",
        (str(portfolio_id),),
    )
    row = cur.fetchone()
    if row is None:
        return None, DEFAULT_MODEL
    return row[0] or None, row[1] or DEFAULT_MODEL


def _public_settings(api_key: str | None, model: str) -> dict[str, Any]:
    return {"configured": bool(api_key), "model": model, "key_hint": key_hint(api_key)}


def _assets(cur: Any, portfolio_id: UUID) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT id, symbol, name
        FROM portfolio_private.assets
        WHERE portfolio_id = %s AND active = true
        ORDER BY symbol ASC;
        """,
        (str(portfolio_id),),
    )
    return [{"id": row[0], "symbol": row[1], "name": row[2]} for row in cur.fetchall()]


def _buy_targets(cur: Any, portfolio_id: UUID) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT id, asset_id, kind, price_usd, active, orientation, version
        FROM portfolio_private.price_targets
        WHERE portfolio_id = %s AND kind = 'buy'
        ORDER BY version DESC;
        """,
        (str(portfolio_id),),
    )
    return [
        {
            "id": row[0],
            "asset_id": row[1],
            "kind": row[2],
            "price_usd": row[3],
            "active": row[4],
            "orientation": row[5],
            "version": row[6],
        }
        for row in cur.fetchall()
    ]


def _material(text: str, upload: UploadFile | None) -> tuple[str, tuple[str, bytes] | None]:
    pasted = (text or "").strip()
    if len(pasted) > MAX_TEXT_CHARS:
        raise _error(HTTP_422, "MATERIAL_TOO_LARGE", "O texto passou de 80 mil caracteres.")
    image = None
    if upload is not None and upload.filename:
        data = upload.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise _error(HTTP_422, "MATERIAL_TOO_LARGE", "O arquivo passou de 4 MB.")
        mime = sniff_image(data)
        if mime:
            image = (mime, data)
        else:
            decoded = data.decode("utf-8", errors="replace").strip()
            if not decoded:
                raise _error(HTTP_422, "MATERIAL_EMPTY", "O arquivo não tem texto legível.")
            pasted = f"{pasted}\n\n{decoded}".strip() if pasted else decoded
            if len(pasted) > MAX_TEXT_CHARS:
                raise _error(HTTP_422, "MATERIAL_TOO_LARGE", "O texto passou de 80 mil caracteres.")
    if not pasted and image is None:
        raise _error(
            HTTP_422,
            "MATERIAL_EMPTY",
            "Cole um texto ou envie um CSV, uma tabela ou uma imagem.",
        )
    return pasted, image


def _configured_context(cur: Any, portfolio_id: UUID) -> tuple[str, str, list[dict[str, Any]]]:
    api_key, model = _settings_row(cur, portfolio_id)
    if not api_key:
        raise _error(
            HTTP_422,
            "AI_NOT_CONFIGURED",
            "Salve a chave do Gemini na engrenagem de IA antes de ler o material.",
        )
    return api_key, model, _assets(cur, portfolio_id)


def _generate(api_key: str, model: str, instruction: str, schema: dict[str, Any], material: str, image):
    try:
        return GeminiClient(api_key, validate_model(model)).generate(instruction, material, image, schema)
    except AiImportError as exc:
        if exc.code in {"AI_UNREADABLE", "AI_REJECTED", "INVALID_MODEL", "AI_CREDITS_DEPLETED"}:
            http_status = HTTP_422
        elif exc.code == "AI_BUSY":
            http_status = status.HTTP_429_TOO_MANY_REQUESTS
        else:
            http_status = status.HTTP_502_BAD_GATEWAY
        raise _error(http_status, exc.code, str(exc))


@router.get("/settings")
def get_ai_settings(user_id: UUID = Depends(get_current_user_id)):
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            api_key, model = _settings_row(cur, portfolio_id)
            return _public_settings(api_key, model)


@router.put("/settings")
def put_ai_settings(body: AiSettingsInput, user_id: UUID = Depends(get_current_user_id)):
    try:
        model = validate_model(body.model)
    except AiImportError as exc:
        raise _error(HTTP_422, exc.code, str(exc))
    replacement = (body.api_key or "").strip()
    if replacement and len(replacement) < 20:
        raise _error(HTTP_422, "INVALID_API_KEY", "A chave informada está curta demais.")
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            if body.clear_key:
                cur.execute(
                    "UPDATE portfolio_private.portfolios SET gemini_api_key = NULL, gemini_model = %s WHERE id = %s;",
                    (model, str(portfolio_id)),
                )
            elif replacement:
                cur.execute(
                    "UPDATE portfolio_private.portfolios SET gemini_api_key = %s, gemini_model = %s WHERE id = %s;",
                    (replacement, model, str(portfolio_id)),
                )
            else:
                cur.execute(
                    "UPDATE portfolio_private.portfolios SET gemini_model = %s WHERE id = %s;",
                    (model, str(portfolio_id)),
                )
            api_key, stored_model = _settings_row(cur, portfolio_id)
        conn.commit()
    return _public_settings(api_key, stored_model)


@router.post("/test")
def test_ai_connection(user_id: UUID = Depends(get_current_user_id)):
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            api_key, model = _settings_row(cur, portfolio_id)
    if not api_key:
        raise _error(HTTP_422, "AI_NOT_CONFIGURED", "Nenhuma chave da API Gemini está configurada.")
    try:
        GeminiClient(api_key, validate_model(model)).generate(
            "Responda apenas com a palavra OK.",
            "",
            None,
            {"type": "OBJECT", "properties": {"status": {"type": "STRING"}}},
        )
        return {"ok": True, "message": "Conexão com o Gemini realizada com sucesso!"}
    except AiImportError as exc:
        if exc.code in {"AI_UNREADABLE", "AI_REJECTED", "INVALID_MODEL", "AI_CREDITS_DEPLETED"}:
            http_status = HTTP_422
        elif exc.code == "AI_BUSY":
            http_status = status.HTTP_429_TOO_MANY_REQUESTS
        else:
            http_status = status.HTTP_502_BAD_GATEWAY
        raise _error(http_status, exc.code, str(exc))


@router.post("/operations/preview")
def preview_operations(
    text: str = Form(""),
    upload: UploadFile | None = File(None),
    user_id: UUID = Depends(get_current_user_id),
):
    material, image = _material(text, upload)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            api_key, model, assets = _configured_context(cur, portfolio_id)
    try:
        payload = _generate(api_key, model, operation_instruction(assets), OPERATION_SCHEMA, material, image)
        return normalize_operations(payload, assets)
    except HTTPException as exc:
        if image is None and material:
            fallback = fallback_parse_operations(material, assets)
            ready_count = sum(1 for item in fallback.get("items", []) if item.get("ready"))
            if ready_count > 0:
                err_detail = exc.detail if isinstance(exc.detail, dict) else {}
                err_info = err_detail.get("error", {}) if isinstance(err_detail, dict) else {}
                reason = err_info.get("message") if isinstance(err_info, dict) else str(exc.detail)
                fallback["summary"] = (
                    f"Modo de contingência local: {ready_count} lançamento(s) lidos diretamente. "
                    f"(Gemini: {reason}). Revise os dados antes de confirmar."
                )
                return fallback
        raise


@router.post("/targets/preview")
def preview_targets(
    text: str = Form(""),
    upload: UploadFile | None = File(None),
    user_id: UUID = Depends(get_current_user_id),
):
    material, image = _material(text, upload)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            api_key, model, assets = _configured_context(cur, portfolio_id)
            targets = _buy_targets(cur, portfolio_id)
    try:
        payload = _generate(api_key, model, target_instruction(assets), TARGET_SCHEMA, material, image)
        return normalize_targets(payload, assets, targets)
    except HTTPException as exc:
        if image is None and material:
            fallback = fallback_parse_targets(material, assets, targets)
            ready_count = sum(1 for item in fallback.get("items", []) if item.get("ready"))
            if ready_count > 0:
                err_detail = exc.detail if isinstance(exc.detail, dict) else {}
                err_info = err_detail.get("error", {}) if isinstance(err_detail, dict) else {}
                reason = err_info.get("message") if isinstance(err_info, dict) else str(exc.detail)
                fallback["summary"] = (
                    f"Modo de contingência local: {ready_count} alvo(s) lidos diretamente. "
                    f"(Gemini: {reason}). Revise os dados antes de confirmar."
                )
                return fallback
        raise
