import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.config import Settings, provider_configured


class MonitoringConfigTests(unittest.TestCase):
    def settings(self, **values):
        with patch.dict(os.environ, values, clear=True):
            return Settings()

    def test_default_has_no_external_or_fake_prices(self):
        settings = self.settings(QUOTE_MODE="unavailable")
        self.assertEqual(settings.quote_mode, "unavailable")
        self.assertFalse(provider_configured(settings, datetime.now(timezone.utc)))

    def test_cryptoprices_does_not_need_a_key_or_window(self):
        settings = self.settings(QUOTE_MODE="cryptoprices")
        self.assertTrue(provider_configured(settings, datetime.now(timezone.utc)))

    def test_production_rejects_both_fake_modes(self):
        for mode in ("fixture", "mock_stale"):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.settings(APP_ENV="production", QUOTE_MODE=mode)

    def test_configuration_window_and_secret(self):
        settings = self.settings(QUOTE_MODE="coingecko", COINGECKO_DEMO_API_KEY="unit-secret",
                                 COINGECKO_WINDOW_START="2026-09-01T00:00:00Z",
                                 COINGECKO_WINDOW_END="2026-10-01T00:00:00Z")
        self.assertTrue(provider_configured(settings, datetime(2026, 9, 15, tzinfo=timezone.utc)))
        self.assertFalse(provider_configured(settings, datetime(2026, 10, 1, tzinfo=timezone.utc)))
        self.assertNotIn("unit-secret", repr(settings))
        self.assertNotIn("unit-secret", str(settings.coingecko_demo_api_key))

    def test_invalid_window_and_limit(self):
        for values in ({"COINGECKO_CALL_LIMIT": "0"},
                       {"COINGECKO_WINDOW_START": "2026-09-01T00:00:00Z"},
                       {"COINGECKO_WINDOW_START": "2026-09-01T00:00:00",
                        "COINGECKO_WINDOW_END": "2026-10-01T00:00:00"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.settings(**values)
