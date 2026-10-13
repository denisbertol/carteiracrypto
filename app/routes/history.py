"""Authenticated trigger for the one-time daily price history import."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.routes.api import get_current_user_id
from app.services.price_history import PriceHistoryService


router = APIRouter(prefix="/api/v1/history", tags=["history"])
history_service = PriceHistoryService()


@router.post("/backfill")
def run_backfill(response: Response, user_id: UUID = Depends(get_current_user_id)):
    """Import missing daily prices for a few assets per call; clients repeat while pending."""
    response.headers["Cache-Control"] = "no-store"
    result = history_service.run_backfill(user_id)
    if result["state"] == "blocked":
        response.status_code = status.HTTP_202_ACCEPTED
    return result
