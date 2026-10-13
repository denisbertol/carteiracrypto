"""Lê lançamentos e alvos com a API Gemini e devolve uma proposta para confirmação."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import base64
import csv
import io
import json
import re
from typing import Any, Callable
from urllib.parse import quote

import httpx

DEFAULT_MODEL = "gemini-2.5-flash"
MAX_ITEMS = 100
MAX_NOTE = 2000
MAX_DECIMALS = 18
MAX_INTEGER_DIGITS = 18
_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_KIND_ALIASES = {
    "buy": "buy", "compra": "buy", "comprar": "buy",
    "sell": "sell", "venda": "sell", "vender": "sell",
    "deposit": "deposit", "deposito": "deposit", "depósito": "deposit",
    "withdrawal": "withdrawal", "saque": "withdrawal", "retirada": "withdrawal",
    "transfer": "transfer", "transferencia": "transfer", "transferência": "transfer",
    "fee": "fee", "taxa": "fee", "taxa avulsa": "fee",
}
_KIND_LABELS = {
    "buy": "Compra", "sell": "Venda", "deposit": "Depósito",
    "withdrawal": "Saque", "transfer": "Transferência", "fee": "Taxa avulsa",
}
_KIND_ORDER = {"deposit": 0, "transfer": 1, "buy": 2, "sell": 3, "fee": 4, "withdrawal": 5}
_USDT_ONLY = {"deposit", "withdrawal", "fee"}
_TRADES = {"buy", "sell"}


class AiImportError(Exception):
    def __init__(self, message: str, code: str = "AI_FAILED") -> None:
        self.code = code
        super().__init__(message)


def validate_model(model: str | None) -> str:
    value = (model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if not _MODEL_PATTERN.match(value):
        raise AiImportError("Informe um nome de modelo válido, como gemini-2.5-flash.", "INVALID_MODEL")
    return value


def key_hint(api_key: str | None) -> str | None:
    if not api_key or len(api_key) < 4:
        return None
    return api_key[-4:]


def sniff_image(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def parse_model_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*)```", raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AiImportError("O Gemini não devolveu uma leitura utilizável.", "AI_UNREADABLE") from exc
    if isinstance(payload, list):
        return {"items": payload}
    if not isinstance(payload, dict):
        raise AiImportError("O Gemini não devolveu uma leitura utilizável.", "AI_UNREADABLE")
    return payload


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    text = str(value).strip().replace(" ", "").replace("US$", "").replace("USDT", "").replace("USD", "").replace("$", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif text.count(",") == 1:
        text = text.replace(",", ".")
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    rendered = format(number, "f")
    whole, _, fraction = rendered.partition(".")
    if len(whole.lstrip("-")) > MAX_INTEGER_DIGITS or len(fraction.rstrip("0")) > MAX_DECIMALS:
        return None
    return number


def _decimal_text(number: Decimal) -> str:
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    if not cleaned:
        return None
    return cleaned[:limit]


def _when(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if not 2009 <= parsed.year <= 2100:
        return None
    return parsed


def _asset_index(assets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(asset["symbol"]).upper(): asset for asset in assets if asset.get("symbol")}


def _blocked(symbol: str, reason: str, **extra: Any) -> dict[str, Any]:
    item = {"ready": False, "symbol": symbol or "—", "reason": reason}
    item.update(extra)
    return item


def normalize_operations(payload: dict[str, Any], assets: list[dict[str, Any]]) -> dict[str, Any]:
    by_symbol = _asset_index(assets)
    raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    proposals: list[dict[str, Any]] = []
    overflow = raw_items[MAX_ITEMS:]
    for raw in raw_items[:MAX_ITEMS]:
        proposals.append(_operation(raw if isinstance(raw, dict) else {}, by_symbol))
    if overflow:
        proposals.append(_blocked("", f"{len(overflow)} lançamentos passaram do limite de {MAX_ITEMS} e ficaram de fora."))
    ready = [item for item in proposals if item["ready"]]
    ready.sort(key=lambda item: (item["occurred_at"], _KIND_ORDER.get(item["kind"], 9), item["symbol"]))
    blocked = [item for item in proposals if not item["ready"]]
    skipped = _skipped(payload.get("skipped"))
    summary = _text(payload.get("summary"), 500)
    return {"summary": summary, "items": ready + blocked, "skipped": skipped}


def _operation(raw: dict[str, Any], by_symbol: dict[str, dict[str, Any]]) -> dict[str, Any]:
    kind = _KIND_ALIASES.get(str(raw.get("kind") or "").strip().lower())
    symbol = str(raw.get("symbol") or "").strip().upper()
    if kind is None:
        return _blocked(symbol, "Tipo de lançamento não reconhecido.", kind=None)
    asset = by_symbol.get(symbol)
    if asset is None:
        return _blocked(symbol, "Ativo não cadastrado na carteira.", kind=kind, kind_label=_KIND_LABELS[kind])
    if kind in _USDT_ONLY and symbol != "USDT":
        return _blocked(symbol, "Depósito, saque e taxa avulsa só podem ser em USDT.", kind=kind, kind_label=_KIND_LABELS[kind])
    if kind in _TRADES and symbol == "USDT":
        return _blocked(symbol, "Compra e venda não usam USDT como ativo negociado.", kind=kind, kind_label=_KIND_LABELS[kind])
    occurred = _when(raw.get("occurred_at"))
    if occurred is None:
        return _blocked(symbol, "Data do lançamento ausente ou inválida.", kind=kind, kind_label=_KIND_LABELS[kind])
    quantity = _decimal(raw.get("quantity"))
    if quantity is None or quantity <= 0:
        return _blocked(symbol, "Quantidade ausente ou inválida.", kind=kind, kind_label=_KIND_LABELS[kind])
    price = _decimal(raw.get("unit_price_usd"))
    if kind in _TRADES and (price is None or price <= 0):
        return _blocked(symbol, "Compra e venda precisam do preço unitário em USD.", kind=kind, kind_label=_KIND_LABELS[kind])
    fee = _decimal(raw.get("fee_usdt"))
    if fee is None:
        fee = Decimal("0")
    if fee < 0:
        return _blocked(symbol, "A taxa não pode ser negativa.", kind=kind, kind_label=_KIND_LABELS[kind])
    if kind not in _TRADES and kind != "transfer":
        fee = Decimal("0")
    return {
        "ready": True,
        "reason": None,
        "kind": kind,
        "kind_label": _KIND_LABELS[kind],
        "symbol": symbol,
        "asset_id": str(asset["id"]),
        "occurred_at": occurred.isoformat(),
        "quantity": _decimal_text(quantity),
        "unit_price_usd": _decimal_text(price) if kind in _TRADES and price is not None else None,
        "fee_usdt": _decimal_text(fee),
        "note": _text(raw.get("note"), MAX_NOTE),
    }


def normalize_targets(
    payload: dict[str, Any],
    assets: list[dict[str, Any]],
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    by_symbol = _asset_index(assets)
    buy_targets: dict[str, dict[str, Any]] = {}
    for target in targets:
        if str(target.get("kind")) != "buy":
            continue
        asset_id = str(target.get("asset_id"))
        current = buy_targets.get(asset_id)
        if current is None or int(target.get("version") or 0) >= int(current.get("version") or 0):
            buy_targets[asset_id] = target
    chosen: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    for raw in raw_items[:MAX_ITEMS]:
        if not isinstance(raw, dict):
            continue
        symbol = str(raw.get("symbol") or "").strip().upper()
        if symbol in chosen:
            duplicates.add(symbol)
        chosen[symbol] = raw
    proposals = [_target(raw, by_symbol, buy_targets, symbol in duplicates) for symbol, raw in chosen.items()]
    if len(raw_items) > MAX_ITEMS:
        proposals.append(_blocked("", f"A leitura passou de {MAX_ITEMS} alvos e o excedente ficou de fora."))
    ready = [item for item in proposals if item["ready"]]
    blocked = [item for item in proposals if not item["ready"]]
    ready.sort(key=lambda item: item["symbol"])
    return {
        "summary": _text(payload.get("summary"), 500),
        "items": ready + blocked,
        "skipped": _skipped(payload.get("skipped")),
    }


def _target(
    raw: dict[str, Any],
    by_symbol: dict[str, dict[str, Any]],
    buy_targets: dict[str, dict[str, Any]],
    duplicated: bool,
) -> dict[str, Any]:
    symbol = str(raw.get("symbol") or "").strip().upper()
    asset = by_symbol.get(symbol)
    if asset is None:
        return _blocked(symbol, "Ativo não cadastrado na carteira.")
    if symbol == "USDT":
        return _blocked(symbol, "USDT é o caixa e não recebe alvo de compra.")
    price = _decimal(raw.get("price_usd"))
    if price is None or price <= 0:
        return _blocked(symbol, "Preço alvo ausente ou inválido.")
    current = buy_targets.get(str(asset["id"]))
    active = raw.get("active")
    if not isinstance(active, bool):
        active = bool(current["active"]) if current else True
    orientation = _text(raw.get("orientation"), 1000)
    same_price = current is not None and Decimal(str(current["price_usd"])) == price and bool(current["active"]) == active
    same_orientation = current is not None and (current.get("orientation") or None) == orientation
    if same_price and (orientation is None or same_orientation):
        return _blocked(symbol, "O alvo de compra já está neste preço.", price_usd=_decimal_text(price))
    reason = "Havia mais de um valor para este ativo; usei o último." if duplicated else None
    return {
        "ready": True,
        "reason": reason,
        "symbol": symbol,
        "asset_id": str(asset["id"]),
        "price_usd": _decimal_text(price),
        "active": active,
        "orientation": orientation,
        "action": "update" if current else "create",
        "target_id": str(current["id"]) if current else None,
        "version": int(current["version"]) if current else None,
        "current_price_usd": str(current["price_usd"]) if current else None,
    }


def _skipped(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows = []
    for item in value[:50]:
        if isinstance(item, str) and item.strip():
            rows.append({"description": item.strip()[:300], "reason": ""})
        elif isinstance(item, dict):
            description = _text(item.get("description") or item.get("symbol"), 300) or "Linha ignorada"
            reason = _text(item.get("reason"), 300) or ""
            rows.append({"description": description, "reason": reason})
    return rows


def operation_instruction(assets: list[dict[str, Any]]) -> str:
    catalog = "\n".join(f"- {asset['symbol']}: {asset.get('name') or asset['symbol']}" for asset in assets)
    return (
        "Extraia lançamentos de carteira cripto a partir do material do usuário. "
        "Responda somente JSON com as chaves items, skipped e summary. "
        "Cada item tem kind (buy, sell, deposit, withdrawal, transfer ou fee), symbol, "
        "occurred_at em ISO 8601 com fuso, quantity, unit_price_usd, fee_usdt e note. "
        "Use ponto decimal e não use separador de milhar. "
        "quantity é a quantidade do ativo; em depósito, saque e taxa avulsa o ativo é USDT e quantity é o valor em USDT. "
        "unit_price_usd é o preço de uma unidade em USD e é obrigatório em compra e venda. "
        "fee_usdt é a taxa paga em USDT na mesma operação. "
        "Una a taxa em USDT de uma ordem à compra ou venda correspondente. "
        "Ignore bônus, staking, rendimento flexível e conversão entre stablecoins quando não forem compra, venda, depósito ou saque reais. "
        "Não invente lançamento que não esteja no material. O que for ambíguo vai em skipped, com description e reason. "
        "Ativos já cadastrados:\n" + catalog
    )


def target_instruction(assets: list[dict[str, Any]]) -> str:
    catalog = "\n".join(f"- {asset['symbol']}: {asset.get('name') or asset['symbol']}" for asset in assets)
    return (
        "Extraia alvos de compra de criptomoedas a partir do material do usuário. "
        "Responda somente JSON com as chaves items, skipped e summary. "
        "Cada item tem symbol, price_usd, active e orientation. "
        "price_usd é o preço alvo de compra de uma unidade em USD, com ponto decimal e sem separador de milhar. "
        "Há no máximo um item por símbolo. Não invente alvo que não esteja no material. "
        "O que não der para ler vai em skipped, com description e reason. "
        "Ativos já cadastrados:\n" + catalog
    )


_SKIPPED_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {"description": {"type": "STRING"}, "reason": {"type": "STRING"}},
    },
}
OPERATION_SCHEMA = {
    "type": "OBJECT",
    "required": ["items"],
    "properties": {
        "summary": {"type": "STRING"},
        "skipped": _SKIPPED_SCHEMA,
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": ["kind", "symbol", "occurred_at", "quantity"],
                "properties": {
                    "kind": {"type": "STRING"},
                    "symbol": {"type": "STRING"},
                    "occurred_at": {"type": "STRING"},
                    "quantity": {"type": "STRING"},
                    "unit_price_usd": {"type": "STRING"},
                    "fee_usdt": {"type": "STRING"},
                    "note": {"type": "STRING"},
                },
            },
        },
    },
}
TARGET_SCHEMA = {
    "type": "OBJECT",
    "required": ["items"],
    "properties": {
        "summary": {"type": "STRING"},
        "skipped": _SKIPPED_SCHEMA,
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": ["symbol", "price_usd"],
                "properties": {
                    "symbol": {"type": "STRING"},
                    "price_usd": {"type": "STRING"},
                    "active": {"type": "BOOLEAN"},
                    "orientation": {"type": "STRING"},
                },
            },
        },
    },
}


class GeminiClient:
    def __init__(self, api_key: str, model: str, poster: Callable[..., Any] | None = None) -> None:
        self._api_key = api_key
        self._model = validate_model(model)
        self._poster = poster

    def generate(self, instruction: str, material: str, image: tuple[str, bytes] | None, schema: dict[str, Any]) -> dict[str, Any]:
        parts: list[dict[str, Any]] = [{"text": instruction}]
        if material:
            parts.append({"text": "Material do usuário:\n" + material})
        if image is not None:
            mime, data = image
            parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}})
        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": schema,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        response = self._post(body)
        if response.status_code == 400:
            body["generationConfig"].pop("thinkingConfig", None)
            response = self._post(body)
        if response.status_code == 400:
            body["generationConfig"].pop("responseSchema", None)
            body["generationConfig"].pop("responseMimeType", None)
            response = self._post(body)
        self._raise_for_status(response)
        return parse_model_json(self._response_text(response))

    def _post(self, body: dict[str, Any]) -> Any:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(self._model)}:generateContent"
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        try:
            if self._poster is not None:
                return self._poster(url, headers=headers, json=body)
            with httpx.Client(timeout=60.0) as client:
                return client.post(url, headers=headers, json=body)
        except Exception:
            raise AiImportError("Não foi possível falar com o Gemini.", "AI_UNAVAILABLE") from None

    @staticmethod
    def _raise_for_status(response: Any) -> None:
        status = getattr(response, "status_code", 200)
        err_msg = ""
        try:
            payload = response.json() if callable(getattr(response, "json", None)) else {}
            if isinstance(payload, dict):
                err = payload.get("error", {})
                if isinstance(err, dict):
                    err_msg = str(err.get("message") or "")
        except Exception:
            err_msg = ""

        if status == 402 or "credits are depleted" in err_msg.lower() or "billing" in err_msg.lower():
            raise AiImportError(
                "Os créditos da sua chave do Gemini estão esgotados no Google AI Studio (erro 402). "
                "Adicione créditos no AI Studio ou configure uma nova chave na engrenagem de IA.",
                "AI_CREDITS_DEPLETED",
            )
        if status in {401, 403}:
            raise AiImportError("A chave da API do Gemini foi recusada. Confira a configuração.", "AI_REJECTED")
        if status == 404:
            raise AiImportError("O modelo configurado não foi encontrado. Ajuste o nome na engrenagem de IA.", "AI_REJECTED")
        if status == 429:
            raise AiImportError("O Gemini recusou por limite de uso. Tente de novo em instantes.", "AI_BUSY")
        if status >= 400:
            detail = f": {err_msg}" if err_msg else "."
            raise AiImportError(f"O Gemini não conseguiu ler este material{detail}", "AI_UNAVAILABLE")

    @staticmethod
    def _response_text(response: Any) -> str:
        try:
            payload = response.json()
        except Exception:
            raise AiImportError("O Gemini não devolveu uma leitura utilizável.", "AI_UNREADABLE") from None
        candidates = payload.get("candidates") if isinstance(payload, dict) else None
        if not candidates:
            raise AiImportError("O Gemini não devolveu uma leitura deste material.", "AI_UNREADABLE")
        content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        text = "".join(part.get("text", "") for part in parts or [] if isinstance(part, dict))
        if not text.strip():
            raise AiImportError("O Gemini não devolveu uma leitura utilizável.", "AI_UNREADABLE")
        return text


def _parse_heuristic_date(raw: str) -> str:
    s = (raw or "").strip()
    m_br = re.search(r"\b(\d{2})/(\d{2})/(\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?\b", s)
    if m_br:
        d, m, y, h, mi, sec = m_br.groups()
        h, mi, sec = h or "00", mi or "00", sec or "00"
        return f"{y}-{m}-{d}T{h}:{mi}:{sec}+00:00"
    m_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?\b", s)
    if m_iso:
        y, m, d, h, mi, sec = m_iso.groups()
        h, mi, sec = h or "00", mi or "00", sec or "00"
        return f"{y}-{m}-{d}T{h}:{mi}:{sec}+00:00"
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_col(header_row: list[str], candidates: set[str]) -> int | None:
    for idx, col in enumerate(header_row):
        norm = col.strip().lower()
        if norm in candidates or any(c == norm or (len(c) > 3 and c in norm) for c in candidates):
            return idx
    return None


def fallback_parse_operations(material: str, assets: list[dict[str, Any]]) -> dict[str, Any]:
    """Processador local de contingência para extrair lançamentos de CSV, tabelas ou texto."""
    asset_by_symbol = _asset_index(assets)
    lines = [line.strip() for line in (material or "").strip().splitlines() if line.strip()]
    if not lines:
        return {"summary": None, "items": [], "skipped": []}

    items: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    first_line = lines[0]
    delim = None
    for candidate_delim in (",", ";", "\t", "|"):
        if candidate_delim in first_line:
            delim = candidate_delim
            break

    header_detected = False
    if delim:
        reader = list(csv.reader(io.StringIO(material), delimiter=delim))
        if reader:
            header_row = [c.strip().lower() for c in reader[0]]
            date_col = _find_col(header_row, {"data", "date", "occurred_at", "timestamp", "time"})
            kind_col = _find_col(header_row, {"tipo", "kind", "type", "operacao", "operação", "lado", "side"})
            sym_col = _find_col(header_row, {"ativo", "symbol", "simbolo", "símbolo", "moeda", "coin", "asset", "par", "pair"})
            qty_col = _find_col(header_row, {"quantidade", "quantity", "qtd", "amount", "volume"})
            price_col = _find_col(header_row, {"preco", "preço", "price", "unit_price", "valor", "cotacao", "cotação"})
            fee_col = _find_col(header_row, {"taxa", "fee", "comissao", "comissão"})
            note_col = _find_col(header_row, {"nota", "note", "obs", "observacao", "observação"})

            recognized_cols = sum(1 for c in (date_col, kind_col, sym_col, qty_col, price_col) if c is not None)
            if recognized_cols >= 2:
                header_detected = True
                for row in reader[1:]:
                    if not row or not any(c.strip() for c in row):
                        continue
                    k_val = row[kind_col].strip() if kind_col is not None and kind_col < len(row) else ""
                    s_val = row[sym_col].strip().upper() if sym_col is not None and sym_col < len(row) else ""
                    if "/" in s_val:
                        s_val = s_val.split("/")[0]
                    d_raw = row[date_col].strip() if date_col is not None and date_col < len(row) else ""
                    d_val = _parse_heuristic_date(d_raw) if d_raw else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    q_val = row[qty_col].strip() if qty_col is not None and qty_col < len(row) else ""
                    p_val = row[price_col].strip() if price_col is not None and price_col < len(row) else None
                    f_val = row[fee_col].strip() if fee_col is not None and fee_col < len(row) else "0"
                    n_val = row[note_col].strip() if note_col is not None and note_col < len(row) else None

                    norm_k = _KIND_ALIASES.get(k_val.lower())
                    if not s_val and norm_k in _USDT_ONLY:
                        s_val = "USDT"

                    items.append({
                        "kind": norm_k or k_val,
                        "symbol": s_val,
                        "occurred_at": d_val,
                        "quantity": q_val,
                        "unit_price_usd": p_val,
                        "fee_usdt": f_val or "0",
                        "note": n_val,
                    })

    if not header_detected:
        for line in lines:
            orig_line = line
            occurred = _parse_heuristic_date(line)
            m_dt = re.search(r"\b(?:\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})(?:[ T]\d{2}:\d{2}(?::\d{2})?)?\b", line)
            if m_dt:
                line = line.replace(m_dt.group(0), " ")

            fee = "0"
            m_fee = re.search(r"\b(?:taxa|fee)\b(?:\s*(?:de|em|usdt|:|=))?\s*([0-9]+(?:[.,][0-9]+)?)", line, re.IGNORECASE)
            if m_fee:
                fee = m_fee.group(1)
                line = line.replace(m_fee.group(0), " ")

            kind = None
            for kw, kv in _KIND_ALIASES.items():
                pat = r"\b" + re.escape(kw) + r"\b"
                if re.search(pat, line, re.IGNORECASE):
                    kind = kv
                    line = re.sub(pat, " ", line, flags=re.IGNORECASE)
                    break

            symbol = None
            for sym in sorted(asset_by_symbol.keys(), key=len, reverse=True):
                pat = r"\b" + re.escape(sym) + r"(?:/USDT|-USDT)?\b"
                if re.search(pat, line, re.IGNORECASE):
                    symbol = sym.upper()
                    line = re.sub(pat, " ", line, flags=re.IGNORECASE)
                    break
            if not symbol and kind in _USDT_ONLY:
                symbol = "USDT"

            price = None
            m_price = re.search(
                r"(?:\b(?:por|a|preço|preco|price|cotação|cotacao|valor)\b|@)(?:\s*(?:de|em|usd|usdt|:|=))?\s*([0-9]+(?:[.,][0-9]+)?)",
                line,
                re.IGNORECASE,
            )
            if m_price:
                price = m_price.group(1)
                line = line.replace(m_price.group(0), " ")

            nums = re.findall(r"[0-9]+(?:[.,][0-9]+)?", line)
            qty = None
            if nums:
                qty = nums[0]
                if len(nums) > 1 and not price:
                    price = nums[1]

            if kind and symbol and qty:
                items.append({
                    "kind": kind,
                    "symbol": symbol,
                    "occurred_at": occurred,
                    "quantity": qty,
                    "unit_price_usd": price,
                    "fee_usdt": fee,
                    "note": None,
                })
            else:
                skipped.append({"description": orig_line[:200], "reason": "Não foi possível identificar tipo, ativo ou quantidade."})

    return normalize_operations({
        "items": items,
        "skipped": skipped,
        "summary": "Processamento local de contingência concluído.",
    }, assets)


def fallback_parse_targets(
    material: str,
    assets: list[dict[str, Any]],
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Processador local de contingência para extrair alvos de CSV, tabelas ou texto."""
    asset_by_symbol = _asset_index(assets)
    lines = [line.strip() for line in (material or "").strip().splitlines() if line.strip()]
    if not lines:
        return {"summary": None, "items": [], "skipped": []}

    items: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    first_line = lines[0]
    delim = None
    for candidate_delim in (",", ";", "\t", "|"):
        if candidate_delim in first_line:
            delim = candidate_delim
            break

    header_detected = False
    if delim:
        reader = list(csv.reader(io.StringIO(material), delimiter=delim))
        if reader:
            header_row = [c.strip().lower() for c in reader[0]]
            sym_col = _find_col(header_row, {"ativo", "symbol", "simbolo", "símbolo", "moeda", "coin", "asset", "ticker"})
            price_col = _find_col(header_row, {"preco", "preço", "price", "alvo", "target", "valor", "cotacao", "cotação"})
            active_col = _find_col(header_row, {"ativo?", "active", "status", "ativado"})
            note_col = _find_col(header_row, {"orientacao", "orientação", "obs", "observacao", "observação", "nota", "note"})

            if sym_col is not None and price_col is not None:
                header_detected = True
                for row in reader[1:]:
                    if not row or not any(c.strip() for c in row):
                        continue
                    s_val = row[sym_col].strip().upper() if sym_col < len(row) else ""
                    if "/" in s_val:
                        s_val = s_val.split("/")[0]
                    p_val = row[price_col].strip() if price_col < len(row) else ""
                    act_val = True
                    if active_col is not None and active_col < len(row):
                        raw_act = row[active_col].strip().lower()
                        if raw_act in ("false", "0", "nao", "não", "inativo"):
                            act_val = False
                    n_val = row[note_col].strip() if note_col is not None and note_col < len(row) else None
                    if s_val and p_val:
                        items.append({"symbol": s_val, "price_usd": p_val, "active": act_val, "orientation": n_val})
                    else:
                        skipped.append({"description": ",".join(row)[:200], "reason": "Símbolo ou preço alvo ausente."})

    if not header_detected:
        for line in lines:
            orig_line = line
            symbol = None
            for sym in sorted(asset_by_symbol.keys(), key=len, reverse=True):
                pat = r"\b" + re.escape(sym) + r"(?:/USDT|-USDT)?\b"
                if re.search(pat, line, re.IGNORECASE):
                    symbol = sym.upper()
                    line = re.sub(pat, " ", line, flags=re.IGNORECASE)
                    break
            if not symbol:
                skipped.append({"description": orig_line[:200], "reason": "Ativo não reconhecido nesta linha."})
                continue

            nums = re.findall(r"[0-9]+(?:[.,][0-9]+)?", line)
            if not nums:
                skipped.append({"description": orig_line[:200], "reason": "Preço alvo não encontrado nesta linha."})
                continue
            price = nums[0]
            line = line.replace(price, " ", 1)

            for filler in ("alvo de compra", "alvo", "preço", "preco", "price", "target", "usd", "usdt", "$", ":", "=", "-"):
                pat = r"\b" + re.escape(filler) + r"\b" if filler.isalnum() else re.escape(filler)
                line = re.sub(pat, " ", line, flags=re.IGNORECASE)
            orientation = " ".join(line.split()).strip().strip("()") or None

            items.append({"symbol": symbol, "price_usd": price, "active": True, "orientation": orientation})

    return normalize_targets({
        "items": items,
        "skipped": skipped,
        "summary": "Processamento local de contingência concluído.",
    }, assets, targets)
