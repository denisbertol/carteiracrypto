import unittest
from decimal import Decimal

from app.domain.monitoring import classify_target


class MonitoringDomainTests(unittest.TestCase):
    def classify(self, target, quote, limit):
        return classify_target(Decimal(target), Decimal(quote), Decimal(limit))

    def test_distance_is_absolute_and_boundary_is_inside(self):
        for quote in ("90", "110"):
            with self.subTest(quote=quote):
                result = self.classify("100", quote, "10")
                self.assertEqual(result.distance_percent, Decimal("10"))
                self.assertEqual(result.result, "inside")

        outside = self.classify("100", "89.99", "10")
        self.assertEqual(outside.distance_percent, Decimal("10.01"))
        self.assertEqual(outside.result, "outside")

    def test_zero_and_hundred_percent_limits_are_inclusive(self):
        self.assertEqual(self.classify("100", "100", "0").result, "inside")
        self.assertEqual(self.classify("100", "100.01", "0").result, "outside")
        self.assertEqual(self.classify("100", "50", "100").result, "inside")
        self.assertEqual(self.classify("100", "201", "100").result, "outside")

    def test_each_valid_cycle_can_produce_an_independent_inside_result(self):
        results = [self.classify("100", quote, "10").result for quote in ("95", "96", "97")]
        self.assertEqual(results, ["inside", "inside", "inside"])

    def test_invalid_prices_and_limits_are_rejected(self):
        invalid_values = (
            ("0", "100", "10"),
            ("-1", "100", "10"),
            ("100", "0", "10"),
            ("100", "NaN", "10"),
            ("Infinity", "100", "10"),
            ("100", "101", "-0.01"),
            ("100", "101", "100.01"),
        )
        for target, quote, limit in invalid_values:
            with self.subTest(target=target, quote=quote, limit=limit):
                with self.assertRaises(ValueError):
                    self.classify(target, quote, limit)


if __name__ == "__main__":
    unittest.main()
