"""Exercise function cold starts, concurrent refreshes, auth and public API paths."""
import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from src.market_bot.app import create_app
from src.market_bot.config import Settings
from src.market_bot.clients.google_sheets import GoogleSheetsError
from src.market_bot.core.request_cache import RequestSheetCache
from src.market_bot.core.users_auth import UsersDirectory
from src.market_bot.db.storage import get_connection
from tests.test_google_sheets import HEADERS, row


class VercelCacheTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.settings = Settings(
            telegram_bot_token="", is_vercel=True,
            db_path=Path(folder.name) / "cache.db",
            auth_source="users", auth_secret_key="isolated-vercel-test-secret",
            google_sheets_tab="Test3", google_sheets_gid="1550076852",
        )
        self.source = Mock()
        self.source.fetch_values.return_value = [
            HEADERS,
            row(Source_Channel="A"),
            row(Source_Channel="B", Name="Other Channel", Sender_ID="456"),
        ]
        client_patch = patch("src.market_bot.core.sheets_sync.GoogleSheetsClient", return_value=self.source)
        client_patch.start()
        self.addCleanup(client_patch.stop)

    def test_concurrent_cold_requests_share_one_refresh_and_warm_reads_are_throttled(self):
        cache = RequestSheetCache(self.settings)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: cache.ensure(), range(8)))
        self.assertEqual(self.source.fetch_values.call_count, 1)
        self.assertEqual(cache.sync.status["drops"], 2)
        cache.ensure()
        self.assertEqual(self.source.fetch_values.call_count, 1)
        cache._next_check = time.monotonic() - 1
        self.source.fetch_values.return_value.append(row(Name="New Drop"))
        cache.ensure()
        self.assertEqual(self.source.fetch_values.call_count, 2)
        self.assertEqual(cache.sync.status["drops"], 3)

    def test_cold_failure_never_becomes_an_empty_success_and_retries(self):
        cache = RequestSheetCache(self.settings)
        self.source.fetch_values.side_effect = GoogleSheetsError("offline")
        for _ in range(2):
            with self.assertRaises(GoogleSheetsError):
                cache.ensure()
        self.source.fetch_values.side_effect = None
        cache.ensure()
        self.assertEqual(cache.sync.status["drops"], 2)

    def test_warm_failure_retains_snapshot_and_lost_temporary_cache_rebuilds(self):
        cache = RequestSheetCache(self.settings)
        cache.ensure()
        cache._next_check = 0
        self.source.fetch_values.side_effect = GoogleSheetsError("offline")
        cache.ensure()
        self.assertEqual(cache.sync.status["state"], "error")
        conn = get_connection(self.settings.db_path)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sales_submissions").fetchone()[0], 2)
        finally:
            conn.close()
        self.settings.db_path.unlink()
        self.source.fetch_values.side_effect = None
        cache.ensure()
        self.assertEqual(cache.sync.status["state"], "ready")
        self.assertEqual(cache.sync.status["drops"], 2)

    def make_client(self):
        settings_patch = patch.object(Settings, "load", return_value=self.settings)
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        app = create_app()
        users_source = Mock()
        users_source.fetch_values.return_value = [
            ["username", "password", "allowed_sources", "role", "is_active"],
            ["viewer", "viewer-password", "A", "rm", "TRUE"],
            ["root", "root-password", "All", "admin", "TRUE"],
        ]
        app.state.users_directory = UsersDirectory(self.settings, users_source)
        client = TestClient(app)
        self.addCleanup(client.close)
        return app, client

    def test_requests_work_without_lifespan_and_keep_channel_permissions(self):
        app, client = self.make_client()
        self.assertEqual(client.get("/api/health").status_code, 200)
        self.assertFalse(self.settings.db_path.exists())
        self.assertEqual(client.get("/api/activity/calendar").status_code, 401)
        self.source.fetch_values.assert_not_called()
        login = client.post("/api/auth/login", json={"password": "viewer-password"})
        self.assertEqual(login.status_code, 200)
        headers = {"Authorization": "Bearer " + login.json()["token"]}
        for path in ["/api/activity/calendar", "/api/activity?date=2026-10-13",
                     "/api/reports", "/api/map/geojson", "/api/sales/profile"]:
            result = client.get(path, headers=headers)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertNotIn("Other Channel", result.text)
        self.source.fetch_values.assert_called_once()
        status = client.get("/api/source/status", headers=headers).json()
        self.assertEqual(status["state"], "ready")
        self.assertNotIn("sheet", status)
        self.assertEqual(client.get("/").status_code, 404)

    def test_cold_api_failure_returns_503_instead_of_an_empty_dashboard(self):
        _, client = self.make_client()
        self.source.fetch_values.side_effect = GoogleSheetsError("offline")
        login = client.post("/api/auth/login", json={"password": "viewer-password"})
        headers = {"Authorization": "Bearer " + login.json()["token"]}
        for _ in range(2):
            result = client.get("/api/activity/calendar", headers=headers)
            self.assertEqual(result.status_code, 503)
            self.assertEqual(result.headers["retry-after"], "15")

    def test_vercel_lifespan_starts_no_background_worker(self):
        app, client = self.make_client()
        with patch("src.market_bot.app.asyncio.create_task") as create_task:
            with client:
                self.assertEqual(client.get("/api/health").status_code, 200)
            create_task.assert_not_called()
        self.assertFalse(self.settings.db_path.exists())

    def test_upload_is_rejected_instead_of_accepting_ephemeral_data(self):
        _, client = self.make_client()
        login = client.post("/api/auth/login", json={"password": "root-password"})
        result = client.post(
            "/api/transactions/upload",
            headers={"Authorization": "Bearer " + login.json()["token"]},
            files={"file": ("transactions.csv", b"example", "text/csv")},
        )
        self.assertEqual(result.status_code, 503, result.text)
        self.assertIn("persistent storage", result.json()["detail"])

    def test_missing_signing_secret_is_a_configuration_error(self):
        self.settings.auth_secret_key = ""
        _, client = self.make_client()
        response = client.post("/api/auth/login", json={"password": "viewer-password"})
        self.assertEqual(response.status_code, 503)
        self.source.fetch_values.assert_not_called()


class VercelSettingsTests(unittest.TestCase):
    def test_vercel_uses_temporary_sheet_cache_instead_of_docker_path(self):
        with patch.dict(os.environ, {
            "VERCEL": "1", "DATABASE_PATH": "/app/data/cannot-write.db",
            "GOOGLE_SHEETS_TAB": "", "GOOGLE_SHEETS_GID": "", "AUTH_SECRET_KEY": "",
        }), patch("src.market_bot.config.load_dotenv"):
            settings = Settings.load()
        self.assertTrue(settings.is_vercel)
        self.assertTrue(settings.db_path.is_relative_to(Path(tempfile.gettempdir())))
        self.assertEqual(settings.google_sheets_tab, "Test3")
        self.assertEqual(settings.google_sheets_gid, "1550076852")
        self.assertEqual(settings.auth_secret_key, "")
