"""Testes da verificação de alarme do Agente Telegram (T004).

Regra D-06:
- Notificação de monitoramento não lida entra.
- Sinal 'Comprar' (participação abaixo da ideal e preço no alvo de compra) entra.
- Sinal 'Vender' (preço >= 2x preço médio ponderado) entra.
- Sinal 'Aguardar' NÃO entra como alarme.
- A consulta pelo Telegram NÃO marca notificação como lida (read_at continua NULL).
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.services.telegram_alarm import check_telegram_alarms


def test_alarm_with_unread_notification():
    unread_notifications = [
        {
            "id": "notif-1",
            "read_at": None,
            "asset": {"symbol": "BTC", "name": "Bitcoin"},
            "target": {"kind": "buy", "price_usd": "60000"},
            "quote": {"price_usd": "59500"},
        }
    ]
    portfolio_summary = {
        "positions": [],
        "totals": {},
    }
    targets = []
    allocations = {}

    alarms = check_telegram_alarms(
        unread_notifications=unread_notifications,
        portfolio_summary=portfolio_summary,
        targets=targets,
        allocations=allocations,
    )

    assert len(alarms) >= 1
    assert any("BTC" in a["symbol"] and a["source"] == "notification" for a in alarms)


def test_alarm_signals_buy_and_sell_included_wait_excluded():
    unread_notifications = []
    # BTC: avg_price 30000, quote 65000 -> >= 2x avg_price -> Sinal VENDER
    # ETH: allocation below ideal, quote at buy target -> Sinal COMPRAR
    # SOL: quote between buy target and 2x avg -> Sinal AGUARDAR (não entra!)
    portfolio_summary = {
        "positions": [
            {
                "symbol": "BTC",
                "quantity": Decimal("1.0"),
                "average_price_usd": Decimal("30000"),
                "quote_usd": Decimal("65000"),
                "current_value_usd": Decimal("65000"),
            },
            {
                "symbol": "ETH",
                "quantity": Decimal("10.0"),
                "average_price_usd": Decimal("3000"),
                "quote_usd": Decimal("2400"),
                "current_value_usd": Decimal("24000"),
            },
            {
                "symbol": "SOL",
                "quantity": Decimal("50.0"),
                "average_price_usd": Decimal("120"),
                "quote_usd": Decimal("140"),
                "current_value_usd": Decimal("7000"),
            },
        ],
        "totals": {"balance_usd": Decimal("96000")},
    }
    targets = [
        {"symbol": "ETH", "kind": "buy", "price_usd": Decimal("2500"), "active": True},
        {"symbol": "SOL", "kind": "buy", "price_usd": Decimal("100"), "active": True},
    ]
    allocations = {
        "ETH": {"target_percent": Decimal("30")},  # atual ~25% -> abaixo da ideal
        "SOL": {"target_percent": Decimal("5")},   # atual ~7.2% -> acima da ideal
    }

    alarms = check_telegram_alarms(
        unread_notifications=unread_notifications,
        portfolio_summary=portfolio_summary,
        targets=targets,
        allocations=allocations,
    )

    symbols = [a["symbol"] for a in alarms]
    assert "BTC" in symbols  # Vender
    assert "ETH" in symbols  # Comprar
    assert "SOL" not in symbols  # Aguardar excluído


def test_no_alarms_when_none_triggered():
    unread_notifications = []
    portfolio_summary = {
        "positions": [
            {
                "symbol": "SOL",
                "quantity": Decimal("10.0"),
                "average_price_usd": Decimal("100"),
                "quote_usd": Decimal("120"),
                "current_value_usd": Decimal("1200"),
            }
        ],
        "totals": {"balance_usd": Decimal("1200")},
    }
    alarms = check_telegram_alarms(
        unread_notifications=unread_notifications,
        portfolio_summary=portfolio_summary,
        targets=[],
        allocations={},
    )
    assert len(alarms) == 0

