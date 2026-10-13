"""Módulo de exportação de dados em CSV conforme interfaces/csv.md."""

import csv
import io
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

DANGEROUS_CHARS = ("=", "+", "-", "@", "\t", "\r")


def sanitize_text(val: Optional[str]) -> str:
    """Higieniza campos de texto contra injeção de fórmulas em planilhas."""
    if val is None:
        return ""
    text = str(val)
    stripped = text.lstrip(" ")
    if stripped.startswith(DANGEROUS_CHARS):
        return "'" + text
    return text


def format_decimal(val: Optional[Decimal]) -> str:
    """Formata decimais sem usar ponto flutuante binário."""
    if val is None:
        return ""
    return f"{val:f}"


def export_assets_csv(assets: List[Dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=",", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(["id", "external_id", "symbol", "name", "active"])

    for a in assets:
        writer.writerow([
            str(a["id"]),
            sanitize_text(a.get("external_id")),
            sanitize_text(a.get("symbol")),
            sanitize_text(a.get("name")),
            "true" if a.get("active", True) else "false",
        ])
    return output.getvalue()


def export_operations_csv(operations: List[Dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=",", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow([
        "id", "kind", "asset_id", "occurred_at", "order_index", "quantity",
        "unit_price_usd", "fee_usdt", "transfer_ref", "source_label",
        "destination_label", "note", "created_at", "updated_at"
    ])

    for op in operations:
        writer.writerow([
            str(op["id"]),
            str(op["kind"]),
            str(op["asset_id"]),
            op["occurred_at"].isoformat() if hasattr(op["occurred_at"], "isoformat") else str(op["occurred_at"]),
            str(op.get("order_index", 0)),
            format_decimal(op.get("quantity")),
            format_decimal(op.get("unit_price_usd")),
            format_decimal(op.get("fee_usdt", Decimal("0"))),
            sanitize_text(op.get("transfer_ref")),
            sanitize_text(op.get("source_label")),
            sanitize_text(op.get("destination_label")),
            sanitize_text(op.get("note")),
            op["created_at"].isoformat() if hasattr(op.get("created_at"), "isoformat") else str(op.get("created_at", "")),
            op["updated_at"].isoformat() if hasattr(op.get("updated_at"), "isoformat") else str(op.get("updated_at", "")),
        ])
    return output.getvalue()


def export_results_csv(
    revision: int,
    positions: List[Dict[str, Any]],
    totals: Dict[str, Any],
    *,
    quote_snapshot_at: Any = None,
    freshness: Optional[str] = None,
) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=",", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow([
        "row_type", "asset_id", "revision", "quantity", "remaining_cost_usd",
        "average_price_usd", "realized_sales_usd", "quote_usd", "quote_at",
        "quote_source", "quote_status", "current_value_usd", "unrealized_usd",
        "cash_usdt", "expenses_usd", "realized_net_usd", "balance_usd",
        "cash_percent", "complete", "updated", "freshness", "quote_snapshot_at",
        "quote_fetched_at", "quote_error",
    ])
    snapshot = quote_snapshot_at or totals.get("quote_snapshot_at")
    snapshot_text = snapshot.isoformat() if hasattr(snapshot, "isoformat") else str(snapshot or "")
    updated = bool(totals.get("updated", totals.get("complete", False)))
    freshness_value = freshness or totals.get("freshness") or (
        "fresh" if updated else ("stale" if totals.get("complete", False) else "incomplete")
    )

    # Linhas de posições individuais
    for pos in positions:
        writer.writerow([
            "position",
            str(pos["asset_id"]),
            str(revision),
            format_decimal(pos.get("quantity")),
            format_decimal(pos.get("remaining_cost_usd")),
            format_decimal(pos.get("average_price_usd")),
            format_decimal(pos.get("realized_sales_usd")),
            format_decimal(pos.get("quote_usd")),
            pos["quote_at"].isoformat() if hasattr(pos.get("quote_at"), "isoformat") else str(pos.get("quote_at") or ""),
            sanitize_text(pos.get("quote_source")),
            str(pos.get("quote_status") or ""),
            format_decimal(pos.get("current_value_usd")),
            format_decimal(pos.get("unrealized_usd")),
            "", "", "", "", "", "",
            "true" if pos.get("quote_status") == "available" else "false",
            sanitize_text(pos.get("quote_freshness") or pos.get("quote_status")),
            snapshot_text,
            pos["quote_fetched_at"].isoformat() if hasattr(pos.get("quote_fetched_at"), "isoformat") else str(pos.get("quote_fetched_at") or ""),
            sanitize_text(pos.get("quote_error")),
        ])

    # Linha consolidada de total
    writer.writerow([
        "total",
        "",
        str(revision),
        "", "", "",
        format_decimal(totals.get("realized_sales_usd")),
        "", "", "", "",
        format_decimal(totals.get("crypto_value_usd")),
        format_decimal(totals.get("unrealized_usd")),
        format_decimal(totals.get("cash_usdt")),
        format_decimal(totals.get("expenses_usd")),
        format_decimal(totals.get("realized_net_usd")),
        format_decimal(totals.get("balance_usd")),
        format_decimal(totals.get("cash_percent")),
        "true" if totals.get("complete", False) else "false",
        "true" if updated else "false",
        sanitize_text(freshness_value),
        snapshot_text,
        "",
        "",
    ])

    return output.getvalue()


def export_allocations_csv(
    version: int,
    items: List[Dict[str, Any]],
    *,
    complete: Optional[bool] = None,
    updated: Optional[bool] = None,
    freshness: Optional[str] = None,
    quote_snapshot_at: Any = None,
) -> str:
    """Exporta a comparação de alocação e rebalanceamento em CSV conforme interfaces/csv.md."""
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=",", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow([
        "symbol", "name", "target_percent", "current_value_usd",
        "ideal_value_usd", "adjustment_usd", "deviation_percent", "complete",
        "updated", "freshness", "quote_snapshot_at",
    ])
    snapshot_text = (
        quote_snapshot_at.isoformat() if hasattr(quote_snapshot_at, "isoformat")
        else str(quote_snapshot_at or "")
    )

    for it in items:
        dev_str = f"{it['deviation_percent']:f}" if it.get("deviation_percent") is not None else ""
        writer.writerow([
            sanitize_text(it.get("symbol")),
            sanitize_text(it.get("name")),
            format_decimal(it.get("target_percent")),
            format_decimal(it.get("current_value_usd")),
            format_decimal(it.get("ideal_value_usd")),
            format_decimal(it.get("adjustment_usd")),
            dev_str,
            "true" if complete else "false" if complete is not None else "",
            "true" if updated else "false" if updated is not None else "",
            sanitize_text(freshness),
            snapshot_text,
        ])

    return output.getvalue()
