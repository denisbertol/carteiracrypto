"""Serviço de reconhecimento e normalização de intenção do Agente Telegram.

Atende ao contrato _reversa_forward/004-agente-telegram/interfaces/intencao.md e aula do Prof. Sandeco:
- Integrado com LLM (Gemini) para compreensão avançada de linguagem natural, conversação e tolerância a erros.
- Fallback heurístico resiliente caso a IA esteja indisponível.
- Reconhece intenções: patrimônio, resultado, lista, saldo, alarme, lançamento, cancelar, conversa e fora de escopo.
- Lançamento incompleto gera pergunta inteligente dos campos faltantes.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class TelegramIntentKind(str, Enum):
    PATRIMONIO = "patrimonio"
    RESULTADO = "resultado"
    LISTA = "lista"
    SALDO = "saldo"
    ALARME = "alarme"
    LANCAMENTO = "lancamento"
    CANCELAR = "cancelar"
    CONVERSA = "conversa"
    FORA_DE_ESCOPO = "fora_de_escopo"


@dataclass
class TelegramIntentResult:
    intent: TelegramIntentKind
    symbol: Optional[str] = None
    kind: Optional[str] = None  # buy, sell, deposit, withdrawal, transfer, fee
    quantity: Optional[Decimal] = None
    unit_price_usd: Optional[Decimal] = None
    fee_usdt: Decimal = Decimal("0")
    occurred_at: Optional[datetime] = None
    note: Optional[str] = None
    missing_fields: List[str] = field(default_factory=list)
    conversational_reply: Optional[str] = None
    raw_text: str = ""


_KIND_ALIASES = {
    "buy": "buy", "comprei": "buy", "compra": "buy", "comprar": "buy",
    "sell": "sell", "vendi": "sell", "venda": "sell", "vender": "sell",
    "deposit": "deposit", "depositei": "deposit", "deposito": "deposit", "depósito": "deposit",
    "withdrawal": "withdrawal", "saquei": "withdrawal", "saque": "withdrawal", "retirada": "withdrawal",
    "transfer": "transfer", "transferi": "transfer", "transferencia": "transfer", "transferência": "transfer",
    "fee": "fee", "taxa": "fee", "taxa avulsa": "fee",
}


def _clean_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _parse_decimal(text: Any) -> Optional[Decimal]:
    if text is None:
        return None
    s = str(text).replace("$", "").replace("usdt", "").replace("usd", "").strip()
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        val = Decimal(s)
        return val if val.is_finite() else None
    except InvalidOperation:
        return None


def _classify_with_gemini(
    text: str,
    assets: List[Dict[str, Any]],
    current_draft: Optional[Dict[str, Any]],
    message_time: datetime,
    api_key: str,
    model: str = "gemini-2.5-flash",
) -> Optional[TelegramIntentResult]:
    """Usa o Gemini para extrair structured intent e resposta conversacional humanizada."""
    symbols_list = [str(a["symbol"]).upper() for a in assets if "symbol" in a]
    symbols_str = ", ".join(symbols_list)

    draft_ctx = "Nenhum rascunho em aberto."
    if current_draft:
        draft_ctx = (
            f"Rascunho de operação em aberto que Denis está preenchendo: "
            f"tipo={current_draft.get('kind')}, ativo={current_draft.get('symbol')}, "
            f"quantidade={current_draft.get('quantity')}, preço={current_draft.get('unit_price_usd')}, "
            f"campos_faltantes={current_draft.get('missing_fields')}"
        )

    system_instruction = (
        "Você é o assistente inteligente da Carteira Crypto pessoal de Denis, no padrão Sandeclaw (Prof. Sandeco). "
        "Sua função é interpretar a mensagem de Denis com inteligência, empatia e precisão, extraindo a intenção e os dados contábeis.\n\n"
        f"Ativos cadastrados na carteira de Denis: [{symbols_str}].\n"
        f"Contexto atual: {draft_ctx}\n\n"
        "Regras de classificação de intent:\n"
        "- 'patrimonio': consultas de patrimônio total, saldo geral, quanto dinheiro tem no total.\n"
        "- 'resultado': consultas de lucro, ganho de capital, PnL, rendimento.\n"
        "- 'lista': pedidos para listar as moedas/ativos cadastrados na carteira.\n"
        "- 'saldo': consulta de saldo de um ativo específico (preencha symbol com o ticker, ex: BTC, ETH).\n"
        "- 'alarme': verificação se algum alvo de compra ou venda foi atingido, se há avisos ou notificações.\n"
        "- 'lancamento': quando Denis quer registrar, cadastrar ou adicionar uma operação (compra, venda, depósito, saque, transferência, taxa).\n"
        "  * Se Denis disser apenas 'registrar nova operação' ou passar dados parciais, preencha missing_fields com o que falta ('kind', 'symbol', 'quantity', 'unit_price_usd') e gere em conversational_reply uma pergunta calorosa pedindo os detalhes que faltam!\n"
        "  * Se for compra ('buy') ou venda ('sell'), 'unit_price_usd' é obrigatório além de quantity e symbol.\n"
        "  * Se for depósito ou saque, o ativo padrão é USDT.\n"
        "- 'cancelar': quando Denis pedir para cancelar, abortar ou esquecer o rascunho atual.\n"
        "- 'conversa': saudações (olá, bom dia), dúvidas sobre como usar o bot, perguntas gerais. Responda em conversational_reply de forma prestativa, explicando o que você pode fazer.\n"
        "- 'fora_de_escopo': quando Denis pedir para executar compra/venda diretamente em corretora (Binance, etc), previsão do futuro, ou assuntos não relacionados. Explique amigavelmente em conversational_reply que você registra operações já realizadas e não opera na corretora.\n\n"
        "Responda EXCLUSIVAMENTE em JSON no schema solicitado."
    )

    schema = {
        "type": "OBJECT",
        "required": ["intent", "conversational_reply"],
        "properties": {
            "intent": {
                "type": "STRING",
                "enum": ["patrimonio", "resultado", "lista", "saldo", "alarme", "lancamento", "cancelar", "conversa", "fora_de_escopo"],
            },
            "kind": {"type": "STRING", "enum": ["buy", "sell", "deposit", "withdrawal", "transfer", "fee", "none"]},
            "symbol": {"type": "STRING"},
            "quantity": {"type": "STRING"},
            "unit_price_usd": {"type": "STRING"},
            "fee_usdt": {"type": "STRING"},
            "missing_fields": {"type": "ARRAY", "items": {"type": "STRING"}},
            "conversational_reply": {"type": "STRING"},
        },
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model)}:generateContent"
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    body = {
        "contents": [
            {"role": "user", "parts": [
                {"text": system_instruction},
                {"text": f"Mensagem de Denis: \"{text}\""}
            ]}
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                logger.warning(f"Gemini retornou status {resp.status_code}: {resp.text}")
                return None
            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return None
            content = candidates[0].get("content") or {}
            parts = content.get("parts") or []
            if not parts:
                return None
            raw_json = parts[0].get("text", "")
            parsed = json.loads(raw_json)

            intent_str = parsed.get("intent", "conversa")
            intent_enum = TelegramIntentKind(intent_str)

            kind_str = parsed.get("kind") or None
            if kind_str == "":
                kind_str = None

            symbol_str = parsed.get("symbol") or None
            if symbol_str:
                symbol_str = symbol_str.strip().upper()

            qty_dec = _parse_decimal(parsed.get("quantity"))
            price_dec = _parse_decimal(parsed.get("unit_price_usd"))
            fee_dec = _parse_decimal(parsed.get("fee_usdt")) or Decimal("0")

            missing = parsed.get("missing_fields") or []

            # Merge com rascunho se for lançamento
            if intent_enum == TelegramIntentKind.LANCAMENTO and current_draft:
                kind_str = kind_str or current_draft.get("kind")
                symbol_str = symbol_str or current_draft.get("symbol")
                if qty_dec is None and current_draft.get("quantity") is not None:
                    qty_dec = current_draft["quantity"]
                if price_dec is None and current_draft.get("unit_price_usd") is not None:
                    price_dec = current_draft["unit_price_usd"]
                if fee_dec == Decimal("0") and current_draft.get("fee_usdt") is not None:
                    fee_dec = current_draft["fee_usdt"]

                # Recalcula missing
                missing_clean = []
                if not kind_str:
                    missing_clean.append("kind")
                if not symbol_str:
                    missing_clean.append("symbol")
                if qty_dec is None or qty_dec <= Decimal("0"):
                    missing_clean.append("quantity")
                if kind_str in ("buy", "sell") and (price_dec is None or price_dec <= Decimal("0")):
                    missing_clean.append("unit_price_usd")
                missing = missing_clean

            return TelegramIntentResult(
                intent=intent_enum,
                kind=kind_str,
                symbol=symbol_str,
                quantity=qty_dec,
                unit_price_usd=price_dec,
                fee_usdt=fee_dec,
                occurred_at=current_draft.get("message_time") if current_draft else message_time,
                missing_fields=missing,
                conversational_reply=parsed.get("conversational_reply"),
                raw_text=text,
            )
    except Exception as e:
        logger.warning(f"Falha ao consultar LLM Gemini para o Telegram: {e}")
        return None


def classify_telegram_intent(
    text: str,
    assets: List[Dict[str, Any]],
    current_draft: Optional[Dict[str, Any]] = None,
    message_time: Optional[datetime] = None,
    gemini_api_key: Optional[str] = None,
    gemini_model: str = "gemini-2.5-flash",
) -> TelegramIntentResult:
    """
    Classifica a intenção usando a LLM Gemini se disponível,
    com fallback heurístico determinístico e tolerante a erros.
    """
    now = message_time or datetime.now(timezone.utc)
    raw = text.strip()

    # 1. Se houver chave Gemini, tenta a LLM primeiro
    if gemini_api_key and gemini_api_key.strip():
        llm_res = _classify_with_gemini(
            text=raw,
            assets=assets,
            current_draft=current_draft,
            message_time=now,
            api_key=gemini_api_key.strip(),
            model=gemini_model,
        )
        if llm_res is not None:
            return llm_res

    # 2. Fallback Heurístico Aperfeiçoado
    norm = _clean_text(raw)

    # Cancelamento
    if norm in ("cancelar", "cancela", "esquece", "cancel", "abortar", "deixa pra lá", "deixa pra la"):
        return TelegramIntentResult(
            intent=TelegramIntentKind.CANCELAR,
            raw_text=raw,
            occurred_at=now,
            conversational_reply="Operação cancelada. O rascunho anterior foi descartado.",
        )

    # Fora de escopo explícito
    if any(p in norm for p in ("binance", "corretora", "exchange", "ordem a mercado", "ordem de mercado", "previsão do tempo", "previsao do tempo", "notícias", "noticias")):
        return TelegramIntentResult(
            intent=TelegramIntentKind.FORA_DE_ESCOPO,
            raw_text=raw,
            occurred_at=now,
        )

    # Alarmes
    if any(p in norm for p in ("alarme", "alvo", "aviso", "atingiu alvo", "notificacao", "notificação")):
        return TelegramIntentResult(
            intent=TelegramIntentKind.ALARME,
            raw_text=raw,
            occurred_at=now,
        )

    # Patrimônio total
    if any(p in norm for p in ("patrimonio", "patrimônio", "saldo total", "total da carteira", "valor da carteira", "quanto tenho no total")):
        return TelegramIntentResult(
            intent=TelegramIntentKind.PATRIMONIO,
            raw_text=raw,
            occurred_at=now,
        )

    # Resultado atual
    if any(p in norm for p in ("resultado", "lucro", "ganho", "rendimento", "pnl", "ganhos e perdas")):
        return TelegramIntentResult(
            intent=TelegramIntentKind.RESULTADO,
            raw_text=raw,
            occurred_at=now,
        )

    # Lista de criptomoedas
    if any(p in norm for p in ("lista", "listar", "quais criptos", "quais moedas", "minhas criptos", "ativos da carteira")):
        return TelegramIntentResult(
            intent=TelegramIntentKind.LISTA,
            raw_text=raw,
            occurred_at=now,
        )

    symbols_map = {str(a["symbol"]).upper(): a for a in assets if "symbol" in a}

    # Saldo de ativo específico
    m_saldo = re.search(r"\b(?:saldo|tenho|quantidade|posição|posicao)\b(?:\s*(?:de|em|do|da))?\s+([a-zA-Z0-9]+)", raw, re.IGNORECASE)
    if m_saldo and not any(k in norm for k in ("comprei", "vendi", "depositei", "saquei")):
        sym = m_saldo.group(1).upper()
        if sym in symbols_map or not any(k in norm for k in _KIND_ALIASES):
            return TelegramIntentResult(
                intent=TelegramIntentKind.SALDO,
                symbol=sym,
                raw_text=raw,
                occurred_at=now,
            )

    if raw.upper() in symbols_map and not current_draft:
        return TelegramIntentResult(
            intent=TelegramIntentKind.SALDO,
            symbol=raw.upper(),
            raw_text=raw,
            occurred_at=now,
        )

    # Lançamento de Operação
    # Inclui expressamente pedidos como "registrar nova operação", "nova operação", "registrar", etc.
    is_explicit_register_request = any(p in norm for p in (
        "registrar nova operacao", "registrar nova operação",
        "nova operacao", "nova operação",
        "registrar operacao", "registrar operação",
        "adicionar operacao", "adicionar operação",
        "cadastrar operacao", "cadastrar operação",
        "novo lancamento", "novo lançamento",
        "registrar", "anotar",
    ))

    is_launch = is_explicit_register_request or any(k in norm for k in ("comprei", "vendi", "depositei", "saquei", "compra", "venda", "depósito", "deposito", "saque", "taxa", "transferi")) or (current_draft is not None)

    if is_launch:
        kind = None
        for alias, mapped_kind in _KIND_ALIASES.items():
            if re.search(r"\b" + re.escape(alias) + r"\b", norm):
                kind = mapped_kind
                break

        symbol = None
        for sym in sorted(symbols_map.keys(), key=len, reverse=True):
            if re.search(r"\b" + re.escape(sym) + r"\b", raw, re.IGNORECASE):
                symbol = sym
                break

        if not symbol and kind in ("deposit", "withdrawal", "fee"):
            symbol = "USDT"

        fee_usdt = Decimal("0")
        m_fee = re.search(r"\b(?:taxa|fee)\b(?:\s*(?:de|em|usdt|:|=))?\s*([0-9]+(?:[.,][0-9]+)?)", raw, re.IGNORECASE)
        if m_fee:
            parsed_fee = _parse_decimal(m_fee.group(1))
            if parsed_fee is not None and parsed_fee >= 0:
                fee_usdt = parsed_fee

        unit_price = None
        m_price = re.search(r"(?:\b(?:a|ao|por|preço|preco|price|cotação|cotacao|valor|preço foi|o preço foi)\b|@)(?:\s*(?:de|em|usd|usdt|:|=))?\s*([0-9]+(?:[.,][0-9]+)?)", raw, re.IGNORECASE)
        if m_price:
            unit_price = _parse_decimal(m_price.group(1))

        clean_for_nums = raw
        if m_fee:
            clean_for_nums = clean_for_nums.replace(m_fee.group(0), " ")
        if m_price:
            clean_for_nums = clean_for_nums.replace(m_price.group(0), " ")

        nums = re.findall(r"[0-9]+(?:[.,][0-9]+)?", clean_for_nums)
        quantity = None
        if nums:
            quantity = _parse_decimal(nums[0])
            if len(nums) > 1 and unit_price is None:
                unit_price = _parse_decimal(nums[1])

        if current_draft:
            kind = kind or current_draft.get("kind")
            symbol = symbol or current_draft.get("symbol")
            if quantity is None and current_draft.get("quantity") is not None:
                quantity = current_draft["quantity"]
            if unit_price is None and current_draft.get("unit_price_usd") is not None:
                unit_price = current_draft["unit_price_usd"]
            if fee_usdt == Decimal("0") and current_draft.get("fee_usdt") is not None:
                fee_usdt = current_draft["fee_usdt"]
            occurred_at = current_draft.get("message_time") or now
        else:
            occurred_at = now

        missing = []
        if not kind:
            missing.append("kind")
        if not symbol:
            missing.append("symbol")
        if quantity is None or quantity <= Decimal("0"):
            missing.append("quantity")
        if kind in ("buy", "sell") and (unit_price is None or unit_price <= Decimal("0")):
            missing.append("unit_price_usd")

        # Mensagem contextual explicativa quando faltam dados
        conversational_reply = None
        if missing:
            conversational_reply = "Com certeza! Para registrar sua operação, me informe por favor:\n"
            parts = []
            if "kind" in missing:
                parts.append("• Se é **Compra** ou **Venda** (ou depósito/saque)")
            if "symbol" in missing:
                parts.append("• Qual é a criptomoeda (ex: BTC, ETH, SOL)")
            if "quantity" in missing:
                parts.append("• Quantas unidades foram negociadas")
            if "unit_price_usd" in missing:
                parts.append("• Qual foi o preço unitário em USD")
            conversational_reply += "\n".join(parts) + "\n\n*(Você pode digitar tudo numa única mensagem ou digitar 'cancelar' para desistir)*"

        return TelegramIntentResult(
            intent=TelegramIntentKind.LANCAMENTO,
            kind=kind,
            symbol=symbol,
            quantity=quantity,
            unit_price_usd=unit_price,
            fee_usdt=fee_usdt,
            occurred_at=occurred_at,
            missing_fields=missing,
            conversational_reply=conversational_reply,
            raw_text=raw,
        )

    # Saudações e conversa amigável
    if any(p in norm for p in ("oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "ajuda", "help", "como funciona", "quem é você", "tudo bem")):
        return TelegramIntentResult(
            intent=TelegramIntentKind.CONVERSA,
            raw_text=raw,
            occurred_at=now,
            conversational_reply=(
                "Olá, Denis! 👋 Sou o assistente pessoal da sua carteira de criptomoedas.\n\n"
                "Aqui você pode:\n"
                "📊 Perguntar: *\"qual o patrimônio?\"* ou *\"meu resultado\"*\n"
                "🪙 Consultar: *\"saldo de BTC\"* ou *\"listar moedas\"*\n"
                "🚨 Verificar: *\"tem algum alarme de compra ou venda?\"*\n"
                "✍️ Registrar operações por texto ou áudio: *\"comprei 0.1 BTC a 68000\"* ou apenas *\"registrar nova operação\"* que eu te guio!\n\n"
                "Como posso te ajudar agora?"
            ),
        )

    # Se não identificou nada específico, responde com instrução amigável em vez de ficar mudo!
    return TelegramIntentResult(
        intent=TelegramIntentKind.CONVERSA,
        raw_text=raw,
        occurred_at=now,
        conversational_reply=(
            f"Não compreendi com certeza o que você quis dizer com \"_{raw}_\".\n\n"
            "Você pode me perguntar:\n"
            "• *\"quanto está o patrimônio?\"*\n"
            "• *\"saldo de BTC\"*\n"
            "• *\"tem algum alarme?\"*\n"
            "• *\"comprei 0.5 SOL por 150\"* ou *\"registrar nova operação\"*\n\n"
            "Ou envie um áudio falando normalmente que eu transcrevo e processo para você!"
        ),
    )
