"""Rotas de exportação CSV conforme contrato interfaces/csv.md."""

from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, Response
from app.db import get_db_connection
from app.routes.api import get_current_user_id, portfolio_service
from app.routes.allocations import allocation_service
from app.services.exports import (
    export_assets_csv,
    export_operations_csv,
    export_results_csv,
)

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


def _existing_portfolio(cur, user_id: UUID):
    cur.execute(
        "SELECT id, revision FROM portfolio_private.portfolios WHERE owner_id=%s;",
        (str(user_id),),
    )
    row = cur.fetchone()
    return (UUID(str(row[0])), int(row[1])) if row else (None, 0)


@router.get("/assets.csv")
def get_assets_csv(user_id: UUID = Depends(get_current_user_id)):
    with get_db_connection(user_id, isolation_level="REPEATABLE READ", read_only=True) as conn:
        with conn.cursor() as cur:
            portfolio_id, revision = _existing_portfolio(cur, user_id)
            if portfolio_id is not None:
                cur.execute(
                    "SELECT id, external_id, symbol, name, active "
                    "FROM portfolio_private.assets WHERE portfolio_id=%s ORDER BY symbol ASC;",
                    (str(portfolio_id),),
                )
                rows = cur.fetchall()
            else:
                rows = []
            assets = [
                {"id": r[0], "external_id": r[1], "symbol": r[2], "name": r[3], "active": r[4]}
                for r in rows
            ]
            csv_content = export_assets_csv(assets)
            return Response(
                content=csv_content,
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="assets.csv"',
                    "X-Portfolio-Revision": str(revision),
                    "Cache-Control": "no-store",
                },
            )


@router.get("/operations.csv")
def get_operations_csv(user_id: UUID = Depends(get_current_user_id)):
    with get_db_connection(user_id, isolation_level="REPEATABLE READ", read_only=True) as conn:
        with conn.cursor() as cur:
            portfolio_id, revision = _existing_portfolio(cur, user_id)
            if portfolio_id is not None:
                cur.execute(
                    "SELECT id, kind, asset_id, occurred_at, order_index, quantity, unit_price_usd, "
                    "fee_usdt, transfer_ref, source_label, destination_label, note, created_at, updated_at "
                    "FROM portfolio_private.operations WHERE portfolio_id=%s AND deleted_at IS NULL "
                    "ORDER BY occurred_at ASC, order_index ASC, id ASC;",
                    (str(portfolio_id),),
                )
                rows = cur.fetchall()
            else:
                rows = []
            ops = [
                {
                    "id": r[0], "kind": r[1], "asset_id": r[2], "occurred_at": r[3],
                    "order_index": r[4], "quantity": r[5], "unit_price_usd": r[6],
                    "fee_usdt": r[7], "transfer_ref": r[8], "source_label": r[9],
                    "destination_label": r[10], "note": r[11], "created_at": r[12],
                    "updated_at": r[13],
                }
                for r in rows
            ]
            csv_content = export_operations_csv(ops)
            return Response(
                content=csv_content,
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="operations.csv"',
                    "X-Portfolio-Revision": str(revision),
                    "Cache-Control": "no-store",
                },
            )


@router.get("/results.csv")
def get_results_csv(user_id: UUID = Depends(get_current_user_id)):
    with get_db_connection(user_id, isolation_level="REPEATABLE READ", read_only=True) as conn:
        with conn.cursor() as cur:
            portfolio_id, revision = _existing_portfolio(cur, user_id)
            if portfolio_id is not None:
                summary = portfolio_service.get_portfolio_summary(cur, portfolio_id)
            else:
                summary = {
                    "revision": 0,
                    "positions": [],
                    "totals": {
                        "realized_sales_usd": Decimal("0"), "crypto_value_usd": Decimal("0"),
                        "unrealized_usd": Decimal("0"), "cash_usdt": Decimal("0"),
                        "expenses_usd": Decimal("0"), "realized_net_usd": Decimal("0"),
                        "balance_usd": Decimal("0"), "cash_percent": None,
                        "complete": True, "updated": True, "freshness": "fresh",
                        "quote_snapshot_at": None,
                    },
                    "quote_snapshot_at": None,
                    "quote_freshness": "fresh",
                }
            csv_content = export_results_csv(
                revision=summary["revision"],
                positions=summary["positions"],
                totals=summary["totals"],
                quote_snapshot_at=summary.get("quote_snapshot_at"),
                freshness=summary.get("quote_freshness"),
            )
            return Response(
                content=csv_content,
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="results.csv"',
                    "X-Portfolio-Revision": str(summary["revision"]),
                    "Cache-Control": "no-store",
                },
            )


@router.get("/allocations.csv")
def get_allocations_csv(user_id: UUID = Depends(get_current_user_id)):
    from app.services.exports import export_allocations_csv

    with get_db_connection(user_id, isolation_level="REPEATABLE READ", read_only=True) as conn:
        with conn.cursor() as cur:
            portfolio_id, _ = _existing_portfolio(cur, user_id)
            if portfolio_id is not None:
                snapshot = portfolio_service.get_portfolio_summary(cur, portfolio_id)
                comp = allocation_service.get_allocation_comparison(
                    cur, portfolio_id, portfolio_summary=snapshot
                )
            else:
                comp = {
                    "version": 1, "items": [], "complete": True, "updated": True,
                    "freshness": "fresh", "quote_snapshot_at": None,
                }
            csv_content = export_allocations_csv(
                version=comp.get("version", 1),
                items=comp.get("items", []),
                complete=comp.get("complete"),
                updated=comp.get("updated"),
                freshness=comp.get("freshness"),
                quote_snapshot_at=comp.get("quote_snapshot_at"),
            )
            return Response(
                content=csv_content,
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="allocations.csv"',
                    "X-Allocation-Version": str(comp.get("version", 1)),
                    "Cache-Control": "no-store",
                },
            )
