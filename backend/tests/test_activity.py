import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from src.market_bot.app import create_app
from src.market_bot.config import Settings
from src.market_bot.core.activity import activity_overview, sender_activity
from src.market_bot.core.sheets_sync import GoogleSheetsSync, build_snapshot
from src.market_bot.db.storage import init_db
from tests.test_google_sheets import HEADERS, row


class ActivityTests(unittest.TestCase):
    def snapshot(self, rows):
        conn, counts = build_snapshot([HEADERS, *rows], [], "activity-test")
        self.addCleanup(conn.close)
        return conn, counts

    def test_reports_without_gps_are_drops(self):
        conn, counts = self.snapshot([row(), row(Name="No GPS", Latitude="", Message_Date="2026-10-13 10:00:00")])
        data = activity_overview(conn, "2026-10-13")
        self.assertEqual(counts["drops"], 2)
        self.assertEqual(counts["visits"], 1)
        self.assertEqual(data["summary"]["drop_count"], 2)
        self.assertEqual(data["summary"]["missing_gps_count"], 1)
        self.assertEqual(data["summary"]["median_gap_seconds"], 1800)
        self.assertEqual(data["senders"][0]["drop_times"], ["2026-10-13T02:30:00Z", "2026-10-13T03:00:00Z"])

    def test_no_gps_sheet_still_has_activity(self):
        conn, counts = self.snapshot([row(Latitude="", Longitude="")])
        self.assertEqual(counts["drops"], 1)
        self.assertEqual(counts["visits"], 0)
        self.assertEqual(activity_overview(conn, "2026-10-13")["summary"]["drop_count"], 1)

    def test_gaps_are_per_sender_and_in_chronological_order(self):
        conn, _ = self.snapshot([
            row(Message_Date="2026-10-13 10:30:00"),
            row(Sender_ID="456", Name="Other sender", Message_Date="2026-10-13 10:00:00"),
            row(Message_Date="2026-10-13 09:30:00"),
        ])
        data = sender_activity(conn, 123, "2026-10-13")
        self.assertEqual([d["gap_seconds"] for d in data["drops"]], [None, 3600])
        self.assertEqual(data["interval_count"], 1)

    def test_overnight_gap_is_shown_and_excluded_from_flags(self):
        conn, _ = self.snapshot([
            row(Message_Date="2026-10-12 17:00:00"),
            row(Message_Date="2026-10-13 09:30:00"),
        ])
        data = sender_activity(conn, 123, "2026-10-13", threshold_minutes=30)
        drop = data["drops"][0]
        self.assertEqual(drop["gap_seconds"], 16 * 3600 + 30 * 60)
        self.assertTrue(drop["overnight_gap"])
        self.assertFalse(drop["above_threshold"])
        self.assertEqual(data["interval_count"], 0)

    def test_cambodia_midnight_uses_local_date(self):
        conn, _ = self.snapshot([
            row(Message_Date="2026-10-13 00:10:00"),
            row(Message_Date="2026-10-13 00:30:00"),
        ])
        data = sender_activity(conn, 123, "2026-10-13")
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["drops"][1]["gap_seconds"], 1200)
        self.assertTrue(data["drops"][0]["submitted_at"].startswith("2026-10-12"))
        self.assertEqual(activity_overview(conn, "2026-10-13")["hourly"][0]["drop_count"], 2)

    def test_threshold_is_optional_and_strictly_greater(self):
        conn, _ = self.snapshot([
            row(Message_Date="2026-10-13 09:00:00"),
            row(Message_Date="2026-10-13 10:00:00"),
            row(Message_Date="2026-10-13 11:01:00"),
        ])
        plain = sender_activity(conn, 123, "2026-10-13")
        flagged = sender_activity(conn, 123, "2026-10-13", threshold_minutes=60)
        self.assertEqual(plain["above_threshold_count"], 0)
        self.assertEqual(flagged["above_threshold_count"], 1)
        self.assertEqual(flagged["longest_gap_seconds"], 3660)

    def test_pagination_keeps_previous_drop_outside_page(self):
        conn, _ = self.snapshot([
            row(Message_Date="2026-10-13 09:00:00"),
            row(Message_Date="2026-10-13 09:15:00"),
            row(Message_Date="2026-10-13 09:30:00"),
        ])
        second = sender_activity(conn, 123, "2026-10-13", limit=1, offset=1)
        self.assertEqual(second["drops"][0]["gap_seconds"], 900)
        self.assertTrue(second["has_more"])
        self.assertEqual(second["total"], 3)

    def test_blank_and_undated_rows_do_not_invent_drops(self):
        conn, counts = self.snapshot([row(), row(Name="", Raw_Text="hello"), row(Name="Undated", Message_Date="")])
        self.assertEqual(counts["drops"], 1)

    def test_no_drop_day_lists_observed_senders_without_gaps(self):
        conn, _ = self.snapshot([row()])
        data = activity_overview(conn, "2026-10-14")
        self.assertEqual(data["summary"]["drop_count"], 0)
        self.assertEqual(data["summary"]["active_senders"], 0)
        self.assertEqual(data["senders"][0]["drop_times"], [])
        self.assertEqual(len(data["senders"]), 1)
        self.assertIsNone(data["senders"][0]["average_gap_seconds"])
        self.assertEqual(data["senders"][0]["latest_observed_drop_at"], "2026-10-13T02:30:00Z")


class ActivityAPITests(unittest.TestCase):
    def test_authentication_dates_and_sender_timeline(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings(telegram_bot_token="", db_path=Path(folder) / "cache.db")
            init_db(settings.db_path)
            source = Mock()
            source.fetch_values.return_value = [
                HEADERS, row(Latitude="", Message_Date="2026-10-13 09:00:00"),
                row(Message_Date="2026-10-13 09:30:00"),
            ]
            sync = GoogleSheetsSync(settings, [], source)
            self.assertEqual(sync.refresh()["state"], "ready")
            with patch.object(Settings, "load", return_value=settings), patch("src.market_bot.app.GoogleSheetsSync", return_value=sync):
                app = create_app()
                with TestClient(app) as client:
                    self.assertEqual(client.get("/api/activity").status_code, 401)
                    self.assertEqual(client.get("/api/activity/routes").status_code, 401)
                    self.assertEqual(client.get("/api/activity/feed").status_code, 401)
                    login = client.post("/api/auth/login", json={
                        "username": "admin", "password": "cmcbmarketinsightadmin",
                    })
                    headers = {"Authorization": "Bearer " + login.json()["token"]}
                    overview = client.get("/api/activity", headers=headers)
                    self.assertEqual(overview.status_code, 200)
                    self.assertEqual(overview.json()["date"], "2026-10-13")
                    self.assertEqual(overview.json()["summary"]["drop_count"], 2)
                    self.assertEqual(overview.json()["channels"], [{"name": "test", "sender_count": 1, "drop_count": 2}])
                    self.assertEqual(overview.json()["senders"][0]["channels"], ["test"])
                    self.assertIn("source_status", overview.json())
                    self.assertEqual(overview.json()["recognition"]["cutoff"], "09:30")
                    feed = client.get("/api/activity/feed", headers=headers)
                    self.assertEqual(feed.status_code, 200)
                    self.assertEqual(feed.json()["total"], 2)
                    self.assertEqual([drop["daily_visit_count"] for drop in feed.json()["entries"]], [2, 2])
                    self.assertEqual(client.get("/api/activity/feed?late_only=true", headers=headers).json()["total"], 0)
                    self.assertEqual(client.get("/api/activity/feed?late_only=invalid", headers=headers).status_code, 422)
                    self.assertEqual([drop["drop_number"] for drop in feed.json()["entries"]], [2, 1])
                    self.assertEqual(client.get("/api/activity/feed?date=bad", headers=headers).status_code, 422)
                    self.assertEqual(client.get("/api/activity/feed?limit=0", headers=headers).status_code, 422)
                    self.assertEqual(client.get("/api/activity/feed?sender_id=-1", headers=headers).status_code, 422)
                    timeline = client.get("/api/activity/123/drops", headers=headers)
                    self.assertEqual(timeline.status_code, 200)
                    self.assertEqual(timeline.json()["drops"][1]["gap_seconds"], 1800)
                    routes = client.get("/api/activity/routes", headers=headers)
                    self.assertEqual(routes.status_code, 200)
                    self.assertEqual(routes.json()["date"], "2026-10-13")
                    self.assertEqual(routes.json()["gps_drop_count"], 1)
                    self.assertEqual(routes.json()["missing_gps_count"], 1)
                    self.assertEqual(routes.json()["tracks"][0]["color"], overview.json()["senders"][0]["color"])
                    self.assertEqual(client.get("/api/activity/routes?date=bad", headers=headers).status_code, 422)
                    self.assertEqual(client.get("/api/activity/routes?sender_id=-1", headers=headers).status_code, 422)
                    self.assertEqual(client.get("/api/activity/routes?sender_id=999", headers=headers).json()["tracks"], [])
                    self.assertEqual(client.get("/api/activity?date=bad", headers=headers).status_code, 422)
                    self.assertEqual(client.get("/api/activity/999/drops", headers=headers).status_code, 404)


if __name__ == "__main__":
    unittest.main()
