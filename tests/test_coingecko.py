import unittest
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.services.coingecko import CoinGeckoClient


class CoinGeckoClientTests(unittest.TestCase):
    def client(self, handler, now=None):
        return CoinGeckoClient(
            api_key="unit-test-secret",
            transport=httpx.MockTransport(handler),
            now=now or (lambda: datetime.fromtimestamp(1790000000, tz=timezone.utc)),
        )

    def test_parses_decimal_timestamp_and_marks_partial_response(self):
        def handler(request):
            self.assertEqual(request.headers["x-cg-demo-api-key"], "unit-test-secret")
            self.assertNotIn("unit-test-secret", str(request.url))
            self.assertEqual(request.url.params["vs_currencies"], "usd")
            return httpx.Response(
                200,
                content=(
                    b'{"bitcoin":{"usd":180.123456789012345678,'
                    b'"last_updated_at":1790000000}}'
                ),
                headers={"Content-Type": "application/json"},
            )

        result = self.client(handler).fetch_prices(["bitcoin", "unlisted"])
        self.assertEqual(
            result.quotes["bitcoin"].price_usd,
            Decimal("180.123456789012345678"),
        )
        self.assertEqual(
            result.quotes["bitcoin"].quoted_at,
            datetime.fromtimestamp(1790000000, tz=timezone.utc),
        )
        self.assertEqual(result.errors["unlisted"], "missing_price")

    def test_deduplicates_ids_and_splits_batches_at_provider_limit(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={})

        ids = [f"coin-{index:04d}" for index in range(516)]
        result = self.client(handler).fetch_prices(ids + [ids[0]])
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(requests[0].url.params["ids"].split(",")), 515)
        self.assertEqual(len(requests[1].url.params["ids"].split(",")), 1)
        self.assertEqual(len(result.errors), 516)

    def test_rate_limit_is_returned_without_retry(self):
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(429, headers={"Retry-After": "120"})

        result = self.client(handler).fetch_prices(["bitcoin", "ethereum"])
        self.assertEqual(calls, 1)
        self.assertEqual(result.retry_after_seconds, 120)
        self.assertEqual(result.errors, {
            "bitcoin": "provider_rate_limited",
            "ethereum": "provider_rate_limited",
        })

    def test_timeout_is_reported_per_asset_without_retry(self):
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            raise httpx.ReadTimeout("simulated timeout", request=request)

        result = self.client(handler).fetch_prices(["bitcoin"])
        self.assertEqual(calls, 1)
        self.assertEqual(result.errors["bitcoin"], "provider_timeout")

    def test_catalog_fetch_uses_explicit_ids_and_api_key_header(self):
        def handler(request):
            self.assertTrue(request.url.path.endswith("/coins/list"))
            self.assertEqual(request.headers["x-cg-demo-api-key"], "unit-test-secret")
            return httpx.Response(
                200,
                json=[{"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"}],
            )

        result = self.client(handler).fetch_coin_catalog()
        self.assertIsNone(result.error_code)
        self.assertEqual(result.request_count, 1)
        self.assertEqual(result.coins, [{"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"}])


if __name__ == "__main__":
    unittest.main()
