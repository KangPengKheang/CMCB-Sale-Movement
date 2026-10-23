import unittest

from src.market_bot.core.activity import activity_overview, activity_feed, sender_activity
from src.market_bot.core.sheets_sync import build_snapshot
from tests.test_google_sheets import HEADERS, row


class ActivityChannelTests(unittest.TestCase):
    def snapshot(self):
        conn, _ = build_snapshot([HEADERS,
            row(Source_Channel="C", Message_Date="2026-10-12 16:00:00"),
            row(Source_Channel="A", Message_Date="2026-10-13 09:00:00"),
            row(Source_Channel="  B  ", Message_Date="2026-10-13 09:15:00"),
            row(Source_Channel="A", Message_Date="2026-10-13 09:30:00"),
            row(Sender_ID="456", Sender_Name="Second RM", Source_Channel="A",
                Message_Date="2026-10-13 09:10:00", Latitude="", Longitude=""),
            row(Sender_ID="789", Sender_Name="Blank Channel RM", Source_Channel="",
                Message_Date="2026-10-13 09:25:00"),
            row(Sender_ID="999", Sender_Name="Previous Day RM", Source_Channel="A",
                Message_Date="2026-10-12 09:00:00"),
        ], [], "channel-test")
        self.addCleanup(conn.close)
        return conn

    def test_selected_date_channels_count_distinct_people_and_all_reports(self):
        data = activity_overview(self.snapshot(), "2026-10-13")
        channels = {channel["name"]: channel for channel in data["channels"]}
        self.assertEqual(set(channels), {"", "A", "B"})
        self.assertEqual(channels["A"], {"name": "A", "sender_count": 2, "drop_count": 3})
        self.assertEqual(channels["B"], {"name": "B", "sender_count": 1, "drop_count": 1})
        self.assertEqual(channels[""]["sender_count"], 1)
        self.assertEqual(data["summary"]["active_senders"], 3)
        self.assertEqual(data["summary"]["drop_count"], 5)

    def test_membership_is_per_date_handles_multiple_and_missing_channels(self):
        conn = self.snapshot()
        data = activity_overview(conn, "2026-10-13")
        people = {person["sender_id"]: person for person in data["senders"]}
        self.assertEqual(people[123]["channels"], ["A", "B"])
        self.assertEqual(people[456]["channels"], ["A"])  # Missing GPS still counts.
        self.assertEqual(people[789]["channels"], [""])
        self.assertEqual(people[999]["channels"], [])  # Yesterday's channel is not today's membership.
        yesterday = activity_overview(conn, "2026-10-12")
        old = {person["sender_id"]: person for person in yesterday["senders"]}
        self.assertEqual(old[123]["channels"], ["C"])
        self.assertEqual(old[999]["channels"], ["A"])

    def test_membership_preserves_full_day_counts_gaps_and_recognition(self):
        conn = self.snapshot()
        data = activity_overview(conn, "2026-10-13")
        person = next(person for person in data["senders"] if person["sender_id"] == 123)
        self.assertEqual(person["drop_count"], 3)
        self.assertTrue(person["is_early_bird"])
        self.assertEqual(person["first_drop_at"], "2026-10-13T02:00:00Z")
        self.assertEqual(person["median_gap_seconds"], 900)
        feed = activity_feed(conn, "2026-10-13", sender_id=123)
        self.assertEqual([entry["drop_number"] for entry in feed["entries"]], [3, 2, 1])
        self.assertEqual([entry["daily_visit_count"] for entry in feed["entries"]], [3, 3, 3])
        self.assertEqual({entry["source_channel"].strip() for entry in feed["entries"]}, {"A", "B"})
        self.assertEqual(sender_activity(conn, 123, "2026-10-13")["total"], 3)

    def test_empty_date_has_no_channel_memberships(self):
        data = activity_overview(self.snapshot(), "2026-10-14")
        self.assertEqual(data["channels"], [])
        self.assertTrue(all(person["channels"] == [] for person in data["senders"]))
