import unittest
from datetime import date

from src.market_bot.core.activity_calendar import activity_calendar
from src.market_bot.core.sheets_sync import build_snapshot
from src.market_bot.core.source_scope import restrict_connection
from tests.test_google_sheets import HEADERS, row


class ActivityCalendarTests(unittest.TestCase):
    def snapshot(self, records):
        conn, _ = build_snapshot([HEADERS, *records], [], "calendar-test")
        self.addCleanup(conn.close)
        return conn

    def test_four_weeks_thirty_days_and_case_drop_counts(self):
        no_gps = row(Message_Date="2026-10-23 09:00:00", Latitude="", Longitude="")
        conn = self.snapshot([
            row(Message_Date="2026-09-23 09:00:00"),
            row(Message_Date="2026-09-24 09:00:00"),
            row(Message_Date="2026-09-27 23:55:00"),
            row(Message_Date="2026-09-28 00:05:00"),
            row(Message_Date="2026-10-05 09:00:00"),
            row(Message_Date="2026-10-18 23:55:00"),
            row(Message_Date="2026-10-19 00:05:00"),
            no_gps, no_gps,
            row(Message_Date="2026-10-24 09:00:00", Sender_Name="Future name"),
            row(Sender_ID="456", Sender_Name="Historical person", Message_Date="2026-09-01 09:00:00"),
        ])
        data = activity_calendar(conn, date(2026, 10, 23))
        self.assertEqual(len(data["days"]), 30)
        self.assertEqual(data["days"][0], "2026-09-24")
        self.assertEqual(data["days"][-1], "2026-10-23")
        self.assertEqual([week["start"] for week in data["weeks"]], [
            "2026-10-19", "2026-10-12", "2026-10-05", "2026-09-28",
        ])
        people = {person["sender_id"]: person for person in data["senders"]}
        self.assertEqual(people[123]["weekly_counts"], [2, 1, 1, 1])
        self.assertEqual(people[123]["total_cases"], 7)
        self.assertEqual(people[123]["active_days"], 7)
        self.assertEqual(people[123]["daily_counts"][-1], 1)  # No GPS still counts; duplicate only once.
        self.assertNotEqual(people[123]["sender_name"], "Future name")
        self.assertEqual(people[456]["daily_counts"], [0] * 30)
        self.assertEqual(people[456]["weekly_counts"], [0] * 4)

    def test_sunday_monday_and_year_boundary(self):
        conn = self.snapshot([
            row(Message_Date="2025-12-28 23:59:00"),
            row(Message_Date="2025-12-29 00:01:00"),
            row(Message_Date="2026-01-04 23:59:00"),
            row(Message_Date="2026-01-05 00:01:00"),
        ])
        sunday = activity_calendar(conn, date(2026, 1, 4))
        monday = activity_calendar(conn, date(2026, 1, 5))
        self.assertEqual(sunday["weeks"][0]["start"], "2025-12-29")
        self.assertEqual(sunday["senders"][0]["weekly_counts"][:2], [2, 1])
        self.assertEqual(monday["weeks"][0]["start"], "2026-01-05")
        self.assertEqual(monday["senders"][0]["weekly_counts"][:3], [1, 2, 1])
        self.assertEqual(monday["days"][0], "2025-12-07")

    def test_current_calendar_does_not_shift_to_historical_sheet_date(self):
        conn = self.snapshot([row(Message_Date="2025-01-01 09:00:00")])
        data = activity_calendar(conn, date(2026, 10, 23))
        self.assertEqual(data["today"], "2026-10-23")
        self.assertEqual(data["senders"][0]["total_cases"], 0)
        self.assertEqual(data["senders"][0]["daily_counts"], [0] * 30)

    def test_counts_and_roster_respect_allowed_channels(self):
        conn = self.snapshot([
            row(Source_Channel="Source A", Message_Date="2026-10-23 09:00:00"),
            row(Source_Channel="Source B", Message_Date="2026-10-23 10:00:00"),
            row(Source_Channel="Source B", Sender_ID="456", Sender_Name="Private person",
                Message_Date="2026-10-23 11:00:00"),
        ])
        restrict_connection(conn, ["Source A"], activity_only=True)
        data = activity_calendar(conn, date(2026, 10, 23))
        self.assertEqual(len(data["senders"]), 1)
        self.assertEqual(data["senders"][0]["sender_id"], 123)
        self.assertEqual(data["senders"][0]["total_cases"], 1)
        self.assertEqual(data["senders"][0]["weekly_counts"][0], 1)
        self.assertNotIn("Private person", str(data))

    def test_empty_scoped_roster_has_all_date_columns(self):
        conn = self.snapshot([row(Source_Channel="Source B")])
        restrict_connection(conn, [], activity_only=True)
        data = activity_calendar(conn, date(2026, 10, 23))
        self.assertEqual(data["senders"], [])
        self.assertEqual(len(data["weeks"]), 4)
        self.assertEqual(len(data["days"]), 30)
