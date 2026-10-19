"""Rotas da API REST em /api/v1 atendendo ao contrato interfaces/http.md."""

from datetime import datetime, timezone
from decimal import Decimal
import json
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from app.auth import TokenVerifier, AuthError
from app.db import get_db_connection, lock_portfolio_for_update
from app.domain.ledger import (
    LedgerEngine,
    LedgerOperation,
    OperationKind,
    InsufficientBalanceError,
    InvalidOperationError,
)
from app.services.portfolio import (
    PortfolioService,
    compute_request_hash,
    RevisionConflictError,
    IdempotencyConflictError,
)

router = APIRouter(prefix="/api/v1", tags=["carteira"])
verifier = TokenVerifier()
portfolio_service = PortfolioService()


def get_current_user_id(authorization: Optional[str] = Header(None)) -> UUID:
    """Extrai e valida o token Bearer do cabeçalho Authorization."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Token não fornecido ou formato inválido."}},
        )
    token = authorization.split("Bearer ", 1)[1].strip()
    try:
        return verifier.verify_token(token)
    except AuthError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": {"code": "AUTH_FAILED", "message": str(e)}},
        )


class CreateAssetInput(BaseModel):
    external_id: str = Field(..., max_length=200)
    symbol: str = Field(..., max_length=30)
    name: str = Field(..., max_length=120)


class CreateOperationInput(BaseModel):
    kind: str = Field(..., description="buy, sell, deposit, withdrawal, transfer, fee")
    asset_id: UUID
    occurred_at: datetime
    quantity: Decimal
    unit_price_usd: Optional[Decimal] = None
    fee_usdt: Decimal = Decimal("0")
    transfer_ref: Optional[str] = Field(None, max_length=200)
    source_label: Optional[str] = Field(None, max_length=200)
    destination_label: Optional[str] = Field(None, max_length=200)
    note: Optional[str] = Field(None, max_length=2000)


class UpdateOperationInput(BaseModel):
    kind: Optional[str] = Field(None, description="buy, sell, deposit, withdrawal, transfer, fee")
    asset_id: Optional[UUID] = None
    occurred_at: Optional[datetime] = None
    quantity: Optional[Decimal] = None
    unit_price_usd: Optional[Decimal] = None
    fee_usdt: Optional[Decimal] = None
    transfer_ref: Optional[str] = Field(None, max_length=200)
    source_label: Optional[str] = Field(None, max_length=200)
    destination_label: Optional[str] = Field(None, max_length=200)
    note: Optional[str] = Field(None, max_length=2000)


class ReorderInput(BaseModel):
    occurred_at: datetime
    ordered_ids: List[UUID]


class ColumnPreferenceInput(BaseModel):
    hidden_columns: List[str] = Field(default_factory=list)


COLUMN_KEYS = {
    "quantity", "average", "price", "buyTarget", "variation",
    "value", "wallet", "ideal", "signal",
}


@router.patch("/ui/columns")
def update_column_preference(
    body: ColumnPreferenceInput,
    user_id: UUID = Depends(get_current_user_id),
):
    """Grava as colunas ocultas da tabela de ativos para o dono da carteira."""
    hidden = []
    for key in body.hidden_columns:
        if key in COLUMN_KEYS and key not in hidden:
            hidden.append(key)
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            cur.execute(
                "UPDATE portfolio_private.portfolios SET hidden_columns = %s::jsonb WHERE id = %s;",
                (json.dumps(hidden), str(portfolio_id)),
            )
        conn.commit()
    return {"hidden_columns": hidden}


@router.get("/portfolio")
def get_portfolio(user_id: UUID = Depends(get_current_user_id)):
    """Retorna posições atuais, totais consolidados e estado das cotações."""
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, revision, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            summary = portfolio_service.get_portfolio_summary(cur, portfolio_id)
            return summary


@router.get("/assets")
def list_assets(user_id: UUID = Depends(get_current_user_id)):
    """Lista todos os ativos cadastrados para a carteira."""
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, revision, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            cur.execute(
                """
                SELECT id, external_id, symbol, name, active 
                FROM portfolio_private.assets 
                WHERE portfolio_id = %s 
                ORDER BY (symbol = 'USDT') DESC, symbol ASC;
                """,
                (str(portfolio_id),),
            )
            rows = cur.fetchall()
            items = [
                {
                    "id": str(r[0]),
                    "external_id": r[1],
                    "symbol": r[2],
                    "name": r[3],
                    "active": r[4],
                }
                for r in rows
            ]
            return {"items": items, "revision": revision}


@router.post("/assets", status_code=status.HTTP_201_CREATED)
def create_asset(input_data: CreateAssetInput, user_id: UUID = Depends(get_current_user_id)):
    """Cadastra um novo ativo cripto na carteira."""
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, revision, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            asset_id = uuid4()
            try:
                cur.execute(
                    """
                    INSERT INTO portfolio_private.assets (id, portfolio_id, external_id, symbol, name, active)
                    VALUES (%s, %s, %s, %s, %s, true);
                    """,
                    (str(asset_id), str(portfolio_id), input_data.external_id, input_data.symbol.upper(), input_data.name),
                )
                cur.execute(
                    """
                    INSERT INTO portfolio_private.asset_price_mappings
                    (portfolio_id, asset_id, provider, provider_coin_id, status, version)
                    VALUES (%s, %s, 'coingecko', %s, 'valid', 1)
                    ON CONFLICT (portfolio_id, asset_id) DO NOTHING;
                    """,
                    (str(portfolio_id), str(asset_id), input_data.external_id),
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": {"code": "DUPLICATE_ASSET", "message": f"Ativo já cadastrado: {e}"}},
                )

            return {
                "asset": {
                    "id": str(asset_id),
                    "external_id": input_data.external_id,
                    "symbol": input_data.symbol.upper(),
                    "name": input_data.name,
                    "active": True,
                },
                "revision": revision,
            }


@router.get("/operations")
def list_operations(
    limit: int = Query(50, ge=1, le=100),
    user_id: UUID = Depends(get_current_user_id),
):
    """Lista o histórico de operações ativas ordenadas cronologicamente."""
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, revision, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            cur.execute(
                """
                SELECT o.id, o.kind, o.asset_id, a.symbol, o.occurred_at, o.order_index, 
                       o.quantity, o.unit_price_usd, o.fee_usdt, o.transfer_ref, 
                       o.source_label, o.destination_label, o.note, o.created_at, o.updated_at
                FROM portfolio_private.operations o
                JOIN portfolio_private.assets a ON a.id = o.asset_id
                WHERE o.portfolio_id = %s AND o.deleted_at IS NULL
                ORDER BY o.occurred_at DESC, o.order_index DESC, o.id DESC
                LIMIT %s;
                """,
                (str(portfolio_id), limit),
            )
            rows = cur.fetchall()
            items = []
            for r in rows:
                items.append({
                    "id": str(r[0]),
                    "kind": r[1],
                    "asset_id": str(r[2]),
                    "symbol": r[3],
                    "occurred_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
                    "order_index": r[5],
                    "quantity": str(r[6]),
                    "unit_price_usd": str(r[7]) if r[7] is not None else None,
                    "fee_usdt": str(r[8]),
                    "transfer_ref": r[9],
                    "source_label": r[10],
                    "destination_label": r[11],
                    "note": r[12],
                })
            return {"items": items, "revision": revision}


@router.post("/operations", status_code=status.HTTP_201_CREATED)
def create_operation(
    op_input: CreateOperationInput,
    response: Response,
    idempotency_key: Optional[UUID] = Header(None, alias="Idempotency-Key"),
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user_id: UUID = Depends(get_current_user_id),
):
    """Registra uma nova operação financeira executando replay e validação atômica."""
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail={"error": {"code": "MISSING_IDEMPOTENCY_KEY", "message": "Cabeçalho Idempotency-Key é obrigatório."}},
        )

    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, current_rev, usdt_id = portfolio_service.get_or_create_portfolio(cur, user_id)
            # Adquire Lock de Linha
            _, locked_rev = lock_portfolio_for_update(cur, portfolio_id)

            req_hash = compute_request_hash("POST", "/api/v1/operations", op_input.model_dump(mode="json"), locked_rev)

            # Verifica recibo de idempotência
            cur.execute(
                "SELECT request_hash, response_status, response_body FROM portfolio_private.mutation_receipts WHERE portfolio_id = %s AND key = %s;",
                (str(portfolio_id), str(idempotency_key)),
            )
            receipt = cur.fetchone()
            if receipt:
                prev_hash, prev_status, prev_body = receipt
                if prev_hash != req_hash:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"error": {"code": "IDEMPOTENCY_CONFLICT", "message": "Chave de idempotência reutilizada com dados diferentes."}},
                    )
                response.headers["Idempotency-Replayed"] = "true"
                response.status_code = prev_status
                return prev_body

            # Valida revisão If-Match
            if if_match:
                expected_rev = if_match.strip('"')
                if str(locked_rev) != expected_rev:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"error": {"code": "REVISION_CONFLICT", "message": f"Conflito de versão. Versão atual: {locked_rev}"}},
                    )

            # Carrega operações existentes ativas
            cur.execute(
                """
                SELECT o.id, o.asset_id, a.symbol, o.kind, o.occurred_at, o.order_index, 
                       o.quantity, o.unit_price_usd, o.fee_usdt, o.transfer_ref, 
                       o.source_label, o.destination_label, o.note
                FROM portfolio_private.operations o
                JOIN portfolio_private.assets a ON a.id = o.asset_id
                WHERE o.portfolio_id = %s AND o.deleted_at IS NULL
                ORDER BY o.occurred_at ASC, o.order_index ASC, o.id ASC;
                """,
                (str(portfolio_id),),
            )
            existing_rows = cur.fetchall()

            ops_list: List[LedgerOperation] = []
            for r in existing_rows:
                ops_list.append(LedgerOperation(
                    id=UUID(str(r[0])),
                    asset_id=UUID(str(r[1])),
                    asset_symbol=str(r[2]),
                    kind=OperationKind(str(r[3])),
                    occurred_at=r[4],
                    order_index=int(r[5]),
                    quantity=Decimal(str(r[6])),
                    unit_price_usd=Decimal(str(r[7])) if r[7] is not None else None,
                    fee_usdt=Decimal(str(r[8])),
                    transfer_ref=r[9],
                    source_label=r[10],
                    destination_label=r[11],
                    note=r[12],
                ))

            # Obtém símbolo do ativo candidado
            cur.execute("SELECT symbol FROM portfolio_private.assets WHERE id = %s;", (str(op_input.asset_id),))
            sym_row = cur.fetchone()
            if not sym_row:
                raise HTTPException(status_code=404, detail={"error": {"code": "ASSET_NOT_FOUND", "message": "Ativo não encontrado."}})
            cand_symbol = str(sym_row[0])

            new_op_id = uuid4()
            candidate_op = LedgerOperation(
                id=new_op_id,
                asset_id=op_input.asset_id,
                asset_symbol=cand_symbol,
                kind=OperationKind(op_input.kind),
                occurred_at=op_input.occurred_at,
                order_index=len(ops_list),
                quantity=op_input.quantity,
                unit_price_usd=op_input.unit_price_usd,
                fee_usdt=op_input.fee_usdt,
                transfer_ref=op_input.transfer_ref,
                source_label=op_input.source_label,
                destination_label=op_input.destination_label,
                note=op_input.note,
            )
            ops_list.append(candidate_op)

            # Executa Replay de Histórico pelo Motor Contábil
            try:
                new_projection = LedgerEngine.replay(ops_list, usdt_id)
            except InsufficientBalanceError as e:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": {"code": "INSUFFICIENT_BALANCE", "message": str(e)}},
                )
            except InvalidOperationError as e:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": {"code": "INVALID_OPERATION", "message": str(e)}},
                )

            # Persistência Atômica
            new_rev = locked_rev + 1

            # 1. Insere Operação
            cur.execute(
                """
                INSERT INTO portfolio_private.operations
                (id, portfolio_id, asset_id, kind, occurred_at, order_index, quantity, unit_price_usd, fee_usdt, transfer_ref, source_label, destination_label, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    str(new_op_id), str(portfolio_id), str(op_input.asset_id), op_input.kind,
                    op_input.occurred_at, candidate_op.order_index, str(op_input.quantity),
                    str(op_input.unit_price_usd) if op_input.unit_price_usd else None,
                    str(op_input.fee_usdt), op_input.transfer_ref, op_input.source_label,
                    op_input.destination_label, op_input.note
                ),
            )

            # 2. Atualiza Projeções
            cur.execute(
                """
                UPDATE portfolio_private.portfolio_projection
                SET cash_usdt = %s, deposits_usdt = %s, withdrawals_usdt = %s, 
                    standalone_expenses_usdt = %s, realized_sales_usd = %s, revision = %s
                WHERE portfolio_id = %s;
                """,
                (
                    str(new_projection.cash_usdt), str(new_projection.deposits_usdt),
                    str(new_projection.withdrawals_usdt), str(new_projection.standalone_expenses_usdt),
                    str(new_projection.realized_sales_usd), new_rev, str(portfolio_id)
                ),
            )

            # Atualiza position_projections
            for aid, pos in new_projection.positions.items():
                cur.execute(
                    """
                    INSERT INTO portfolio_private.position_projections
                    (portfolio_id, asset_id, quantity, remaining_cost_usd, realized_sales_usd, revision)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (portfolio_id, asset_id) DO UPDATE
                    SET quantity = EXCLUDED.quantity, remaining_cost_usd = EXCLUDED.remaining_cost_usd,
                        realized_sales_usd = EXCLUDED.realized_sales_usd, revision = EXCLUDED.revision;
                    """,
                    (str(portfolio_id), str(aid), str(pos.quantity), str(pos.remaining_cost_usd), str(pos.realized_sales_usd), new_rev),
                )

            # 3. Atualiza Revisão da Carteira
            cur.execute(
                "UPDATE portfolio_private.portfolios SET revision = %s WHERE id = %s;",
                (new_rev, str(portfolio_id)),
            )

            # 4. Registra Auditoria
            cur.execute(
                """
                INSERT INTO portfolio_private.operation_audit
                (portfolio_id, operation_id, action, actor_id, after_data, revision)
                VALUES (%s, %s, 'insert', %s, %s, %s);
                """,
                (str(portfolio_id), str(new_op_id), str(user_id), json.dumps(op_input.model_dump(mode="json")), new_rev),
            )

            result_body = {
                "operation": {
                    "id": str(new_op_id),
                    "kind": op_input.kind,
                    "asset_id": str(op_input.asset_id),
                    "symbol": cand_symbol,
                    "occurred_at": op_input.occurred_at.isoformat(),
                    "quantity": str(op_input.quantity),
                    "unit_price_usd": str(op_input.unit_price_usd) if op_input.unit_price_usd else None,
                    "fee_usdt": str(op_input.fee_usdt),
                },
                "revision": new_rev,
            }

            # 5. Salva Recibo de Idempotência
            cur.execute(
                """
                INSERT INTO portfolio_private.mutation_receipts
                (portfolio_id, key, request_hash, response_status, response_body)
                VALUES (%s, %s, %s, 201, %s);
                """,
                (str(portfolio_id), str(idempotency_key), req_hash, json.dumps(result_body)),
            )

            conn.commit()
            return result_body


@router.patch("/operations/{operation_id}")
@router.put("/operations/{operation_id}")
def update_operation(
    operation_id: UUID,
    op_input: UpdateOperationInput,
    response: Response,
    request: Request,
    idempotency_key: Optional[UUID] = Header(None, alias="Idempotency-Key"),
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user_id: UUID = Depends(get_current_user_id),
):
    """Atualiza uma operação existente com recálculo atômico e verificação de integridade."""
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail={"error": {"code": "MISSING_IDEMPOTENCY_KEY", "message": "Cabeçalho Idempotency-Key é obrigatório."}},
        )

    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, current_rev, usdt_id = portfolio_service.get_or_create_portfolio(cur, user_id)
            # Adquire Lock de Linha
            _, locked_rev = lock_portfolio_for_update(cur, portfolio_id)

            req_hash = compute_request_hash(
                request.method,
                f"/api/v1/operations/{operation_id}",
                op_input.model_dump(mode="json"),
                locked_rev,
            )

            # Verifica recibo de idempotência
            cur.execute(
                "SELECT request_hash, response_status, response_body FROM portfolio_private.mutation_receipts WHERE portfolio_id = %s AND key = %s;",
                (str(portfolio_id), str(idempotency_key)),
            )
            receipt = cur.fetchone()
            if receipt:
                prev_hash, prev_status, prev_body = receipt
                if prev_hash != req_hash:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"error": {"code": "IDEMPOTENCY_CONFLICT", "message": "Chave de idempotência reutilizada com dados diferentes."}},
                    )
                response.headers["Idempotency-Replayed"] = "true"
                response.status_code = prev_status
                return prev_body

            # Valida revisão If-Match
            if if_match:
                expected_rev = if_match.strip('"')
                if str(locked_rev) != expected_rev:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"error": {"code": "REVISION_CONFLICT", "message": f"Conflito de versão. Versão atual: {locked_rev}"}},
                    )

            # Busca a operação existente
            cur.execute(
                """
                SELECT o.id, o.asset_id, a.symbol, o.kind, o.occurred_at, o.order_index, 
                       o.quantity, o.unit_price_usd, o.fee_usdt, o.transfer_ref, 
                       o.source_label, o.destination_label, o.note
                FROM portfolio_private.operations o
                JOIN portfolio_private.assets a ON a.id = o.asset_id
                WHERE o.portfolio_id = %s AND o.id = %s AND o.deleted_at IS NULL;
                """,
                (str(portfolio_id), str(operation_id)),
            )
            existing_row = cur.fetchone()
            if not existing_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"code": "NOT_FOUND", "message": "Operação não encontrada."}},
                )

            before_data = {
                "id": str(existing_row[0]),
                "asset_id": str(existing_row[1]),
                "symbol": str(existing_row[2]),
                "kind": str(existing_row[3]),
                "occurred_at": existing_row[4].isoformat() if hasattr(existing_row[4], "isoformat") else str(existing_row[4]),
                "order_index": existing_row[5],
                "quantity": str(existing_row[6]),
                "unit_price_usd": str(existing_row[7]) if existing_row[7] is not None else None,
                "fee_usdt": str(existing_row[8]),
                "transfer_ref": existing_row[9],
                "source_label": existing_row[10],
                "destination_label": existing_row[11],
                "note": existing_row[12],
            }

            new_kind_str = op_input.kind if op_input.kind is not None else str(existing_row[3])
            try:
                new_kind = OperationKind(new_kind_str)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": {"code": "INVALID_OPERATION", "message": f"Tipo de operação inválido: {new_kind_str}"}},
                )

            new_asset_id = op_input.asset_id if op_input.asset_id is not None else UUID(str(existing_row[1]))
            new_occurred_at = op_input.occurred_at if op_input.occurred_at is not None else existing_row[4]
            new_quantity = op_input.quantity if op_input.quantity is not None else Decimal(str(existing_row[6]))
            if new_quantity <= Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": {"code": "INVALID_OPERATION", "message": "Quantidade deve ser estritamente positiva."}},
                )

            if new_kind in (OperationKind.BUY, OperationKind.SELL):
                if "unit_price_usd" in op_input.model_fields_set:
                    new_unit_price = op_input.unit_price_usd
                else:
                    new_unit_price = Decimal(str(existing_row[7])) if existing_row[7] is not None else None

                if new_unit_price is None or new_unit_price <= Decimal("0"):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={"error": {"code": "INVALID_OPERATION", "message": "Operação de compra ou venda requer preço unitário positivo."}},
                    )
            else:
                new_unit_price = None

            if "fee_usdt" in op_input.model_fields_set:
                new_fee_usdt = op_input.fee_usdt if op_input.fee_usdt is not None else Decimal("0")
            else:
                new_fee_usdt = Decimal(str(existing_row[8])) if existing_row[8] is not None else Decimal("0")
            if new_fee_usdt < Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": {"code": "INVALID_OPERATION", "message": "Taxa em USDT não pode ser negativa."}},
                )

            if new_kind in (OperationKind.DEPOSIT, OperationKind.WITHDRAWAL, OperationKind.FEE):
                if new_asset_id != usdt_id:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={"error": {"code": "INVALID_OPERATION", "message": "Depósitos, saques e taxas avulsas devem ser exclusivamente em USDT."}},
                    )
            elif new_kind in (OperationKind.BUY, OperationKind.SELL):
                if new_asset_id == usdt_id:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={"error": {"code": "INVALID_OPERATION", "message": "Não é permitido negociar USDT contra USDT."}},
                    )

            cur.execute(
                "SELECT symbol FROM portfolio_private.assets WHERE id = %s AND portfolio_id = %s;",
                (str(new_asset_id), str(portfolio_id)),
            )
            sym_row = cur.fetchone()
            if not sym_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"code": "ASSET_NOT_FOUND", "message": "Ativo não encontrado."}},
                )
            new_symbol = str(sym_row[0])

            new_transfer_ref = op_input.transfer_ref if "transfer_ref" in op_input.model_fields_set else existing_row[9]
            new_source_label = op_input.source_label if "source_label" in op_input.model_fields_set else existing_row[10]
            new_destination_label = op_input.destination_label if "destination_label" in op_input.model_fields_set else existing_row[11]
            new_note = op_input.note if "note" in op_input.model_fields_set else existing_row[12]

            cur.execute(
                """
                SELECT o.id, o.asset_id, a.symbol, o.kind, o.occurred_at, o.order_index, 
                       o.quantity, o.unit_price_usd, o.fee_usdt, o.transfer_ref, 
                       o.source_label, o.destination_label, o.note
                FROM portfolio_private.operations o
                JOIN portfolio_private.assets a ON a.id = o.asset_id
                WHERE o.portfolio_id = %s AND o.deleted_at IS NULL
                ORDER BY o.occurred_at ASC, o.order_index ASC, o.id ASC;
                """,
                (str(portfolio_id),),
            )
            all_rows = cur.fetchall()

            ops_list: List[LedgerOperation] = []
            for r in all_rows:
                r_id = UUID(str(r[0]))
                if r_id == operation_id:
                    candidate_op = LedgerOperation(
                        id=operation_id,
                        asset_id=new_asset_id,
                        asset_symbol=new_symbol,
                        kind=new_kind,
                        occurred_at=new_occurred_at,
                        order_index=int(r[5]),
                        quantity=new_quantity,
                        unit_price_usd=new_unit_price,
                        fee_usdt=new_fee_usdt,
                        transfer_ref=new_transfer_ref,
                        source_label=new_source_label,
                        destination_label=new_destination_label,
                        note=new_note,
                    )
                    ops_list.append(candidate_op)
                else:
                    ops_list.append(LedgerOperation(
                        id=r_id,
                        asset_id=UUID(str(r[1])),
                        asset_symbol=str(r[2]),
                        kind=OperationKind(str(r[3])),
                        occurred_at=r[4],
                        order_index=int(r[5]),
                        quantity=Decimal(str(r[6])),
                        unit_price_usd=Decimal(str(r[7])) if r[7] is not None else None,
                        fee_usdt=Decimal(str(r[8])),
                        transfer_ref=r[9],
                        source_label=r[10],
                        destination_label=r[11],
                        note=r[12],
                    ))

            try:
                new_projection = LedgerEngine.replay(ops_list, usdt_id)
            except InsufficientBalanceError as e:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": {"code": "INSUFFICIENT_BALANCE", "message": str(e)}},
                )
            except InvalidOperationError as e:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": {"code": "INVALID_OPERATION", "message": str(e)}},
                )

            new_rev = locked_rev + 1

            try:
                cur.execute(
                    """
                    UPDATE portfolio_private.operations
                    SET asset_id = %s,
                        kind = %s,
                        occurred_at = %s,
                        quantity = %s,
                        unit_price_usd = %s,
                        fee_usdt = %s,
                        transfer_ref = %s,
                        source_label = %s,
                        destination_label = %s,
                        note = %s,
                        updated_at = now()
                    WHERE id = %s AND portfolio_id = %s;
                    """,
                    (
                        str(new_asset_id), new_kind.value, new_occurred_at,
                        str(new_quantity), str(new_unit_price) if new_unit_price is not None else None,
                        str(new_fee_usdt), new_transfer_ref, new_source_label,
                        new_destination_label, new_note, str(operation_id), str(portfolio_id),
                    ),
                )
            except Exception as e:
                conn.rollback()
                if "uq_operations_transfer_ref" in str(e):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"error": {"code": "DUPLICATE_REFERENCE", "message": "Referência de transferência já utilizada."}},
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "DATABASE_ERROR", "message": str(e)}},
                )

            cur.execute(
                """
                UPDATE portfolio_private.portfolio_projection
                SET cash_usdt = %s, deposits_usdt = %s, withdrawals_usdt = %s, 
                    standalone_expenses_usdt = %s, realized_sales_usd = %s, revision = %s
                WHERE portfolio_id = %s;
                """,
                (
                    str(new_projection.cash_usdt), str(new_projection.deposits_usdt),
                    str(new_projection.withdrawals_usdt), str(new_projection.standalone_expenses_usdt),
                    str(new_projection.realized_sales_usd), new_rev, str(portfolio_id)
                ),
            )

            cur.execute(
                """
                UPDATE portfolio_private.position_projections
                SET quantity = 0, remaining_cost_usd = 0, realized_sales_usd = 0, revision = %s
                WHERE portfolio_id = %s;
                """,
                (new_rev, str(portfolio_id)),
            )

            for aid, pos in new_projection.positions.items():
                cur.execute(
                    """
                    INSERT INTO portfolio_private.position_projections
                    (portfolio_id, asset_id, quantity, remaining_cost_usd, realized_sales_usd, revision)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (portfolio_id, asset_id) DO UPDATE
                    SET quantity = EXCLUDED.quantity, remaining_cost_usd = EXCLUDED.remaining_cost_usd,
                        realized_sales_usd = EXCLUDED.realized_sales_usd, revision = EXCLUDED.revision;
                    """,
                    (str(portfolio_id), str(aid), str(pos.quantity), str(pos.remaining_cost_usd), str(pos.realized_sales_usd), new_rev),
                )

            cur.execute(
                "UPDATE portfolio_private.portfolios SET revision = %s WHERE id = %s;",
                (new_rev, str(portfolio_id)),
            )

            after_data = {
                "id": str(operation_id),
                "asset_id": str(new_asset_id),
                "symbol": new_symbol,
                "kind": new_kind.value,
                "occurred_at": new_occurred_at.isoformat() if hasattr(new_occurred_at, "isoformat") else str(new_occurred_at),
                "order_index": existing_row[5],
                "quantity": str(new_quantity),
                "unit_price_usd": str(new_unit_price) if new_unit_price is not None else None,
                "fee_usdt": str(new_fee_usdt),
                "transfer_ref": new_transfer_ref,
                "source_label": new_source_label,
                "destination_label": new_destination_label,
                "note": new_note,
            }

            cur.execute(
                """
                INSERT INTO portfolio_private.operation_audit
                (portfolio_id, operation_id, action, actor_id, before_data, after_data, revision)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (str(portfolio_id), str(operation_id), "update", str(user_id), json.dumps(before_data), json.dumps(after_data), new_rev),
            )

            result_body = {
                "operation": after_data,
                "revision": new_rev,
            }

            cur.execute(
                """
                INSERT INTO portfolio_private.mutation_receipts
                (portfolio_id, key, request_hash, response_status, response_body)
                VALUES (%s, %s, %s, 200, %s);
                """,
                (str(portfolio_id), str(idempotency_key), req_hash, json.dumps(result_body)),
            )

            conn.commit()
            return result_body


@router.delete("/operations/{operation_id}")
def delete_operation(
    operation_id: UUID,
    response: Response,
    request: Request,
    idempotency_key: Optional[UUID] = Header(None, alias="Idempotency-Key"),
    if_match: Optional[str] = Header(None, alias="If-Match"),
    user_id: UUID = Depends(get_current_user_id),
):
    """Exclui (soft delete) uma operação com recálculo atômico e verificação de integridade."""
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, current_rev, usdt_id = portfolio_service.get_or_create_portfolio(cur, user_id)
            _, locked_rev = lock_portfolio_for_update(cur, portfolio_id)

            if idempotency_key:
                req_hash = compute_request_hash(
                    "DELETE",
                    f"/api/v1/operations/{operation_id}",
                    {},
                    locked_rev,
                )
                cur.execute(
                    "SELECT request_hash, response_status, response_body FROM portfolio_private.mutation_receipts WHERE portfolio_id = %s AND key = %s;",
                    (str(portfolio_id), str(idempotency_key)),
                )
                receipt = cur.fetchone()
                if receipt:
                    prev_hash, prev_status, prev_body = receipt
                    if prev_hash != req_hash:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail={"error": {"code": "IDEMPOTENCY_CONFLICT", "message": "Chave de idempotência reutilizada com dados diferentes."}},
                        )
                    response.headers["Idempotency-Replayed"] = "true"
                    response.status_code = prev_status
                    return prev_body

            if if_match:
                expected_rev = if_match.strip('"')
                if str(locked_rev) != expected_rev:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"error": {"code": "REVISION_CONFLICT", "message": f"Conflito de versão. Versão atual: {locked_rev}"}},
                    )

            cur.execute(
                """
                SELECT o.id, o.asset_id, a.symbol, o.kind, o.occurred_at, o.order_index, 
                       o.quantity, o.unit_price_usd, o.fee_usdt, o.transfer_ref, 
                       o.source_label, o.destination_label, o.note
                FROM portfolio_private.operations o
                JOIN portfolio_private.assets a ON a.id = o.asset_id
                WHERE o.portfolio_id = %s AND o.id = %s AND o.deleted_at IS NULL;
                """,
                (str(portfolio_id), str(operation_id)),
            )
            existing_row = cur.fetchone()
            if not existing_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"code": "NOT_FOUND", "message": "Operação não encontrada."}},
                )

            before_data = {
                "id": str(existing_row[0]),
                "asset_id": str(existing_row[1]),
                "symbol": str(existing_row[2]),
                "kind": str(existing_row[3]),
                "occurred_at": existing_row[4].isoformat() if hasattr(existing_row[4], "isoformat") else str(existing_row[4]),
                "order_index": existing_row[5],
                "quantity": str(existing_row[6]),
                "unit_price_usd": str(existing_row[7]) if existing_row[7] is not None else None,
                "fee_usdt": str(existing_row[8]),
                "transfer_ref": existing_row[9],
                "source_label": existing_row[10],
                "destination_label": existing_row[11],
                "note": existing_row[12],
            }

            cur.execute(
                """
                SELECT o.id, o.asset_id, a.symbol, o.kind, o.occurred_at, o.order_index, 
                       o.quantity, o.unit_price_usd, o.fee_usdt, o.transfer_ref, 
                       o.source_label, o.destination_label, o.note
                FROM portfolio_private.operations o
                JOIN portfolio_private.assets a ON a.id = o.asset_id
                WHERE o.portfolio_id = %s AND o.deleted_at IS NULL AND o.id != %s
                ORDER BY o.occurred_at ASC, o.order_index ASC, o.id ASC;
                """,
                (str(portfolio_id), str(operation_id)),
            )
            remaining_rows = cur.fetchall()

            ops_list: List[LedgerOperation] = []
            for r in remaining_rows:
                ops_list.append(LedgerOperation(
                    id=UUID(str(r[0])),
                    asset_id=UUID(str(r[1])),
                    asset_symbol=str(r[2]),
                    kind=OperationKind(str(r[3])),
                    occurred_at=r[4],
                    order_index=int(r[5]),
                    quantity=Decimal(str(r[6])),
                    unit_price_usd=Decimal(str(r[7])) if r[7] is not None else None,
                    fee_usdt=Decimal(str(r[8])),
                    transfer_ref=r[9],
                    source_label=r[10],
                    destination_label=r[11],
                    note=r[12],
                ))

            try:
                new_projection = LedgerEngine.replay(ops_list, usdt_id)
            except InsufficientBalanceError as e:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": {"code": "INSUFFICIENT_BALANCE", "message": f"Não é possível excluir esta operação pois operações posteriores dependem do saldo gerado por ela: {e}"}},
                )
            except InvalidOperationError as e:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": {"code": "INVALID_OPERATION", "message": str(e)}},
                )

            new_rev = locked_rev + 1

            cur.execute(
                """
                UPDATE portfolio_private.operations
                SET deleted_at = now(), updated_at = now()
                WHERE id = %s AND portfolio_id = %s;
                """,
                (str(operation_id), str(portfolio_id)),
            )

            cur.execute(
                """
                UPDATE portfolio_private.portfolio_projection
                SET cash_usdt = %s, deposits_usdt = %s, withdrawals_usdt = %s, 
                    standalone_expenses_usdt = %s, realized_sales_usd = %s, revision = %s
                WHERE portfolio_id = %s;
                """,
                (
                    str(new_projection.cash_usdt), str(new_projection.deposits_usdt),
                    str(new_projection.withdrawals_usdt), str(new_projection.standalone_expenses_usdt),
                    str(new_projection.realized_sales_usd), new_rev, str(portfolio_id)
                ),
            )

            cur.execute(
                """
                UPDATE portfolio_private.position_projections
                SET quantity = 0, remaining_cost_usd = 0, realized_sales_usd = 0, revision = %s
                WHERE portfolio_id = %s;
                """,
                (new_rev, str(portfolio_id)),
            )

            for aid, pos in new_projection.positions.items():
                cur.execute(
                    """
                    INSERT INTO portfolio_private.position_projections
                    (portfolio_id, asset_id, quantity, remaining_cost_usd, realized_sales_usd, revision)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (portfolio_id, asset_id) DO UPDATE
                    SET quantity = EXCLUDED.quantity, remaining_cost_usd = EXCLUDED.remaining_cost_usd,
                        realized_sales_usd = EXCLUDED.realized_sales_usd, revision = EXCLUDED.revision;
                    """,
                    (str(portfolio_id), str(aid), str(pos.quantity), str(pos.remaining_cost_usd), str(pos.realized_sales_usd), new_rev),
                )

            cur.execute(
                "UPDATE portfolio_private.portfolios SET revision = %s WHERE id = %s;",
                (new_rev, str(portfolio_id)),
            )

            cur.execute(
                """
                INSERT INTO portfolio_private.operation_audit
                (portfolio_id, operation_id, action, actor_id, before_data, after_data, revision)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (str(portfolio_id), str(operation_id), "delete", str(user_id), json.dumps(before_data), None, new_rev),
            )

            result_body = {
                "id": str(operation_id),
                "deleted": True,
                "revision": new_rev,
            }

            if idempotency_key:
                req_hash = compute_request_hash(
                    "DELETE",
                    f"/api/v1/operations/{operation_id}",
                    {},
                    locked_rev,
                )
                cur.execute(
                    """
                    INSERT INTO portfolio_private.mutation_receipts
                    (portfolio_id, key, request_hash, response_status, response_body)
                    VALUES (%s, %s, %s, 200, %s);
                    """,
                    (str(portfolio_id), str(idempotency_key), req_hash, json.dumps(result_body)),
                )

            conn.commit()
            return result_body
