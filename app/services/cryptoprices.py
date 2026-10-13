"""Cotação pontual em https://cryptoprices.cc/{SIMBOLO}. Uma chamada por ativo."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re

import httpx


BASE_URL = "https://cryptoprices.cc"
SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9]{1,15}$")
MAX_RESPONSE_BYTES = 64


class CryptoPricesClient:
    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=httpx.Timeout(timeout_seconds, connect=3.0),
            transport=transport,
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def fetch(self, symbol: str, *, now: datetime | None = None) -> tuple[Decimal | None, str | None]:
        """Retorna (preço, None) ou (None, código de erro). Não tenta de novo."""
        code = str(symbol or "").strip().upper()
        if not SYMBOL_PATTERN.fullmatch(code):
            return None, "invalid_symbol"
        try:
            response = self._client.get(f"/{code}")
        except httpx.TimeoutException:
            return None, "provider_timeout"
        except httpx.HTTPError:
            return None, "provider_unavailable"
        if response.status_code == 404:
            return None, "provider_unknown_symbol"
        if response.status_code != 200:
            return None, "provider_unavailable"
        if len(response.content) > MAX_RESPONSE_BYTES:
            return None, "provider_invalid_price"
        try:
            price = Decimal(response.text.strip())
        except InvalidOperation:
            return None, "provider_invalid_price"
        if not price.is_finite() or price <= 0:
            return None, "provider_invalid_price"
        return price, None

    @staticmethod
    def quoted_at(now: datetime | None = None) -> datetime:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now deve conter timezone.")
        return current.astimezone(timezone.utc)
