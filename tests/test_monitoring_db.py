"""PostgreSQL integration checks; TEST_DATABASE_URL must point to a disposable database."""

import os
import threading
import time
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services.provider_budget import ProviderBudgetService
from app.services.monitoring import MonitoringCycleService
from app.services.retention import cleanup_retained_history

try:
    import psycopg
except ImportError:  # pragma: no cover - dependency optional in lightweight environments
    psycopg = None


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
MIGRATION_FILE = Path(__file__).resolve().parents[1] / "migrations" / "003_price_monitoring.sql"


@unittest.skipUnless(
    TEST_DATABASE_URL and psycopg is not None,
    "Não verificado: configure TEST_DATABASE_URL para um PostgreSQL descartável.",
)
class MonitoringDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.migration_sql = MIGRATION_FILE.read_text(encoding="utf-8")
        # The test DSN is explicit and never falls back to the application's DATABASE_URL.
        with psycopg.connect(TEST_DATABASE_URL) as conn:
            conn.execute(cls.migration_sql)

    def role_can_be_used(self, conn):
        row = conn.execute(
            "SELECT pg_has_role(current_user, 'carteira_app', 'MEMBER'), "
            "rolbypassrls FROM pg_roles WHERE rolname = 'carteira_app'"
        ).fetchone()
        return bool(row and row[0] and not row[1])

    def test_migration_is_repeatable_and_cross_portfolio_foreign_keys_hold(self):
        with psycopg.connect(TEST_DATABASE_URL) as conn:
            conn.execute(self.migration_sql)
            tables = conn.execute(
                "SELECT to_regclass(%s), to_regclass(%s), to_regclass(%s)",
                (
                    "portfolio_private.price_targets",
                    "portfolio_private.monitoring_cycles",
                    "portfolio_private.price_notifications",
                ),
            ).fetchone()
            self.assertTrue(all(tables))

            owner_a, owner_b = uuid4(), uuid4()
            portfolio_a, portfolio_b = uuid4(), uuid4()
            asset_a, asset_b = uuid4(), uuid4()
            for owner_id, portfolio_id, asset_id in (
                (owner_a, portfolio_a, asset_a),
                (owner_b, portfolio_b, asset_b),
            ):
                conn.execute(
                    "SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),)
                )
                conn.execute(
                    "INSERT INTO portfolio_private.portfolios (id, owner_id) VALUES (%s, %s)",
                    (portfolio_id, owner_id),
                )
                conn.execute(
                    "INSERT INTO portfolio_private.assets "
                    "(id, portfolio_id, external_id, symbol, name) VALUES (%s, %s, %s, %s, %s)",
                    (asset_id, portfolio_id, f"test-{asset_id}", "TST", "Test asset"),
                )

            conn.execute(
                "SELECT set_config('app.current_user_id', %s, true)", (str(owner_a),)
            )
            with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                with conn.transaction():
                    conn.execute(
                        "INSERT INTO portfolio_private.price_targets "
                        "(portfolio_id, asset_id, kind, price_usd) VALUES (%s, %s, 'buy', 1)",
                        (portfolio_a, asset_b),
                    )

    def test_rls_and_two_connections_reserve_only_one_due_cycle(self):
        with psycopg.connect(TEST_DATABASE_URL) as conn:
            if not self.role_can_be_used(conn):
                self.skipTest("carteira_app sem membership restrita disponível no PostgreSQL de teste.")

        owner_id, portfolio_id = uuid4(), uuid4()
        with psycopg.connect(TEST_DATABASE_URL) as conn:
            conn.execute("SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),))
            conn.execute(
                "INSERT INTO portfolio_private.portfolios (id, owner_id) VALUES (%s, %s)",
                (portfolio_id, owner_id),
            )
            conn.execute(
                "INSERT INTO portfolio_private.monitoring_settings (portfolio_id) VALUES (%s)",
                (portfolio_id,),
            )
            conn.execute(
                "INSERT INTO portfolio_private.monitoring_state (portfolio_id, next_due_at) "
                "VALUES (%s, now() - interval '1 second')",
                (portfolio_id,),
            )

        other_owner = uuid4()
        try:
            # RLS hides the same row when the validated transaction identity changes.
            with psycopg.connect(TEST_DATABASE_URL) as conn:
                with conn.transaction():
                    conn.execute("SET LOCAL ROLE carteira_app")
                    conn.execute(
                        "SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),)
                    )
                    self.assertEqual(
                        conn.execute(
                            "SELECT count(*) FROM portfolio_private.monitoring_settings WHERE portfolio_id=%s",
                            (portfolio_id,),
                        ).fetchone()[0],
                        1,
                    )
                    conn.execute(
                        "SELECT set_config('app.current_user_id', %s, true)", (str(other_owner),)
                    )
                    self.assertEqual(
                        conn.execute(
                            "SELECT count(*) FROM portfolio_private.monitoring_settings WHERE portfolio_id=%s",
                            (portfolio_id,),
                        ).fetchone()[0],
                        0,
                    )

            barrier = threading.Barrier(2)
            outcomes = []
            failures = []

            def reserve_once():
                try:
                    with psycopg.connect(TEST_DATABASE_URL) as conn:
                        with conn.transaction():
                            conn.execute("SET LOCAL ROLE carteira_app")
                            conn.execute(
                                "SELECT set_config('app.current_user_id', %s, true)",
                                (str(owner_id),),
                            )
                            barrier.wait(timeout=10)
                            due_at = conn.execute(
                                "SELECT next_due_at FROM portfolio_private.monitoring_state "
                                "WHERE portfolio_id=%s FOR UPDATE",
                                (portfolio_id,),
                            ).fetchone()[0]
                            if due_at > datetime.now(timezone.utc):
                                outcomes.append(False)
                                return
                            cycle_id = uuid4()
                            conn.execute(
                                "INSERT INTO portfolio_private.monitoring_cycles "
                                "(id, portfolio_id, status, settings_revision) "
                                "VALUES (%s, %s, 'reserved', 1)",
                                (cycle_id, portfolio_id),
                            )
                            conn.execute(
                                "UPDATE portfolio_private.monitoring_state "
                                "SET current_cycle_id=%s, lease_until=now() + interval '60 seconds', "
                                "next_due_at=now() + interval '300 seconds' WHERE portfolio_id=%s",
                                (cycle_id, portfolio_id),
                            )
                            time.sleep(0.1)
                            outcomes.append(True)
                except Exception as exc:  # surfaced in the test thread below
                    failures.append(exc)

            workers = [threading.Thread(target=reserve_once) for _ in range(2)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=15)
            self.assertFalse(any(worker.is_alive() for worker in workers), "conexão concorrente não terminou")
            self.assertEqual(failures, [])
            self.assertEqual(sorted(outcomes), [False, True])
        finally:
            with psycopg.connect(TEST_DATABASE_URL) as conn:
                conn.execute(
                    "SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),)
                )
                conn.execute(
                    "DELETE FROM portfolio_private.portfolios WHERE id=%s", (portfolio_id,)
                )

    def test_two_connections_share_one_provider_budget_slot(self):
        with psycopg.connect(TEST_DATABASE_URL) as conn:
            if not self.role_can_be_used(conn):
                self.skipTest("carteira_app sem membership restrita disponível no PostgreSQL de teste.")

        owner_id, portfolio_id = uuid4(), uuid4()
        api_key = f"test-key-{uuid4()}"
        fingerprint = ProviderBudgetService.key_fingerprint(api_key)
        now = datetime.now(timezone.utc)
        window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        window_end = window_start.replace(day=1)  # replaced below with next month boundary
        if window_start.month == 12:
            window_end = window_start.replace(year=window_start.year + 1, month=1)
        else:
            window_end = window_start.replace(month=window_start.month + 1)

        with psycopg.connect(TEST_DATABASE_URL) as conn:
            conn.execute("SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),))
            conn.execute(
                "INSERT INTO portfolio_private.portfolios (id, owner_id) VALUES (%s, %s)",
                (portfolio_id, owner_id),
            )

        barrier = threading.Barrier(2)
        outcomes = []
        failures = []

        def reserve_budget():
            try:
                with psycopg.connect(TEST_DATABASE_URL) as conn:
                    with conn.transaction():
                        conn.execute("SET LOCAL ROLE carteira_app")
                        conn.execute(
                            "SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),)
                        )
                        barrier.wait(timeout=10)
                        with conn.cursor() as cur:
                            decision = ProviderBudgetService().reserve(
                                cur,
                                provider="coingecko",
                                api_key=api_key,
                                window_start=window_start,
                                window_end=window_end,
                                configured_limit=1,
                                request_count=1,
                                now=datetime.now(timezone.utc),
                            )
                        outcomes.append((decision.allowed, decision.reason))
            except Exception as exc:
                failures.append(exc)

        try:
            workers = [threading.Thread(target=reserve_budget) for _ in range(2)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=15)
            self.assertFalse(any(worker.is_alive() for worker in workers), "reserva concorrente não terminou")
            self.assertEqual(failures, [])
            self.assertEqual(sorted(allowed for allowed, _ in outcomes), [False, True])
            self.assertIn((False, "quota_exhausted"), outcomes)
        finally:
            with psycopg.connect(TEST_DATABASE_URL) as conn:
                conn.execute("SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),))
                conn.execute(
                    "DELETE FROM portfolio_private.provider_budget "
                    "WHERE provider='coingecko' AND key_fingerprint=%s",
                    (fingerprint,),
                )
                conn.execute(
                    "DELETE FROM portfolio_private.portfolios WHERE id=%s", (portfolio_id,)
                )

    def test_two_first_cycle_requests_are_deduplicated_by_service_lock(self):
        with psycopg.connect(TEST_DATABASE_URL) as conn:
            if not self.role_can_be_used(conn):
                self.skipTest("carteira_app sem membership restrita disponível no PostgreSQL de teste.")

        owner_id, portfolio_id = uuid4(), uuid4()
        with psycopg.connect(TEST_DATABASE_URL) as conn:
            conn.execute("SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),))
            conn.execute(
                "INSERT INTO portfolio_private.portfolios (id, owner_id) VALUES (%s, %s)",
                (portfolio_id, owner_id),
            )

        now = datetime.now(timezone.utc)
        settings = SimpleNamespace(
            coingecko_demo_api_key=SimpleNamespace(get_secret_value=lambda: "test-api-key"),
            coingecko_window_start=now - timedelta(days=1),
            coingecko_window_end=now + timedelta(days=29),
            coingecko_call_limit=10,
        )
        fake_client = SimpleNamespace(plan_batches=lambda ids: ([], {}))
        barrier = threading.Barrier(2)
        outcomes = []
        failures = []

        def reserve_cycle():
            try:
                with psycopg.connect(TEST_DATABASE_URL) as conn:
                    with conn.transaction():
                        conn.execute("SET LOCAL ROLE carteira_app")
                        conn.execute(
                            "SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),)
                        )
                        barrier.wait(timeout=10)
                        with conn.cursor() as cur:
                            result = MonitoringCycleService().reserve_cycle(
                                cur, portfolio_id, uuid4(), now=now
                            )
                        outcomes.append((result.state, result.http_status))
            except Exception as exc:
                failures.append(exc)

        try:
            with patch("app.services.monitoring.get_app_settings", return_value=settings), \
                 patch("app.services.monitoring.provider_configured", return_value=True), \
                 patch("app.services.monitoring.CoinGeckoClient") as client_cls:
                client_cls.return_value.__enter__.return_value = fake_client
                workers = [threading.Thread(target=reserve_cycle) for _ in range(2)]
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join(timeout=15)
            self.assertFalse(any(worker.is_alive() for worker in workers), "reserva de ciclo não terminou")
            self.assertEqual(failures, [])
            self.assertCountEqual(outcomes, [("reserved", 201), ("in_progress", 202)])
        finally:
            with psycopg.connect(TEST_DATABASE_URL) as conn:
                conn.execute("SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),))
                conn.execute(
                    "DELETE FROM portfolio_private.portfolios WHERE id=%s", (portfolio_id,)
                )

    def test_retention_removes_expired_rows_but_keeps_live_references_and_registrations(self):
        with psycopg.connect(TEST_DATABASE_URL) as conn:
            if not self.role_can_be_used(conn):
                self.skipTest("carteira_app sem membership restrita disponível no PostgreSQL de teste.")

        owner_id, portfolio_id = uuid4(), uuid4()
        asset_id, target_id = uuid4(), uuid4()
        expired_cycle_id, retained_cycle_id = uuid4(), uuid4()
        expired_eval_id, retained_eval_id = uuid4(), uuid4()
        expired_notification_id, retained_notification_id = uuid4(), uuid4()
        receipt_key = uuid4()
        api_key = f"retention-test-{uuid4()}"
        fingerprint = ProviderBudgetService.key_fingerprint(api_key)
        now = datetime.now(timezone.utc)
        expired_at = now - timedelta(days=31)
        retained_notification_at = now - timedelta(days=29)

        with psycopg.connect(TEST_DATABASE_URL) as conn:
            conn.execute("SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),))
            conn.execute(
                "INSERT INTO portfolio_private.portfolios (id, owner_id) VALUES (%s, %s)",
                (portfolio_id, owner_id),
            )
            conn.execute(
                "INSERT INTO portfolio_private.assets (id, portfolio_id, external_id, symbol, name) "
                "VALUES (%s, %s, 'bitcoin', 'BTC', 'Bitcoin')",
                (asset_id, portfolio_id),
            )
            conn.execute(
                "INSERT INTO portfolio_private.price_targets "
                "(id, portfolio_id, asset_id, kind, price_usd) VALUES (%s, %s, %s, 'buy', 60000)",
                (target_id, portfolio_id, asset_id),
            )
            conn.execute(
                "INSERT INTO portfolio_private.monitoring_cycles "
                "(id, portfolio_id, status, started_at, completed_at) "
                "VALUES (%s, %s, 'completed', %s, %s), (%s, %s, 'completed', %s, %s)",
                (expired_cycle_id, portfolio_id, expired_at, expired_at,
                 retained_cycle_id, portfolio_id, expired_at, expired_at),
            )
            conn.execute(
                "INSERT INTO portfolio_private.price_evaluations "
                "(id, portfolio_id, cycle_id, target_id, target_version, target_price_usd, "
                "target_kind, proximity_percent, result, created_at) "
                "VALUES (%s, %s, %s, %s, 1, 60000, 'buy', 10, 'inside', %s), "
                "(%s, %s, %s, %s, 1, 60000, 'buy', 10, 'inside', %s)",
                (expired_eval_id, portfolio_id, expired_cycle_id, target_id, expired_at,
                 retained_eval_id, portfolio_id, retained_cycle_id, target_id, expired_at),
            )
            conn.execute(
                "INSERT INTO portfolio_private.price_notifications "
                "(id, portfolio_id, evaluation_id, created_at) "
                "VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)",
                (expired_notification_id, portfolio_id, expired_eval_id, expired_at,
                 retained_notification_id, portfolio_id, retained_eval_id, retained_notification_at),
            )
            conn.execute(
                "INSERT INTO portfolio_private.latest_quotes "
                "(portfolio_id, asset_id, price_usd, quoted_at, provider, source_cycle_id) "
                "VALUES (%s, %s, 61000, %s, 'coingecko', %s)",
                (portfolio_id, asset_id, now, retained_cycle_id),
            )
            conn.execute(
                "INSERT INTO portfolio_private.provider_budget "
                "(provider, key_fingerprint, window_start, window_end, configured_limit) "
                "VALUES ('coingecko', %s, %s, %s, 10)",
                (fingerprint, now - timedelta(days=1), now + timedelta(days=29)),
            )
            conn.execute(
                "INSERT INTO portfolio_private.mutation_receipts "
                "(portfolio_id, key, request_hash, response_status, response_body, created_at) "
                "VALUES (%s, %s, repeat('a', 64), 200, '{}'::jsonb, %s)",
                (portfolio_id, receipt_key, expired_at),
            )

        @contextmanager
        def restricted_connection(user_id):
            with psycopg.connect(TEST_DATABASE_URL) as conn:
                conn.execute("SET LOCAL ROLE carteira_app")
                conn.execute(
                    "SELECT set_config('app.current_user_id', %s, true)", (str(user_id),)
                )
                yield conn

        try:
            result = cleanup_retained_history(
                owner_id, now=now, connection_factory=restricted_connection
            )
            self.assertEqual(result["state"], "completed")
            with psycopg.connect(TEST_DATABASE_URL) as conn:
                conn.execute("SET LOCAL ROLE carteira_app")
                conn.execute(
                    "SELECT set_config('app.current_user_id', %s, true)", (str(owner_id),)
                )
                self.assertEqual(conn.execute(
                    "SELECT count(*) FROM portfolio_private.price_notifications "
                    "WHERE id=%s", (expired_notification_id,),
                ).fetchone()[0], 0)
                for table, row_id in (
                    ("price_notifications", retained_notification_id),
                    ("price_evaluations", retained_eval_id),
                    ("monitoring_cycles", retained_cycle_id),
                    ("price_targets", target_id),
                ):
                    self.assertEqual(conn.execute(
                        f"SELECT count(*) FROM portfolio_private.{table} WHERE id=%s", (row_id,),
                    ).fetchone()[0], 1)
                self.assertEqual(conn.execute(
                    "SELECT count(*) FROM portfolio_private.latest_quotes WHERE portfolio_id=%s",
                    (portfolio_id,),
                ).fetchone()[0], 1)
                self.assertEqual(conn.execute(
                    "SELECT count(*) FROM portfolio_private.provider_budget WHERE key_fingerprint=%s",
                    (fingerprint,),
                ).fetchone()[0], 1)
                self.assertEqual(conn.execute(
                    "SELECT count(*) FROM portfolio_private.mutation_receipts WHERE key=%s",
                    (receipt_key,),
                ).fetchone()[0], 1)
        finally:
            with psycopg.connect(TEST_DATABASE_URL) as conn:
                conn.execute(
                    "DELETE FROM portfolio_private.provider_budget WHERE key_fingerprint=%s",
                    (fingerprint,),
                )
                conn.execute(
                    "DELETE FROM portfolio_private.portfolios WHERE id=%s", (portfolio_id,)
                )


if __name__ == "__main__":
    unittest.main()
