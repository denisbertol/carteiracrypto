import unittest
from decimal import Decimal

import httpx

from app.services.cryptoprices import CryptoPricesClient


class CryptoPricesClientTests(unittest.TestCase):
    def test_reads_plain_usd_price(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/BTC")
            return httpx.Response(200, text="82868\n")

        with CryptoPricesClient(transport=httpx.MockTransport(handler)) as client:
            price, error = client.fetch("btc")
        self.assertIsNone(error)
        self.assertEqual(price, Decimal("82868"))

    def test_rejects_unknown_symbol_without_calling(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            raise AssertionError("não deveria chamar a rede")

        with CryptoPricesClient(transport=httpx.MockTransport(handler)) as client:
            price, error = client.fetch("../etc/passwd")
        self.assertIsNone(price)
        self.assertEqual(error, "invalid_symbol")
