"""Rotas da API REST para metas de alocação e rebalanceamento."""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.domain.allocation import InvalidAllocationSumError
from app.routes.api import get_current_user_id, portfolio_service
from app.services.allocation import AllocationService

router = APIRouter(prefix="/api/v1/allocations", tags=["allocations"])
allocation_service = AllocationService(portfolio_service=portfolio_service)


class AllocationItemInput(BaseModel):
    asset_id: UUID
    target_percent: Decimal = Field(..., ge=0, le=100)


class CreateAllocationInput(BaseModel):
    items: List[AllocationItemInput]


@router.get("")
def get_allocations(user_id: UUID = Depends(get_current_user_id)):
    """Retorna a comparação de alocação recomendada vigente em relação à carteira atual."""
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            comparison = allocation_service.get_allocation_comparison(cur, portfolio_id)
            return comparison


@router.post("", status_code=status.HTTP_201_CREATED)
def create_allocation(
    input_data: CreateAllocationInput,
    user_id: UUID = Depends(get_current_user_id),
):
    """Cadastra e ativa imediatamente uma nova recomendação de alocação."""
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            items_payload = [
                {"asset_id": str(it.asset_id), "target_percent": str(it.target_percent)}
                for it in input_data.items
            ]
            try:
                orientation_id, version = allocation_service.create_orientation(
                    cur, portfolio_id, items_payload
                )
                conn.commit()
            except InvalidAllocationSumError as e:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": {"code": "INVALID_ALLOCATION_SUM", "message": str(e)}},
                )
            except ValueError as e:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "INVALID_ASSET", "message": str(e)}},
                )

            return {
                "orientation_id": str(orientation_id),
                "version": version,
                "status": "active",
                "message": "Orientação de alocação ativada com sucesso.",
            }


@router.get("/history")
def get_history(user_id: UUID = Depends(get_current_user_id)):
    """Retorna histórico de todas as orientações cadastradas."""
    with get_db_connection(user_id) as conn:
        with conn.cursor() as cur:
            portfolio_id, _, _ = portfolio_service.get_or_create_portfolio(cur, user_id)
            history = allocation_service.get_history(cur, portfolio_id)
            return {"history": history}
