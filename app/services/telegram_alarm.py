"""Serviço de verificação de alarmes da carteira para o Telegram.

Atende à decisão D-06 e aos requisitos RF-06/RF-07:
- Consulta sob demanda: roda no momento do pedido.
- Devolve notificações de monitoramento não lidas (read_at IS NULL).
- Identifica alarmes a mercado conforme regra do painel:
  * Vender: preço a mercado >= 2x preço médio de compra (take-profit / dobro do PM).
  * Comprar: participação da moeda (% do total) abaixo da meta ideal E preço a mercado <= alvo de compra ativo.
  * Aguardar: não é alarme e não entra na resposta.
- NÃO marca read_at na notificação (a notificação continua intacta para o painel web).
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional


def check_telegram_alarms(
    unread_notifications: List[Dict[str, Any]],
    portfolio_summary: Dict[str, Any],
    targets: List[Dict[str, Any]],
    allocations: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Calcula e agrega alarmes ativos: notificações não lidas + sinais de Compra e Venda."""
    alarms: List[Dict[str, Any]] = []
    seen_symbols = set()

    # 1. Notificações não lidas
    for notif in unread_notifications:
        asset_info = notif.get("asset") or {}
        sym = asset_info.get("symbol") or "—"
        target_info = notif.get("target") or {}
        quote_info = notif.get("quote") or {}
        kind = target_info.get("kind") or "alvo"
        price = quote_info.get("price_usd") or target_info.get("price_usd")
        alarms.append({
            "source": "notification",
            "symbol": sym,
            "kind": kind,
            "price_usd": price,
            "message": f"Alvo de {kind} para {sym} atingido a ${price}",
        })
        seen_symbols.add(sym)

    # 2. Regras de sinal do painel (Comprar ou Vender)
    positions = portfolio_summary.get("positions") or []
    totals = portfolio_summary.get("totals") or {}
    balance_usd = totals.get("balance_usd")

    # Mapeia alvos de compra ativos por símbolo
    buy_targets_by_sym: Dict[str, Decimal] = {}
    for t in targets:
        if t.get("kind") == "buy" and t.get("active", True):
            s = str(t.get("symbol")).upper()
            p = t.get("price_usd")
            if p is not None:
                buy_targets_by_sym[s] = Decimal(str(p))

    for pos in positions:
        sym = str(pos.get("symbol") or "").upper()
        if sym == "USDT":
            continue

        quote = pos.get("quote_usd")
        avg_price = pos.get("average_price_usd")
        val = pos.get("current_value_usd")

        if quote is None:
            continue

        quote_dec = Decimal(str(quote))
        avg_dec = Decimal(str(avg_price)) if avg_price is not None else None
        val_dec = Decimal(str(val)) if val is not None else Decimal("0")

        # Regra VENDER: Preço atingiu ou superou o dobro do preço médio
        if avg_dec is not None and avg_dec > Decimal("0"):
            if quote_dec >= (avg_dec * Decimal("2")):
                alarms.append({
                    "source": "signal_sell",
                    "symbol": sym,
                    "kind": "Vender",
                    "price_usd": quote_dec,
                    "message": f"Sinal VENDER em {sym}: cotação (${quote_dec:.2f}) atingiu o dobro do preço médio (${avg_dec:.2f})",
                })
                continue

        # Regra COMPRAR: Participação abaixo da ideal E preço no alvo de compra
        target_buy_price = buy_targets_by_sym.get(sym)
        alloc_info = allocations.get(sym)
        target_percent = alloc_info.get("target_percent") if alloc_info else None

        if target_buy_price is not None and target_percent is not None and balance_usd and balance_usd > Decimal("0"):
            current_percent = (val_dec / Decimal(str(balance_usd))) * Decimal("100")
            target_pct_dec = Decimal(str(target_percent))

            # Participação abaixo da ideal e preço atingiu ou ficou abaixo do alvo de compra
            if current_percent < target_pct_dec and quote_dec <= target_buy_price:
                alarms.append({
                    "source": "signal_buy",
                    "symbol": sym,
                    "kind": "Comprar",
                    "price_usd": quote_dec,
                    "message": f"Sinal COMPRAR em {sym}: participação ({current_percent:.1f}%) abaixo da meta ({target_pct_dec:.1f}%) e preço (${quote_dec:.2f}) no alvo de compra (${target_buy_price:.2f})",
                })

    return alarms

