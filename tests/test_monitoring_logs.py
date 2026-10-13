"""Check that monitoring failures cannot leak secrets or portfolio data to logs."""

import json
import logging
import unittest

from app.logging import JsonFormatter


class MonitoringLogTests(unittest.TestCase):
    def test_cycle_failure_redacts_credentials_and_financial_fields(self):
        canaries = (
            "eyJsecret.jwt.payload",
            "coin-gecko-secret",
            "postgres-password",
            "private-orientation",
            "987654.32",
        )
        message = (
            "cycle failed Bearer eyJsecret.jwt.payload "
            "x-cg-demo-api-key=coin-gecko-secret "
            "postgresql://carteira_app:postgres-password@localhost/db "
            "orientation=private-orientation balance_usd=987654.32"
        )
        record = logging.LogRecord("monitoring", logging.ERROR, __file__, 1, message, (), None)

        result = json.loads(JsonFormatter().format(record))

        self.assertEqual(result["level"], "ERROR")
        self.assertIn("cycle failed", result["message"])
        self.assertIn("[REDACTED]", result["message"])
        for secret in canaries:
            self.assertNotIn(secret, result["message"])

    def test_exception_text_is_redacted(self):
        try:
            raise RuntimeError("refresh_token=refresh-secret price_usd=12345.67")
        except RuntimeError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            "monitoring", logging.ERROR, __file__, 1, "provider unavailable", (), exc_info
        )
        result = json.loads(JsonFormatter().format(record))

        self.assertIn("provider unavailable", result["message"])
        self.assertIn("[REDACTED]", result["exception"])
        self.assertNotIn("refresh-secret", result["exception"])
        self.assertNotIn("12345.67", result["exception"])


if __name__ == "__main__":
    unittest.main()
