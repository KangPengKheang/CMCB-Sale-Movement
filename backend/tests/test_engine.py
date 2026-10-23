import json
import sqlite3
import time
import unittest
from pathlib import Path
from src.market_bot.core.engine import process_update
from src.market_bot.db.storage import get_all_merchants, get_all_reports, get_dlq_items, init_db, sweep_expired_events


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("data/test_engine_temp.db")
        if self.db_path.exists():
            self.db_path.unlink()
        init_db(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.pp_features = []

    def tearDown(self):
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_form_first_then_location(self):
        # Step 1: Form arrives from User 100
        form_update = {
            "update_id": 1,
            "message": {
                "message_id": 501,
                "date": int(time.time()),
                "chat": {"id": -10012345},
                "from": {"id": 100, "first_name": "Sreyphim", "last_name": "Nuth"},
                "photo": [{"file_id": "photo_1"}],
                "caption": (
                    "Name: Moew Milk Tea\n"
                    "Tel: 098391998\n"
                    "Business: Milk Tea\n"
                    "Purpose: CMCB Products\n"
                    "Bank: AC(KHQR)\n"
                    "Amount: N/A\n"
                    "Interest: N/A\n"
                    "Loan Type: N/A\n"
                    "Tenure: N/A\n"
                    "Maturity: N/A\n"
                    "Status: New\n"
                    "Potential H/M/L: L\n"
                    "Potential Product: KHQR\n"
                    "Remark: New visited and signed form"
                ),
            },
        }
        res1 = process_update(self.conn, form_update, self.pp_features)
        self.assertIsNone(res1)  # Buffered, waiting for location

        # Step 2: Location arrives 10 seconds later from same User 100
        loc_update = {
            "update_id": 2,
            "message": {
                "message_id": 502,
                "date": int(time.time()) + 10,
                "chat": {"id": -10012345},
                "from": {"id": 100, "first_name": "Sreyphim", "last_name": "Nuth"},
                "location": {"latitude": 11.5911, "longitude": 104.8749},
            },
        }
        res2 = process_update(self.conn, loc_update, self.pp_features)
        self.assertIsNotNone(res2)
        self.assertEqual(res2.merchant_name, "Moew Milk Tea")
        self.assertEqual(res2.sender_name, "Sreyphim Nuth")
        self.assertAlmostEqual(res2.latitude, 11.5911)

        reports = get_all_reports(self.conn)
        self.assertEqual(len(reports), 1)

    def test_in_place_edit_form_after_pairing(self):
        # 1. Initial pairing
        form_update = {
            "update_id": 10,
            "message": {
                "message_id": 801,
                "date": int(time.time()),
                "chat": {"id": -10012345},
                "from": {"id": 100, "first_name": "Samol", "last_name": "Touch"},
                "caption": (
                    "Name: PHa789\n"
                    "Tel: TG\n"
                    "Business: Restaurant\n"
                    "Purpose: CMCB Products\n"
                    "Bank: AC/ ABA\n"
                    "Amount: N/A\n"
                    "Interest: N/A\n"
                    "Loan Type: N/A\n"
                    "Tenure: N/A\n"
                    "Maturity: N/A\n"
                    "Status: OP\n"
                    "Potential H/M/L: L\n"
                    "Potential Product: KHQR\n"
                    "Remark: New visit"
                ),
            },
        }
        loc_update = {
            "update_id": 11,
            "message": {
                "message_id": 802,
                "date": int(time.time()) + 5,
                "chat": {"id": -10012345},
                "from": {"id": 100, "first_name": "Samol", "last_name": "Touch"},
                "location": {"latitude": 11.5514, "longitude": 104.8915},
            },
        }
        process_update(self.conn, form_update, self.pp_features)
        res_initial = process_update(self.conn, loc_update, self.pp_features)
        self.assertIsNotNone(res_initial)
        self.assertEqual(res_initial.merchant_name, "PHa789")

        # 2. Sales Rep edits message 801 to fix typo -> PH0789
        edited_update = {
            "update_id": 12,
            "edited_message": {
                "message_id": 801,
                "date": int(time.time()),
                "chat": {"id": -10012345},
                "from": {"id": 100, "first_name": "Samol", "last_name": "Touch"},
                "caption": (
                    "Name: PH0789\n"
                    "Tel: TG\n"
                    "Business: Restaurant\n"
                    "Purpose: CMCB Products\n"
                    "Bank: AC/ ABA\n"
                    "Amount: N/A\n"
                    "Interest: N/A\n"
                    "Loan Type: N/A\n"
                    "Tenure: N/A\n"
                    "Maturity: N/A\n"
                    "Status: OP\n"
                    "Potential H/M/L: L\n"
                    "Potential Product: KHQR\n"
                    "Remark: New visit"
                ),
            },
        }
        res_edited = process_update(self.conn, edited_update, self.pp_features)
        self.assertIsNotNone(res_edited)
        self.assertEqual(res_edited.merchant_name, "PH0789")

        # Confirm zero duplicate rows in merchant_reports
        reports = get_all_reports(self.conn)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["merchant_name"], "PH0789")

        # Confirm merchant table has the updated canonical name
        merchants = get_all_merchants(self.conn)
        self.assertEqual(len(merchants), 1)
        self.assertEqual(merchants[0]["canonical_name"], "PH0789")

    def test_in_place_location_edit_after_pairing(self):
        # Initial pairing
        form_update = {
            "update_id": 20,
            "message": {
                "message_id": 901,
                "date": int(time.time()),
                "chat": {"id": -10012345},
                "from": {"id": 100, "first_name": "Samol", "last_name": "Touch"},
                "caption": (
                    "Name: Test Store\n"
                    "Tel: TG\n"
                    "Business: Restaurant\n"
                    "Purpose: CMCB Products\n"
                    "Bank: AC/ ABA\n"
                    "Amount: N/A\n"
                    "Interest: N/A\n"
                    "Loan Type: N/A\n"
                    "Tenure: N/A\n"
                    "Maturity: N/A\n"
                    "Status: OP\n"
                    "Potential H/M/L: L\n"
                    "Potential Product: KHQR\n"
                    "Remark: New visit"
                ),
            },
        }
        loc_update = {
            "update_id": 21,
            "message": {
                "message_id": 902,
                "date": int(time.time()) + 5,
                "chat": {"id": -10012345},
                "from": {"id": 100, "first_name": "Samol", "last_name": "Touch"},
                "location": {"latitude": 11.5000, "longitude": 104.8000},
            },
        }
        process_update(self.conn, form_update, self.pp_features)
        process_update(self.conn, loc_update, self.pp_features)

        # Rep updates GPS pin 902
        edited_loc_update = {
            "update_id": 22,
            "edited_message": {
                "message_id": 902,
                "date": int(time.time()) + 5,
                "chat": {"id": -10012345},
                "from": {"id": 100, "first_name": "Samol", "last_name": "Touch"},
                "location": {"latitude": 11.5999, "longitude": 104.8999},
            },
        }
        process_update(self.conn, edited_loc_update, self.pp_features)

        reports = get_all_reports(self.conn)
        self.assertEqual(len(reports), 1)
        self.assertAlmostEqual(reports[0]["latitude"], 11.5999)

    def test_location_first_then_form(self):
        loc_update = {
            "update_id": 30,
            "message": {
                "message_id": 601,
                "date": int(time.time()),
                "chat": {"id": -10012345},
                "from": {"id": 200, "first_name": "Lach", "last_name": "Chanthy"},
                "location": {"latitude": 11.5915, "longitude": 104.8750},
            },
        }
        process_update(self.conn, loc_update, self.pp_features)

        form_update = {
            "update_id": 31,
            "message": {
                "message_id": 602,
                "date": int(time.time()) + 15,
                "chat": {"id": -10012345},
                "from": {"id": 200, "first_name": "Lach", "last_name": "Chanthy"},
                "caption": (
                    "Name: Panel 598\n"
                    "Tel: Telegram\n"
                    "Business: Flower\n"
                    "Purpose: CMCB Products\n"
                    "Bank: CMCB (POS)\n"
                    "Amount: N/A\n"
                    "Interest: N/A\n"
                    "Loan Type: N/A\n"
                    "Tenure: N/A\n"
                    "Maturity: N/A\n"
                    "Status: Existing customer\n"
                    "Potential H/M/L: L\n"
                    "Potential Product: POS,KHQR\n"
                    "Remark: Return POS machine"
                ),
            },
        }
        res2 = process_update(self.conn, form_update, self.pp_features)
        self.assertIsNotNone(res2)
        self.assertEqual(res2.merchant_name, "Panel 598")
        self.assertAlmostEqual(res2.latitude, 11.5915)

    def test_sweep_expired_event(self):
        past_time = int(time.time()) - 1000
        form_update = {
            "update_id": 40,
            "message": {
                "message_id": 701,
                "date": past_time,
                "chat": {"id": -10012345},
                "from": {"id": 300, "first_name": "Channa", "last_name": "Thor"},
                "caption": (
                    "Name: Peach Petroleum\n"
                    "Tel: TG\n"
                    "Business: Gasoline station\n"
                    "Purpose: CMCB Products\n"
                    "Bank: ABA (KHQR)\n"
                    "Amount: N/A\n"
                    "Interest: N/A\n"
                    "Loan Type: N/A\n"
                    "Tenure: N/A\n"
                    "Maturity: N/A\n"
                    "Status: OP\n"
                    "Potential H/M/L: M\n"
                    "Potential Product: KHQR\n"
                    "Remark: Meeting discussion"
                ),
            },
        }
        process_update(self.conn, form_update, self.pp_features)

        expired_count = sweep_expired_events(self.conn, window_seconds=900)
        self.assertEqual(expired_count, 1)

        dlq = get_dlq_items(self.conn)
        self.assertEqual(len(dlq), 1)
        self.assertEqual(dlq[0]["message_type"], "unmatched_report")
        self.assertEqual(dlq[0]["sender_name"], "Channa Thor")

    def test_duplicate_submission_rejected_within_30min(self):
        now = int(time.time())
        # 1. First Visit: Form arrives at t=0
        form1 = {
            "update_id": 10,
            "message": {
                "message_id": 1001,
                "date": now,
                "chat": {"id": -10012345},
                "from": {"id": 200, "first_name": "Chem", "last_name": "Sreynuch"},
                "caption": "Name: Sokkha\nTel: TG\nBusiness: coffee shops\nPurpose: CMCB Products\nBank: AC\nAmount: N/A\nInterest: N/A\nLoan Type: N/A\nTenure: N/A\nMaturity: N/A\nStatus: OP\nPotential H/M/L: L\nPotential Product: KHQR\nRemark: New visit and contact tg",
            },
        }
        process_update(self.conn, form1, self.pp_features)

        # Location arrives at t=60s -> Pairs into Visit 1
        loc1 = {
            "update_id": 11,
            "message": {
                "message_id": 1002,
                "date": now + 60,
                "chat": {"id": -10012345},
                "from": {"id": 200, "first_name": "Chem", "last_name": "Sreynuch"},
                "location": {"latitude": 11.594341, "longitude": 104.928537},
            },
        }
        res1 = process_update(self.conn, loc1, self.pp_features)
        self.assertIsNotNone(res1)
        self.assertEqual(len(get_all_reports(self.conn)), 1)

        # 2. Duplicate submission: Form arrives at t=66s (same RM, same store)
        form2 = {
            "update_id": 12,
            "message": {
                "message_id": 1003,
                "date": now + 66,
                "chat": {"id": -10012345},
                "from": {"id": 200, "first_name": "Chem", "last_name": "Sreynuch"},
                "caption": "Name: Sokkha\nTel: TG\nBusiness: coffee shops\nPurpose: CMCB Products\nBank: AC\nAmount: N/A\nInterest: N/A\nLoan Type: N/A\nTenure: N/A\nMaturity: N/A\nStatus: OP\nPotential H/M/L: L\nPotential Product: KHQR\nRemark: New visit and contact tg",
            },
        }
        res2 = process_update(self.conn, form2, self.pp_features)
        self.assertIsNone(res2)  # Must be rejected, not buffered

        # Location arrives at t=80s
        loc2 = {
            "update_id": 13,
            "message": {
                "message_id": 1004,
                "date": now + 80,
                "chat": {"id": -10012345},
                "from": {"id": 200, "first_name": "Chem", "last_name": "Sreynuch"},
                "location": {"latitude": 11.594341, "longitude": 104.928537},
            },
        }
        res3 = process_update(self.conn, loc2, self.pp_features)
        self.assertIsNone(res3)

        # Verify that reports table STILL only has 1 report!
        reports = get_all_reports(self.conn)
        self.assertEqual(len(reports), 1, "Duplicate report was not blocked!")

        # Verify that duplicate form was logged in Dead-Letter Queue
        dlq = get_dlq_items(self.conn)
        dup_dlqs = [d for d in dlq if "DUPLICATE_SUBMISSION" in d["reason"]]
        self.assertTrue(len(dup_dlqs) >= 1)

    def test_legitimate_revisit_after_30min_allowed(self):
        now = int(time.time())
        # Visit 1 at 9:00 AM
        form1 = {
            "update_id": 20,
            "message": {
                "message_id": 2001,
                "date": now,
                "chat": {"id": -10012345},
                "from": {"id": 300, "first_name": "RM", "last_name": "One"},
                "caption": "Name: Cafe Lotus\nTel: 012345678\nBusiness: Cafe\nPurpose: CMCB Products\nBank: ABA\nAmount: N/A\nInterest: N/A\nLoan Type: N/A\nTenure: N/A\nMaturity: N/A\nStatus: OP\nPotential H/M/L: M\nPotential Product: KHQR\nRemark: Morning visit",
            },
        }
        loc1 = {
            "update_id": 21,
            "message": {
                "message_id": 2002,
                "date": now + 10,
                "chat": {"id": -10012345},
                "from": {"id": 300, "first_name": "RM", "last_name": "One"},
                "location": {"latitude": 11.55, "longitude": 104.92},
            },
        }
        process_update(self.conn, form1, self.pp_features)
        process_update(self.conn, loc1, self.pp_features)

        # Legitimate Revisit at 2:00 PM (5 hours = 18000s later)
        form2 = {
            "update_id": 22,
            "message": {
                "message_id": 2003,
                "date": now + 18000,
                "chat": {"id": -10012345},
                "from": {"id": 300, "first_name": "RM", "last_name": "One"},
                "caption": "Name: Cafe Lotus\nTel: 012345678\nBusiness: Cafe\nPurpose: CMCB Products\nBank: ABA\nAmount: N/A\nInterest: N/A\nLoan Type: N/A\nTenure: N/A\nMaturity: N/A\nStatus: OP\nPotential H/M/L: M\nPotential Product: KHQR\nRemark: Afternoon follow up with contract",
            },
        }
        loc2 = {
            "update_id": 23,
            "message": {
                "message_id": 2004,
                "date": now + 18010,
                "chat": {"id": -10012345},
                "from": {"id": 300, "first_name": "RM", "last_name": "One"},
                "location": {"latitude": 11.55, "longitude": 104.92},
            },
        }
        process_update(self.conn, form2, self.pp_features)
        res2 = process_update(self.conn, loc2, self.pp_features)
        self.assertIsNotNone(res2)
        self.assertEqual(len(get_all_reports(self.conn)), 2, "Legitimate revisit was incorrectly blocked!")

    def test_different_merchant_within_30min_allowed(self):
        now = int(time.time())
        # Store 1 at 9:00 AM
        form1 = {
            "update_id": 30,
            "message": {
                "message_id": 3001,
                "date": now,
                "chat": {"id": -10012345},
                "from": {"id": 400, "first_name": "RM", "last_name": "Two"},
                "caption": "Name: Store Alpha\nTel: 011111111\nBusiness: Retail\nPurpose: CMCB Products\nBank: ABA\nAmount: N/A\nInterest: N/A\nLoan Type: N/A\nTenure: N/A\nMaturity: N/A\nStatus: OP\nPotential H/M/L: L\nPotential Product: KHQR\nRemark: Store Alpha visit",
            },
        }
        loc1 = {
            "update_id": 31,
            "message": {
                "message_id": 3002,
                "date": now + 5,
                "chat": {"id": -10012345},
                "from": {"id": 400, "first_name": "RM", "last_name": "Two"},
                "location": {"latitude": 11.55, "longitude": 104.92},
            },
        }
        process_update(self.conn, form1, self.pp_features)
        process_update(self.conn, loc1, self.pp_features)

        # Store 2 next door at 9:10 AM (10 min later)
        form2 = {
            "update_id": 32,
            "message": {
                "message_id": 3003,
                "date": now + 600,
                "chat": {"id": -10012345},
                "from": {"id": 400, "first_name": "RM", "last_name": "Two"},
                "caption": "Name: Store Beta\nTel: 022222222\nBusiness: Retail\nPurpose: CMCB Products\nBank: ABA\nAmount: N/A\nInterest: N/A\nLoan Type: N/A\nTenure: N/A\nMaturity: N/A\nStatus: OP\nPotential H/M/L: L\nPotential Product: KHQR\nRemark: Store Beta next door",
            },
        }
        loc2 = {
            "update_id": 33,
            "message": {
                "message_id": 3004,
                "date": now + 605,
                "chat": {"id": -10012345},
                "from": {"id": 400, "first_name": "RM", "last_name": "Two"},
                "location": {"latitude": 11.5501, "longitude": 104.9201},
            },
        }
        process_update(self.conn, form2, self.pp_features)
        res2 = process_update(self.conn, loc2, self.pp_features)
        self.assertIsNotNone(res2)
        self.assertEqual(len(get_all_reports(self.conn)), 2, "Different store next door was incorrectly blocked!")
if __name__ == "__main__":
    unittest.main()
