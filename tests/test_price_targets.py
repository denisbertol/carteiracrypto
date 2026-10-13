import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.services.portfolio import IdempotencyConflictError, RevisionConflictError
from app.services.price_targets import (
    DEFAULT_PROXIMITY_PERCENT,
    PriceTargetService,
    _decimal,
    _settings_body,
)


class TargetCursor:
    def __init__(self, asset_id):
        self.asset_id = asset_id
        self.receipts = {}
        self.target = None
        self.result = None
        self.target_inserts = 0
        self.now = datetime(2026, 9, 28, tzinfo=timezone.utc)

    def execute(self, query, params=None):
        sql = " ".join(query.lower().split())
        params = params or ()
        if sql.startswith("select pg_advisory_xact_lock"):
            self.result = None
        elif "from portfolio_private.mutation_receipts" in sql:
            key = str(params[1])
            self.result = self.receipts.get(key)
        elif "select id from portfolio_private.assets" in sql:
            self.result = (self.asset_id,) if params[1] == str(self.asset_id) else None
        elif sql.startswith("insert into portfolio_private.price_targets"):
            target_id, _, asset_id, kind, price, active, orientation = params
            self.target = (
                target_id, asset_id, kind, price, active, orientation, 1, self.now, self.now
            )
            self.target_inserts += 1
            self.result = None
        elif sql.startswith("select id, asset_id, kind, price_usd"):
            self.result = self.target
        elif sql.startswith("delete from portfolio_private.price_targets"):
            self.target = None
            self.result = None
        elif sql.startswith("insert into portfolio_private.monitoring_changes"):
            self.result = None
        elif sql.startswith("insert into portfolio_private.mutation_receipts"):
            key = str(params[1])
            self.receipts[key] = (params[2], params[3], json.loads(params[4]))
            self.result = None
        else:
            raise AssertionError(f"SQL não esperado: {sql}")

    def fetchone(self):
        return self.result


class PriceTargetServiceTests(unittest.TestCase):
    def test_settings_default_and_decimal_limits(self):
        self.assertEqual(DEFAULT_PROXIMITY_PERCENT, Decimal("10.00"))
        self.assertEqual(_settings_body(None)["proximity_percent"], "10.00")
        self.assertEqual(_decimal("0", "proximity_percent", positive=False, scale=2), Decimal("0"))
        self.assertEqual(_decimal("100", "proximity_percent", positive=False, scale=2), Decimal("100"))
        for value in ("-0.01", "100.01", "NaN", "1.001"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _decimal(value, "proximity_percent", positive=False, scale=2)
        for value in ("0", "-1", "NaN", "Infinity", "0.0000000000000000001"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _decimal(value, "price_usd", positive=True, scale=18)

    def test_create_replays_identical_idempotency_key_without_duplicate(self):
        asset_id, portfolio_id, owner_id, idempotency_key = uuid4(), uuid4(), uuid4(), uuid4()
        cur = TargetCursor(asset_id)
        service = PriceTargetService()
        args = {
            "asset_id": asset_id,
            "kind": "buy",
            "price_usd": Decimal("90.25"),
            "active": True,
            "orientation": "acumular",
            "idempotency_key": idempotency_key,
        }
        first, replayed = service.create_target(cur, portfolio_id, owner_id, **args)
        second, replayed_again = service.create_target(cur, portfolio_id, owner_id, **args)
        self.assertFalse(replayed)
        self.assertTrue(replayed_again)
        self.assertEqual(first, second)
        self.assertEqual(cur.target_inserts, 1)

    def test_reusing_key_with_different_target_conflicts(self):
        asset_id, portfolio_id, owner_id, idempotency_key = uuid4(), uuid4(), uuid4(), uuid4()
        cur = TargetCursor(asset_id)
        service = PriceTargetService()
        base = {
            "asset_id": asset_id,
            "kind": "buy",
            "price_usd": Decimal("90"),
            "active": True,
            "orientation": None,
            "idempotency_key": idempotency_key,
        }
        service.create_target(cur, portfolio_id, owner_id, **base)
        with self.assertRaises(IdempotencyConflictError):
            service.create_target(
                cur, portfolio_id, owner_id, **{**base, "price_usd": Decimal("91")}
            )
        self.assertEqual(cur.target_inserts, 1)

    def test_delete_target_success_and_idempotent_replay(self):
        asset_id, portfolio_id, owner_id, idempotency_key = uuid4(), uuid4(), uuid4(), uuid4()
        cur = TargetCursor(asset_id)
        service = PriceTargetService()
        target, _ = service.create_target(
            cur, portfolio_id, owner_id,
            asset_id=asset_id, kind="buy", price_usd=Decimal("50000"),
            active=True, orientation=None, idempotency_key=uuid4(),
        )
        target_id = target["id"]
        result, replayed = service.delete_target(
            cur, portfolio_id, owner_id, target_id,
            expected_version=1, idempotency_key=idempotency_key,
        )
        self.assertFalse(replayed)
        self.assertTrue(result["deleted"])
        self.assertEqual(result["id"], str(target_id))

        # Replay with same idempotency key
        replayed_result, replayed_flag = service.delete_target(
            cur, portfolio_id, owner_id, target_id,
            expected_version=1, idempotency_key=idempotency_key,
        )
        self.assertTrue(replayed_flag)
        self.assertEqual(replayed_result, result)

    def test_delete_target_not_found(self):
        cur = TargetCursor(uuid4())
        service = PriceTargetService()
        with self.assertRaises(LookupError):
            service.delete_target(cur, uuid4(), uuid4(), uuid4())

    def test_delete_target_version_conflict(self):
        asset_id, portfolio_id, owner_id = uuid4(), uuid4(), uuid4()
        cur = TargetCursor(asset_id)
        service = PriceTargetService()
        target, _ = service.create_target(
            cur, portfolio_id, owner_id,
            asset_id=asset_id, kind="buy", price_usd=Decimal("50000"),
            active=True, orientation=None, idempotency_key=uuid4(),
        )
        with self.assertRaises(RevisionConflictError):
            service.delete_target(cur, portfolio_id, owner_id, target["id"], expected_version=99)


if __name__ == "__main__":
    unittest.main()
