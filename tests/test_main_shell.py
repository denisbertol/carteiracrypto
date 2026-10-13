import asyncio
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.routing import APIRoute
from starlette.requests import Request

from app.main import _maintenance_loop, app, health_ready, home
from app.routes.api import get_current_user_id


class MainShellTests(unittest.TestCase):
    def test_public_home_returns_shell_without_database_or_financial_values(self):
        request = Request({
            "type": "http", "method": "GET", "path": "/", "headers": [],
            "query_string": b"", "server": ("test", 80),
        })
        with patch("app.main.get_db_connection", side_effect=AssertionError("GET / não deve consultar banco")):
            response = home(request)
        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="app-shell"', body)
        self.assertIn("Entre para consultar sua carteira.", body)
        self.assertNotIn("Saldo Total", body)
        self.assertNotIn("USDT", body)
        self.assertNotIn("$", body)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_public_home_contains_dormant_post_login_splash_with_video_and_progress(self):
        request = Request({
            "type": "http", "method": "GET", "path": "/", "headers": [],
            "query_string": b"", "server": ("test", 80),
        })
        response = home(request)
        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('<body class="has-splash">', body)
        self.assertIn('<div id="splash"', body)
        self.assertIn('hidden', body)
        self.assertIn('abertura_carteiracrypto.mp4', body)
        self.assertIn('id="splash-progress-bar"', body)
        self.assertIn('id="splash-status-text"', body)
        self.assertIn('splash.js', body)

    def test_public_home_contains_mobile_viewport_and_google_login_elements(self):
        request = Request({
            "type": "http", "method": "GET", "path": "/", "headers": [],
            "query_string": b"", "server": ("test", 80),
        })
        response = home(request)
        body = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn('viewport-fit=cover', body)
        self.assertIn('theme-color', body)
        self.assertIn('id="google-login-btn"', body)
        self.assertIn('Entrar com o Google', body)
        self.assertIn('id="login-container"', body)
        self.assertIn('id="toggle-password"', body)

    def test_dashboard_route_has_bearer_dependency_and_anonymous_request_is_rejected(self):
        self.assertIn("/api/v1/dashboard", app.openapi()["paths"])
        self.assertIn("/api/v1/notifications", app.openapi()["paths"])
        routes = list(app.routes)
        for included in app.routes:
            router = getattr(included, "original_router", None)
            if router is not None:
                routes.extend(router.routes)
        dashboard_route = next(route for route in routes
                               if isinstance(route, APIRoute) and route.path == "/api/v1/dashboard")
        self.assertIn(get_current_user_id, [dependency.call for dependency in dashboard_route.dependant.dependencies])
        with self.assertRaises(HTTPException) as raised:
            get_current_user_id(None)
        self.assertEqual(raised.exception.status_code, 401)

    def test_readiness_error_does_not_echo_connection_details(self):
        with patch("app.main.get_db_connection", side_effect=RuntimeError("postgres://private-host/secret")):
            response = health_ready()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private-host", response.body.decode("utf-8"))
        self.assertNotIn("secret", response.body.decode("utf-8"))


class MainMaintenanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_reconciles_before_retention_and_schedules_sixty_seconds(self):
        owner_id = uuid4()
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        order = []

        def reconcile(user_id):
            order.append(("recovery", user_id))
            return {"state": "completed", "reconciled": 0}

        def cleanup(user_id):
            order.append(("retention", user_id))
            loop.call_soon_threadsafe(stop_event.set)

        async def wait_for_stop(awaitable, timeout):
            self.assertEqual(timeout, 60)
            await awaitable

        with patch("app.main.reconcile_expired_cycles", side_effect=reconcile), \
             patch("app.main.cleanup_retained_history", side_effect=cleanup), \
             patch("app.main.asyncio.wait_for", new=wait_for_stop):
            await _maintenance_loop(owner_id, stop_event)

        self.assertEqual(order, [("recovery", owner_id), ("retention", owner_id)])

    async def test_retention_is_skipped_when_reconciliation_fails(self):
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        def fail_recovery(user_id):
            loop.call_soon_threadsafe(stop_event.set)
            raise RuntimeError("private database detail")

        async def wait_for_stop(awaitable, timeout):
            self.assertEqual(timeout, 60)
            await awaitable

        with patch("app.main.reconcile_expired_cycles", side_effect=fail_recovery), \
             patch("app.main.cleanup_retained_history") as cleanup, \
             patch("app.main.asyncio.wait_for", new=wait_for_stop):
            await _maintenance_loop(uuid4(), stop_event)
        cleanup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
