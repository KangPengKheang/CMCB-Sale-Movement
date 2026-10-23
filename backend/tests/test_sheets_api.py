import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from src.market_bot.app import create_app
from src.market_bot.config import Settings
from src.market_bot.core.sheets_sync import GoogleSheetsSync
from src.market_bot.db.storage import init_db
from tests.test_google_sheets import HEADERS, row


class SheetsAPITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.settings = Settings(
            telegram_bot_token="unused-in-sheet-mode",
            db_path=Path(self.folder.name) / "cache.db",
        )
        init_db(self.settings.db_path)
        self.values = [
            HEADERS, row(Message_Date="2026-09-17 09:30:00"),
            row(Message_Date="2026-10-13 09:30:00", Remark="signed form"),
            row(Name="Invalid Row", Latitude=""),
        ]
        self.source = Mock()
        self.source.fetch_values.return_value = self.values
        self.sync = GoogleSheetsSync(self.settings, [], self.source)
        self.assertEqual(self.sync.refresh()["state"], "ready")
        self.settings_patch = patch.object(Settings, "load", return_value=self.settings)
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.app = create_app()
        self.app.state.sheets_sync = self.sync
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        login = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "cmcbmarketinsightadmin"},
        )
        self.assertEqual(login.status_code, 200)
        self.headers = {"Authorization": "Bearer " + login.json()["token"]}

    def test_existing_admin_and_sales_apis_serve_sheet_cache(self):
        stats = self.client.get("/api/reports/stats", headers=self.headers)
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.json()["total_visits"], 2)
        self.assertEqual(stats.json()["total_merchants"], 1)
        self.assertEqual(stats.json()["total_dlq_items"], 1)
        reports = self.client.get("/api/reports", headers=self.headers).json()
        merchant_id = reports[0]["merchant_id"]
        rm_id = reports[0]["rm_id"]
        urls = [
            "/api/merchants", f"/api/merchants/{merchant_id}",
            "/api/rms", f"/api/rms/{rm_id}", "/api/map/geojson",
            "/api/map/merchants-geojson", "/api/map/khan-stats",
            "/api/reports/dlq", f"/api/reports/{reports[0]['id']}",
            "/api/sales/profile", "/api/sales/today", "/api/sales/store-map",
            "/api/sales/customers", "/api/sales/visits?time_range=all",
            f"/api/sales/merchants/{merchant_id}",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url, headers=self.headers).status_code, 200)

    def test_case_calendar_is_authenticated_and_has_four_weeks_and_thirty_days(self):
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/activity/calendar").status_code, 401)
        response = self.client.get("/api/activity/calendar", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["timezone"], "Asia/Phnom_Penh")
        self.assertEqual(len(payload["weeks"]), 4)
        self.assertEqual(len(payload["days"]), 30)
        self.assertEqual(payload["days"][-1], payload["today"])

    def test_latest_reports_and_merchant_timeline_are_chronological(self):
        reports = self.client.get("/api/reports", headers=self.headers).json()
        dates = [r["report_time"] for r in reports]
        self.assertEqual(dates, sorted(dates, reverse=True))
        timeline = self.client.get(
            f"/api/merchants/{reports[0]['merchant_id']}/timeline",
            headers=self.headers,
        ).json()
        timeline_dates = [r["report_time"] for r in timeline]
        self.assertEqual(timeline_dates, sorted(timeline_dates))
        self.assertEqual([r["visit_no"] for r in timeline], [1, 2])

    def test_source_status_requires_admin_and_health_exposes_source(self):
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/source/status").status_code, 401)
        source = self.client.get("/api/source/status", headers=self.headers)
        self.assertEqual(source.status_code, 200)
        self.assertEqual(source.json()["visits"], 2)
        self.assertEqual(source.json()["state"], "ready")
        self.assertEqual(
            self.client.get("/api/health").json()["visit_data_source"], "google_sheets"
        )

    def test_sheet_mode_lifecycle_does_not_start_telegram_poller(self):
        class LifecycleSync:
            def __init__(self):
                self.status = {"state": "ready"}
                self.started = False
                self.stopped = False

            async def run(self):
                self.started = True
                try:
                    await asyncio.Event().wait()
                finally:
                    self.stopped = True

        sync = LifecycleSync()
        with patch("src.market_bot.app.GoogleSheetsSync", return_value=sync):
            with patch("src.market_bot.app.background_polling_loop") as telegram:
                with TestClient(create_app()) as client:
                    self.assertEqual(client.get("/api/health").status_code, 200)
                    self.assertTrue(sync.started)
                    telegram.assert_not_called()
                self.assertTrue(sync.stopped)


if __name__ == "__main__":
    unittest.main()
