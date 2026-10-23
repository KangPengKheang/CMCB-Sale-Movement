import unittest

from src.market_bot.core.activity import activity_feed, activity_overview
from src.market_bot.core.sheets_sync import build_snapshot
from tests.test_google_sheets import HEADERS, row


class DailyPulseTests(unittest.TestCase):
    def snapshot(self, rows):
        conn, _ = build_snapshot([HEADERS, *rows], [], "daily-pulse")
        self.addCleanup(conn.close)
        return conn

    def test_exact_cutoff_and_later_drops_do_not_change_start(self):
        conn = self.snapshot([
            row(Sender_ID="123", Message_Date="2026-10-13 09:29:59"),
            row(Sender_ID="124", Message_Date="2026-10-13 09:30:00"),
            row(Sender_ID="125", Message_Date="2026-10-13 09:30:01"),
            row(Sender_ID="123", Message_Date="2026-10-13 11:00:00"),
            row(Sender_ID="124", Message_Date="2026-10-13 12:00:00"),
        ])
        data = activity_overview(conn, "2026-10-13")
        people = {sender["sender_id"]: sender for sender in data["senders"]}
        self.assertEqual(people[123]["start_status"], "on_time")
        self.assertEqual(people[124]["start_status"], "on_time")
        self.assertEqual(people[125]["start_status"], "late_start")
        self.assertTrue(people[123]["is_early_bird"])
        self.assertFalse(people[124]["is_early_bird"])
        self.assertEqual(data["recognition"]["late_start_count"], 1)
        self.assertEqual(data["recognition"]["on_time_count"], 2)
        self.assertEqual(data["recognition"]["cutoff"], "09:30")

    def test_previous_day_does_not_prevent_late_start(self):
        conn = self.snapshot([
            row(Message_Date="2026-10-12 08:00:00"),
            row(Message_Date="2026-10-13 10:00:00"),
        ])
        data = activity_overview(conn, "2026-10-13")
        self.assertEqual(data["senders"][0]["start_status"], "late_start")
        self.assertEqual(data["recognition"]["early_birds"], [])
        self.assertEqual(data["senders"][0]["first_drop_at"], "2026-10-13T03:00:00Z")

    def test_missing_gps_can_be_early_bird(self):
        conn = self.snapshot([
            row(Latitude="", Longitude="", Message_Date="2026-10-13 08:00:00"),
            row(Sender_ID="456", Message_Date="2026-10-13 08:01:00"),
        ])
        early = activity_overview(conn, "2026-10-13")["recognition"]["early_birds"]
        self.assertEqual([drop["sender_id"] for drop in early], [123])
        self.assertFalse(early[0]["has_gps"])

    def test_tied_first_submissions_share_recognition(self):
        conn = self.snapshot([
            row(Sender_ID="456", Message_Date="2026-10-13 08:10:00"),
            row(Sender_ID="123", Message_Date="2026-10-13 08:10:00"),
        ])
        data = activity_overview(conn, "2026-10-13")
        self.assertEqual([drop["sender_id"] for drop in data["recognition"]["early_birds"]], [123, 456])
        self.assertTrue(all(sender["is_early_bird"] for sender in data["senders"]))

    def test_no_drop_day_is_not_late_start(self):
        conn = self.snapshot([row()])
        data = activity_overview(conn, "2026-10-14")
        self.assertEqual(data["senders"][0]["start_status"], "no_drop")
        self.assertIsNone(data["senders"][0]["first_drop_id"])
        self.assertFalse(data["senders"][0]["is_early_bird"])
        self.assertEqual(data["recognition"]["late_start_count"], 0)

    def test_midnight_uses_cambodia_day(self):
        conn = self.snapshot([
            row(Message_Date="2026-10-13T00:10:00+07:00"),
            row(Sender_ID="456", Message_Date="2026-10-13T09:31:00+07:00"),
        ])
        data = activity_overview(conn, "2026-10-13")
        self.assertTrue(data["recognition"]["early_birds"][0]["submitted_at"].startswith("2026-10-12"))
        self.assertEqual(data["recognition"]["late_start_count"], 1)

    def test_feed_latest_first_and_keeps_gaps_and_drop_numbers(self):
        conn = self.snapshot([
            row(Name="First", Message_Date="2026-10-13 09:00:00", Latitude=""),
            row(Name="Last", Message_Date="2026-10-13 10:00:00"),
            row(Sender_ID="456", Name="Other first", Message_Date="2026-10-13 09:45:00"),
            row(Sender_ID="456", Name="Other last", Message_Date="2026-10-13 10:30:00"),
        ])
        feed = activity_feed(conn, "2026-10-13", threshold_minutes=30)
        self.assertEqual([drop["merchant_name"] for drop in feed["entries"]], ["Other last", "Last", "Other first", "First"])
        self.assertEqual([drop["drop_number"] for drop in feed["entries"]], [2, 2, 1, 1])
        self.assertTrue(feed["entries"][0]["above_threshold"])
        self.assertIsNone(feed["entries"][0]["start_status"])
        self.assertEqual(feed["entries"][2]["start_status"], "late_start")
        self.assertTrue(feed["entries"][3]["is_early_bird"])
        self.assertFalse(feed["entries"][3]["has_gps"])
        filtered = activity_feed(conn, "2026-10-13", sender_id=456, limit=1, offset=1)
        self.assertEqual(filtered["total"], 2)
        self.assertEqual(filtered["entries"][0]["drop_number"], 1)
        self.assertFalse(filtered["entries"][0]["is_early_bird"])
        self.assertEqual(filtered["recognition"]["early_birds"][0]["sender_id"], 123)

    def test_feed_empty_day_and_unknown_sender(self):
        conn = self.snapshot([row()])
        self.assertEqual(activity_feed(conn, "2026-10-14")["entries"], [])
        self.assertEqual(activity_feed(conn, "2026-10-13", sender_id=999)["total"], 0)


    def test_late_feed_keeps_full_day_totals_and_first_drop_numbers(self):
        conn = self.snapshot([
            row(Sender_ID="123", Message_Date="2026-10-13 09:00:00"),
            row(Sender_ID="123", Message_Date="2026-10-13 11:00:00"),
            row(Sender_ID="456", Message_Date="2026-10-13 09:31:00", Latitude=""),
            row(Sender_ID="456", Message_Date="2026-10-13 12:00:00"),
        ])
        result = activity_feed(conn, "2026-10-13", late_only=True, limit=1)
        self.assertEqual(result["total"], 1)
        self.assertTrue(result["late_only"])
        drop = result["entries"][0]
        self.assertEqual(drop["sender_id"], 456)
        self.assertEqual(drop["drop_number"], 1)
        self.assertEqual(drop["daily_visit_count"], 2)
        self.assertEqual(drop["start_status"], "late_start")
        self.assertFalse(drop["has_gps"])
        scoped = activity_feed(conn, "2026-10-13", sender_id=123, late_only=True)
        self.assertEqual(scoped["entries"], [])

    def test_first_daily_visit_keeps_previous_date_gap(self):
        conn = self.snapshot([
            row(Message_Date="2026-10-12 17:00:00"),
            row(Message_Date="2026-10-13 10:00:00"),
        ])
        drop = activity_feed(conn, "2026-10-13")["entries"][0]
        self.assertEqual(drop["drop_number"], 1)
        self.assertEqual(drop["daily_visit_count"], 1)
        self.assertEqual(drop["gap_seconds"], 17 * 3600)
        self.assertTrue(drop["overnight_gap"])

    def test_rm_last_gap_is_latest_interval_instead_of_daily_median(self):
        conn = self.snapshot([
            row(Message_Date="2026-10-13 09:00:00"),
            row(Message_Date="2026-10-13 09:10:00"),
            row(Name="Latest report", Latitude="", Message_Date="2026-10-13 10:10:00"),
        ])
        sender = activity_overview(conn, "2026-10-13")["senders"][0]
        self.assertEqual(sender["last_gap_seconds"], 3600)
        self.assertEqual(sender["last_drop_merchant_name"], "Latest report")
        self.assertFalse(sender["last_drop_has_gps"])
        self.assertEqual(sender["median_gap_seconds"], 2100)
        self.assertFalse(sender["last_gap_overnight"])
        page = activity_feed(conn, "2026-10-13", limit=1, offset=2)
        self.assertEqual(page["entries"][0]["daily_visit_count"], 3)
        self.assertEqual(page["entries"][0]["drop_number"], 1)
        empty = activity_overview(conn, "2026-10-14")["senders"][0]
        self.assertIsNone(empty["last_gap_seconds"])
        self.assertIsNone(empty["last_drop_merchant_name"])
        self.assertFalse(empty["last_drop_has_gps"])
        self.assertFalse(empty["last_gap_overnight"])

if __name__ == "__main__":
    unittest.main()
