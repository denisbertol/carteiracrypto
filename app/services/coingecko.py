"""CoinGecko Demo HTTP adapter. It never retries quota-consuming requests."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
import json
import math
import re
from typing import Callable, Iterable

import httpx


BASE_URL = "https://api.coingecko.com/api/v3"
MAX_HISTORY_DAYS = 365
COIN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,199}$")
MAX_IDS_PER_REQUEST = 515
MAX_URL_LENGTH = 8 * 1024
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_QUOTE_AGE_SECONDS = 300
MAX_FUTURE_SKEW_SECONDS = 60


@dataclass(frozen=True)
class ProviderQuote:
    coin_id: str
    price_usd: Decimal
    quoted_at: datetime
    fetched_at: datetime


@dataclass
class PriceBatch:
    quotes: dict[str, ProviderQuote] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    retry_after_seconds: int | None = None
    request_count: int = 0


@dataclass
class HistoryBatch:
    points: list[tuple[datetime, Decimal]] = field(default_factory=list)
    error_code: str | None = None
    retry_after_seconds: int | None = None
    request_count: int = 0


@dataclass
class CatalogBatch:
    coins: list[dict[str, str]] = field(default_factory=list)
    error_code: str | None = None
    retry_after_seconds: int | None = None
    request_count: int = 0


def _reject_json_constant(value: str):
    raise ValueError(f"Constante JSON inválida: {value}")


class CoinGeckoClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        now: Callable[[], datetime] | None = None,
        timeout_seconds: float = 10.0,
        connect_timeout_seconds: float = 3.0,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        max_ids_per_request: int = MAX_IDS_PER_REQUEST,
        max_url_length: int = MAX_URL_LENGTH,
    ) -> None:
        if timeout_seconds <= 0 or connect_timeout_seconds <= 0:
            raise ValueError("Timeouts devem ser positivos.")
        if max_response_bytes < 1 or max_ids_per_request < 1 or max_url_length < 1:
            raise ValueError("Limites da integração devem ser positivos.")
        headers = {"x-cg-demo-api-key": api_key} if api_key else {}
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers=headers,
            timeout=httpx.Timeout(timeout_seconds, connect=connect_timeout_seconds),
            transport=transport,
            follow_redirects=False,
        )
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._max_response_bytes = max_response_bytes
        self._max_ids_per_request = min(max_ids_per_request, MAX_IDS_PER_REQUEST)
        self._max_url_length = max_url_length
        self._configured = bool(api_key)

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def _request_url_length(self, coin_ids: list[str]) -> int:
        request = self._client.build_request(
            "GET",
            "/simple/price",
            params={
                "ids": ",".join(coin_ids),
                "vs_currencies": "usd",
                "include_last_updated_at": "true",
                "precision": "full",
            },
        )
        return len(str(request.url))

    def _chunks(self, coin_ids: list[str], errors: dict[str, str]) -> Iterable[list[str]]:
        chunk: list[str] = []
        for coin_id in coin_ids:
            candidate = chunk + [coin_id]
            too_many = len(candidate) > self._max_ids_per_request
            too_long = self._request_url_length(candidate) > self._max_url_length
            if chunk and (too_many or too_long):
                yield chunk
                chunk = [coin_id]
                if self._request_url_length(chunk) > self._max_url_length:
                    errors[coin_id] = "provider_url_too_long"
                    chunk = []
            elif too_many or too_long:
                errors[coin_id] = "provider_url_too_long"
            else:
                chunk = candidate
        if chunk:
            yield chunk

    @staticmethod
    def _retry_after_seconds(value: str | None, now: datetime) -> int | None:
        if not value:
            return None
        try:
            return max(0, math.ceil(float(value)))
        except (TypeError, ValueError, OverflowError):
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0, math.ceil((retry_at - now).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                return None

    @staticmethod
    def _errors(coin_ids: list[str], code: str) -> dict[str, str]:
        return {coin_id: code for coin_id in coin_ids}

    def _read_body(self, response: httpx.Response) -> bytes | None:
        chunks = bytearray()
        for part in response.iter_bytes():
            if len(chunks) + len(part) > self._max_response_bytes:
                return None
            chunks.extend(part)
        return bytes(chunks)

    def _fetch_chunk(self, coin_ids: list[str], result: PriceBatch) -> None:
        params = {
            "ids": ",".join(coin_ids),
            "vs_currencies": "usd",
            "include_last_updated_at": "true",
            "precision": "full",
        }
        try:
            with self._client.stream("GET", "/simple/price", params=params) as response:
                if response.status_code == 429:
                    result.errors.update(self._errors(coin_ids, "provider_rate_limited"))
                    if result.retry_after_seconds is None:
                        result.retry_after_seconds = self._retry_after_seconds(
                            response.headers.get("Retry-After"), self._now()
                        )
                    return
                if response.status_code in (401, 403):
                    result.errors.update(self._errors(coin_ids, "provider_auth_failed"))
                    return
                if response.status_code >= 500:
                    result.errors.update(self._errors(coin_ids, "provider_unavailable"))
                    return
                if response.status_code < 200 or response.status_code >= 300:
                    result.errors.update(self._errors(coin_ids, "provider_bad_response"))
                    return
                body = self._read_body(response)
                if body is None:
                    result.errors.update(self._errors(coin_ids, "provider_response_too_large"))
                    return
        except httpx.TimeoutException:
            result.errors.update(self._errors(coin_ids, "provider_timeout"))
            return
        except httpx.HTTPError:
            result.errors.update(self._errors(coin_ids, "provider_network_error"))
            return

        try:
            payload = json.loads(
                body.decode("utf-8"),
                parse_float=Decimal,
                parse_int=Decimal,
                parse_constant=_reject_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            result.errors.update(self._errors(coin_ids, "provider_invalid_json"))
            return
        if not isinstance(payload, dict):
            result.errors.update(self._errors(coin_ids, "provider_invalid_json"))
            return

        fetched_at = self._now()
        if fetched_at.tzinfo is None:
            result.errors.update(self._errors(coin_ids, "invalid_clock"))
            return
        fetched_at = fetched_at.astimezone(timezone.utc)

        for coin_id in coin_ids:
            item = payload.get(coin_id)
            if not isinstance(item, dict):
                result.errors[coin_id] = "missing_price"
                continue
            try:
                raw_price = item.get("usd")
                price = raw_price if isinstance(raw_price, Decimal) else Decimal(str(raw_price))
                raw_timestamp = item.get("last_updated_at")
                timestamp = raw_timestamp if isinstance(raw_timestamp, Decimal) else Decimal(str(raw_timestamp))
                if not price.is_finite() or price <= 0:
                    raise ValueError("invalid price")
                if not timestamp.is_finite() or timestamp <= 0 or timestamp != timestamp.to_integral_value():
                    raise ValueError("invalid timestamp")
                quoted_at = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
            except (InvalidOperation, TypeError, ValueError, OverflowError, OSError):
                result.errors[coin_id] = "invalid_price_or_timestamp"
                continue

            age = (fetched_at - quoted_at).total_seconds()
            if age > MAX_QUOTE_AGE_SECONDS:
                result.errors[coin_id] = "stale_quote"
                continue
            if age < -MAX_FUTURE_SKEW_SECONDS:
                result.errors[coin_id] = "invalid_timestamp"
                continue
            result.quotes[coin_id] = ProviderQuote(
                coin_id=coin_id,
                price_usd=price,
                quoted_at=quoted_at,
                fetched_at=fetched_at,
            )

    def plan_batches(self, coin_ids: list[str] | tuple[str, ...]) -> tuple[list[list[str]], dict[str, str]]:
        """Return the exact bounded request plan so callers can reserve quota first."""
        errors: dict[str, str] = {}
        unique_ids: list[str] = []
        seen: set[str] = set()
        for raw_id in coin_ids:
            coin_id = str(raw_id).strip()
            if not coin_id or "," in coin_id or len(coin_id) > 200:
                if coin_id:
                    errors[coin_id] = "invalid_provider_id"
                continue
            if coin_id not in seen:
                seen.add(coin_id)
                unique_ids.append(coin_id)
        return list(self._chunks(unique_ids, errors)), errors

    def fetch_prices(self, coin_ids: list[str] | tuple[str, ...]) -> PriceBatch:
        """Fetch unique explicit IDs in bounded batches, returning per-asset errors."""
        result = PriceBatch()
        batches, plan_errors = self.plan_batches(coin_ids)
        result.errors.update(plan_errors)

        if not self._configured:
            result.errors.update(self._errors(list(coin_ids), "provider_not_configured"))
            return result

        for chunk in batches:
            result.request_count += 1
            self._fetch_chunk(chunk, result)
        return result

    def fetch_coin_catalog(self) -> CatalogBatch:
        """Fetch the explicit provider ID catalog, bounded and without retries."""
        result = CatalogBatch()
        if not self._configured:
            result.error_code = "provider_not_configured"
            return result
        result.request_count = 1
        try:
            with self._client.stream("GET", "/coins/list") as response:
                if response.status_code == 429:
                    result.error_code = "provider_rate_limited"
                    result.retry_after_seconds = self._retry_after_seconds(
                        response.headers.get("Retry-After"), self._now()
                    )
                    return result
                if response.status_code in (401, 403):
                    result.error_code = "provider_auth_failed"
                    return result
                if response.status_code >= 500:
                    result.error_code = "provider_unavailable"
                    return result
                if response.status_code < 200 or response.status_code >= 300:
                    result.error_code = "provider_bad_response"
                    return result
                body = self._read_body(response)
                if body is None:
                    result.error_code = "provider_response_too_large"
                    return result
        except httpx.TimeoutException:
            result.error_code = "provider_timeout"
            return result
        except httpx.HTTPError:
            result.error_code = "provider_network_error"
            return result

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            result.error_code = "provider_invalid_json"
            return result
        if not isinstance(payload, list):
            result.error_code = "provider_invalid_json"
            return result
        coins = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            coin_id, symbol, name = item.get("id"), item.get("symbol"), item.get("name")
            if isinstance(coin_id, str) and coin_id and isinstance(symbol, str) and isinstance(name, str):
                coins.append({"id": coin_id, "symbol": symbol, "name": name})
        if not coins:
            result.error_code = "provider_invalid_catalog"
            return result
        result.coins = coins
        return result

    def fetch_daily_history(self, coin_id: str, days: int = MAX_HISTORY_DAYS) -> HistoryBatch:
        """Fetch daily USD prices for one coin; one request, never retried."""
        result = HistoryBatch()
        if not self._configured:
            result.error_code = "provider_not_configured"
            return result
        if not isinstance(coin_id, str) or not COIN_ID_PATTERN.fullmatch(coin_id):
            result.error_code = "invalid_provider_id"
            return result
        if days < 1 or days > MAX_HISTORY_DAYS:
            raise ValueError("days fora do limite do plano Demo.")
        params = {"vs_currency": "usd", "days": str(days), "interval": "daily", "precision": "full"}
        result.request_count = 1
        try:
            with self._client.stream("GET", f"/coins/{coin_id}/market_chart", params=params) as response:
                if response.status_code == 429:
                    result.error_code = "provider_rate_limited"
                    result.retry_after_seconds = self._retry_after_seconds(
                        response.headers.get("Retry-After"), self._now()
                    )
                    return result
                if response.status_code in (401, 403):
                    result.error_code = "provider_auth_failed"
                    return result
                if response.status_code == 404:
                    result.error_code = "provider_unknown_coin"
                    return result
                if response.status_code >= 500:
                    result.error_code = "provider_unavailable"
                    return result
                if response.status_code < 200 or response.status_code >= 300:
                    result.error_code = "provider_bad_response"
                    return result
                body = self._read_body(response)
                if body is None:
                    result.error_code = "provider_response_too_large"
                    return result
        except httpx.TimeoutException:
            result.error_code = "provider_timeout"
            return result
        except httpx.HTTPError:
            result.error_code = "provider_network_error"
            return result

        try:
            payload = json.loads(
                body.decode("utf-8"),
                parse_float=Decimal,
                parse_int=Decimal,
                parse_constant=_reject_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            result.error_code = "provider_invalid_json"
            return result
        prices = payload.get("prices") if isinstance(payload, dict) else None
        if not isinstance(prices, list):
            result.error_code = "provider_invalid_json"
            return result

        latest_allowed = self._now().astimezone(timezone.utc).timestamp() + MAX_FUTURE_SKEW_SECONDS
        for item in prices:
            if not isinstance(item, list) or len(item) != 2:
                continue
            raw_ms, raw_price = item
            try:
                millis = raw_ms if isinstance(raw_ms, Decimal) else Decimal(str(raw_ms))
                price = raw_price if isinstance(raw_price, Decimal) else Decimal(str(raw_price))
                if not millis.is_finite() or millis <= 0 or not price.is_finite() or price <= 0:
                    continue
                seconds = millis / Decimal(1000)
                if seconds > latest_allowed:
                    continue
                stamp = datetime.fromtimestamp(float(seconds), tz=timezone.utc)
            except (InvalidOperation, TypeError, ValueError, OverflowError, OSError):
                continue
            result.points.append((stamp, price))
        if not result.points:
            result.error_code = "provider_empty_history"
        return result
