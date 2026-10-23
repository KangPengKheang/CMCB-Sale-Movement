import unittest
from datetime import datetime, timedelta

from src.market_bot.core.activity import activity_overview, movement_routes, sender_color, drop_detail
from src.market_bot.core.sheets_sync import build_snapshot
from tests.test_google_sheets import HEADERS, row


class MovementTests(unittest.TestCase):
    def snapshot(self, rows):
        conn, _ = build_snapshot([HEADERS, *rows], [], "movement-test")
        self.addCleanup(conn.close)
        return conn

    def test_routes_stay_with_sender_in_time_order_and_selected_day(self):
        conn = self.snapshot([
            row(Message_Date="2026-10-13 10:30:00", Latitude="11.58"),
            row(Sender_ID="456", Message_Date="2026-10-13 10:00:00"),
            row(Message_Date="2026-10-12 17:00:00"),
            row(Message_Date="2026-10-13 09:30:00", Latitude="11.55"),
        ])
        result = movement_routes(conn, "2026-10-13")
        self.assertEqual(result["drop_count"], 3)
        tracks = {t["sender_id"]: t for t in result["tracks"]}
        own = tracks[123]
        self.assertEqual([p["latitude"] for p in own["points"]], [11.55, 11.58])
        self.assertEqual(own["segments"][0]["gap_seconds"], 3600)
        self.assertEqual(len(own["segments"]), 1)
        self.assertEqual(len(tracks[456]["segments"]), 0)
        self.assertGreater(own["segments"][0]["distance_meters"], 3000)
        self.assertEqual(movement_routes(conn, "2026-10-13", 456)["sender_count"], 1)

    def test_missing_gps_keeps_drop_numbers_and_marks_unknown_interval(self):
        conn = self.snapshot([
            row(Message_Date="2026-10-13 09:00:00"),
            row(Message_Date="2026-10-13 09:10:00", Latitude="", Longitude=""),
            row(Message_Date="2026-10-13 09:30:00", Latitude="11.57"),
            row(Sender_ID="456", Latitude="", Longitude=""),
        ])
        result = movement_routes(conn, "2026-10-13")
        self.assertEqual(result["drop_count"], 4)
        self.assertEqual(result["missing_gps_count"], 2)
        self.assertEqual(result["gps_drop_count"], 2)
        self.assertEqual(result["sender_count"], 1)
        track = result["tracks"][0]
        self.assertEqual(track["drop_count"], 3)
        self.assertEqual([p["drop_number"] for p in track["points"]], [1, 3])
        self.assertEqual(track["segments"][0]["missing_gps_between"], 1)
        self.assertEqual(track["segments"][0]["gap_seconds"], 1800)

    def test_color_matches_overview_across_days(self):
        conn = self.snapshot([row(), row(Message_Date="2026-10-14 09:30:00")])
        first = movement_routes(conn, "2026-10-13")["tracks"][0]["color"]
        second = movement_routes(conn, "2026-10-14")["tracks"][0]["color"]
        overview = activity_overview(conn, "2026-10-13")["senders"][0]["color"]
        self.assertEqual(first, second)
        self.assertEqual(first, overview)
        self.assertRegex(first, r"^#[0-9a-f]{6}$")
        self.assertNotEqual(sender_color(123), sender_color(456))

    def test_same_coordinates_do_not_invent_movement(self):
        conn = self.snapshot([row(), row(Message_Date="2026-10-13 10:30:00")])
        track = movement_routes(conn, "2026-10-13")["tracks"][0]
        self.assertEqual(track["segments"][0]["distance_meters"], 0)
        for point in track["points"]:
            self.assertEqual(point["latitude"], track["points"][0]["latitude"])
            self.assertEqual(point["longitude"], track["points"][0]["longitude"])

    def test_all_points_are_returned_beyond_timeline_page_limit(self):
        start = datetime(2026, 10, 13, 8)
        conn = self.snapshot([
            row(Message_Date=(start + timedelta(minutes=index)).strftime("%Y-%m-%d %H:%M:%S"))
            for index in range(120)
        ])
        result = movement_routes(conn, "2026-10-13")
        self.assertEqual(result["gps_drop_count"], 120)
        self.assertEqual(len(result["tracks"][0]["segments"]), 119)

    def test_empty_day_has_no_routes(self):
        conn = self.snapshot([row()])
        result = movement_routes(conn, "2026-10-14")
        self.assertEqual(result["tracks"], [])
        self.assertEqual(result["drop_count"], 0)


class DropDetailTests(unittest.TestCase):
    def test_each_drop_has_its_own_contact_and_financial_values(self):
        conn, _ = build_snapshot([HEADERS,
            row(Tel="012345678", Business="Coffee Shop", Bank="ABA", Amount="USD 5,000",
                Interest="1.2% monthly", Loan_Type="Working capital", Maturity="2027-10-13", Status="Follow Up"),
            row(Message_Date="2026-10-13 10:30:00", Tel="098765432", Bank="ACLEDA", Amount="KHR 0",
                Interest="0%", Loan_Type="Overdraft", Maturity="24 months", Status="Pending"),
        ], [], "drop-detail-test")
        self.addCleanup(conn.close)
        points=movement_routes(conn,"2026-10-13")["tracks"][0]["points"]
        first=drop_detail(conn,points[0]["id"])
        second=drop_detail(conn,points[1]["id"])
        self.assertEqual(first["merchant_name"],"Sample Coffee")
        self.assertEqual(first["tel"],"012345678")
        self.assertEqual(first["business"],"Coffee Shop")
        self.assertEqual(first["bank"],"ABA")
        self.assertEqual(first["amount"],"USD 5,000")
        self.assertEqual(first["interest"],"1.2% monthly")
        self.assertEqual(first["loan_type"],"Working capital")
        self.assertEqual(first["maturity"],"2027-10-13")
        self.assertEqual(first["status"],"Follow Up")
        self.assertEqual(second["tel"],"098765432")
        self.assertEqual(second["amount"],"KHR 0")
        self.assertEqual(second["interest"],"0%")
        self.assertEqual(second["maturity"],"24 months")
        self.assertEqual(second["status"],"Pending")
        self.assertIsNone(drop_detail(conn,-123))

    def test_no_gps_drop_does_not_borrow_details_from_another_visit(self):
        conn,_=build_snapshot([HEADERS,row(Amount="USD 9,999"),row(
            Message_Date="2026-10-13 10:30:00",Latitude="",Longitude="",Business="Bakery")
        ],[],"drop-detail-missing")
        self.addCleanup(conn.close)
        identity=conn.execute("SELECT id FROM sales_submissions WHERE has_gps=0").fetchone()[0]
        result=drop_detail(conn,identity)
        self.assertFalse(result["report_available"])
        self.assertEqual(result["business"],"Bakery")
        self.assertIsNone(result["tel"])
        self.assertIsNone(result["amount"])

if __name__ == "__main__":
    unittest.main()
