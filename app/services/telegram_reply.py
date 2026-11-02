"""Redator e compositor de respostas em português para o Agente Telegram.

Atende a T013, T014, D-07, RF-01 a RF-10:
- Tom pessoal, conciso e profissional em linguagem natural.
- Formatação clara em Markdown.
- Nenhuma exposição de chaves, tokens, segredos ou dados de terceiros.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional


_KIND_PT = {
    "buy": "Compra",
    "sell": "Venda",
    "deposit": "Depósito",
    "withdrawal": "Saque",
    "transfer": "Transferência",
    "fee": "Taxa avulsa",
}

_FIELD_PT = {
    "kind": "o tipo da operação (compra, venda, depósito ou saque)",
    "symbol": "a criptomoeda (ex: BTC, ETH, SOL)",
    "quantity": "a quantidade",
    "unit_price_usd": "o preço unitário em USD",
}


class TelegramReplyComposer:
    """Gera textos de resposta formatados para cada cenário do bot."""

    @staticmethod
    def format_unauthorized() -> str:
        return "⛔ Acesso não autorizado. Este assistente é de uso pessoal e privado."

    @staticmethod
    def format_out_of_scope() -> str:
        return (
            "Olá Denis! Sou seu assistente pessoal de carteira.\n\n"
            "Posso ajudar você com:\n"
            "• Consultar patrimônio total e resultado atual\n"
            "• Listar suas criptomoedas e ver o saldo de um ativo\n"
            "• Checar se há alarmes de alvos de compra ou venda\n"
            "• Registrar novas operações que você realizou (por texto ou voz)\n\n"
            "*(Não executo ordens de mercado em corretoras nem realizo recomendações de investimento).*"
        )

    @staticmethod
    def format_read_error() -> str:
        return "Não foi possível compreender o conteúdo enviado. Por favor, tente enviar novamente em texto ou áudio claro."

    @staticmethod
    def format_cancel_draft() -> str:
        return "Operação cancelada. O rascunho anterior foi descartado."

    @staticmethod
    def format_missing_field_question(missing_fields: List[str], current_draft: Dict[str, Any]) -> str:
        k = current_draft.get("kind")
        k_label = _KIND_PT.get(k, "operação") if k else "operação"
        sym = current_draft.get("symbol") or "ativo"

        questions = []
        for f in missing_fields:
            if f == "unit_price_usd":
                questions.append(f"qual foi o preço unitário em USD para essa {k_label} de {sym}?")
            elif f == "quantity":
                questions.append(f"qual foi a quantidade negociada de {sym}?")
            elif f == "symbol":
                questions.append("qual é a criptomoeda (ex: BTC, ETH)?")
            elif f == "kind":
                questions.append("qual foi o tipo da operação (compra, venda, depósito ou saque)?")

        joined = " e ".join(questions)
        return f"Para registrar sua {k_label}, {joined}\n*(Responda com o valor ou digite 'cancelar' para desistir)*"

    @staticmethod
    def format_patrimonio(summary: Dict[str, Any]) -> str:
        totals = summary.get("totals") or {}
        bal = totals.get("balance_usd")
        cash = totals.get("cash_usdt")
        complete = totals.get("complete", True)

        bal_str = f"${bal:,.2f} USD" if bal is not None else "indisponível"
        cash_str = f"${cash:,.2f} USDT" if cash is not None else "$0.00 USDT"

        msg = f"📊 *Patrimônio Total:* {bal_str}\n💵 *Caixa Disponível:* {cash_str}"
        if not complete:
            msg += "\n\n⚠️ _Visão parcial: algumas cotações de mercado estão temporariamente indisponíveis._"
        return msg

    @staticmethod
    def format_resultado(summary: Dict[str, Any]) -> str:
        totals = summary.get("totals") or {}
        unrealized = totals.get("unrealized_usd")
        realized_net = totals.get("realized_net_usd")
        complete = totals.get("complete", True)

        total_result = None
        if unrealized is not None and realized_net is not None:
            total_result = unrealized + realized_net

        res_str = f"${total_result:,.2f} USD" if total_result is not None else "indisponível"
        unreal_str = f"${unrealized:,.2f} USD" if unrealized is not None else "parcial"
        real_str = f"${realized_net:,.2f} USD" if realized_net is not None else "$0.00 USD"

        msg = (
            f"📈 *Resultado Consolidado:* {res_str}\n"
            f"• *Ganho de Capital (não realizado):* {unreal_str}\n"
            f"• *Lucro Líquido Realizado:* {real_str}"
        )
        if not complete:
            msg += "\n\n⚠️ _Visão parcial: cálculo de resultado baseado nas cotações disponíveis._"
        return msg

    @staticmethod
    def format_asset_list(summary: Dict[str, Any]) -> str:
        positions = summary.get("positions") or []
        lines = []
        for p in positions:
            sym = p.get("symbol")
            qty = p.get("quantity")
            val = p.get("current_value_usd")
            val_txt = f" (${val:,.2f} USD)" if val is not None else ""
            lines.append(f"• *{sym}:* {qty}{val_txt}")

        totals = summary.get("totals") or {}
        cash = totals.get("cash_usdt")
        if cash and cash > Decimal("0"):
            lines.append(f"• *USDT (Caixa):* {cash:,.2f}")

        if not lines:
            return "Sua carteira ainda não possui ativos com posição cadastrada."

        return "🪙 *Criptomoedas na Carteira:*\n" + "\n".join(lines)

    @staticmethod
    def format_saldo(symbol: str, summary: Dict[str, Any]) -> str:
        positions = summary.get("positions") or []
        target_pos = next((p for p in positions if str(p.get("symbol")).upper() == symbol.upper()), None)

        if not target_pos:
            # Checa se é USDT
            if symbol.upper() == "USDT":
                cash = summary.get("totals", {}).get("cash_usdt", Decimal("0"))
                return f"💵 *Saldo de USDT:* {cash:,.2f}"
            return f"O ativo *{symbol.upper()}* não está na sua carteira."

        qty = target_pos.get("quantity")
        val = target_pos.get("current_value_usd")
        val_txt = f" (equivalente a ${val:,.2f} USD)" if val is not None else ""
        avg = target_pos.get("average_price_usd")
        avg_txt = f"\n• *Preço médio:* ${avg:,.2f} USD" if avg is not None else ""

        return f"🪙 *Saldo de {symbol.upper()}:* {qty}{val_txt}{avg_txt}"

    @staticmethod
    def format_alarms(alarms: List[Dict[str, Any]], query_type: Optional[str] = None) -> str:
        if not alarms:
            if query_type == "compra":
                return "🎯 Não existem alvos de compra atingidos no momento na sua carteira."
            if query_type == "venda":
                return "🎯 Não existem alvos de venda atingidos no momento na sua carteira."
            return "🎯 Não existem alvos atingidos no momento na sua carteira. Todos os ativos estão dentro das faixas normais."

        lines = ["🚨 *Alarmes Identificados:*"]
        for a in alarms:
            lines.append(f"• {a.get('message')}")
        return "\n".join(lines)

    @staticmethod
    def format_launch_success(op: Dict[str, Any]) -> str:
        k = op.get("kind")
        k_label = _KIND_PT.get(k, "Operação")
        sym = op.get("symbol")
        qty = op.get("quantity")
        price = op.get("unit_price_usd")
        fee = op.get("fee_usdt")
        dt = op.get("occurred_at")
        dt_str = dt.strftime("%d/%m/%Y %H:%M UTC") if isinstance(dt, datetime) else str(dt)

        lines = [
            f"✅ *{k_label} registrada com sucesso!*",
            f"• *Ativo:* {qty} {sym}",
        ]
        if price:
            lines.append(f"• *Preço Unitário:* ${price:,.2f} USD")
        if fee and fee > Decimal("0"):
            lines.append(f"• *Taxa:* ${fee:,.2f} USDT")
        lines.append(f"• *Data e Hora:* {dt_str}")
        lines.append("\n_A posição e o patrimônio foram recalculados no seu painel._")
        return "\n".join(lines)

    @staticmethod
    def format_launch_failure(reason: str) -> str:
        return f"❌ *Não foi possível registrar o lançamento:*\n{reason}"

