import sqlite3
import unittest
from pathlib import Path
from src.market_bot.core.merchant_resolver import resolve_or_create_merchant
from src.market_bot.db.models import MerchantReportRecord
from src.market_bot.db.storage import (
    get_all_merchants,
    get_merchant_by_id,
    get_merchant_visits,
    init_db,
    link_visit_to_entities,
    upsert_merchant_report,
)


class TestMerchantResolver(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("data/test_merchants_temp.db")
        if self.db_path.exists():
            self.db_path.unlink()
        init_db(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_same_merchant_revisit_merging(self):
        # Visit 1: Initial Pitch by Samol
        v1 = MerchantReportRecord(
            report_time="2026-09-03T10:00:00Z",
            sender_id=101,
            sender_name="Samol Touch",
            merchant_name="Green Bakery",
            tel="012345678",
            tel_clean="012345678",
            business_clean="Coffee Shop / Cafe",
            status_clean="OP",
            khqr_stage="TARGET",
            bank="ABA (KHQR)",
            has_aba=1,
            has_cmcb=0,
            remark="New visit and get owner contact",
            latitude=11.5915,
            longitude=104.8750,
            district_khan="Sen Sok",
            form_msg_id=1001,
            location_msg_id=1002,
        )
        m_id1 = resolve_or_create_merchant(self.conn, v1)
        v1.merchant_id = m_id1
        row_id1 = upsert_merchant_report(self.conn, v1)
        link_visit_to_entities(self.conn, row_id1, merchant_id=m_id1)

        # Visit 2: Follow-up & Onboarded by Liza 5 days later
        v2 = MerchantReportRecord(
            report_time="2026-09-08T14:30:00Z",
            sender_id=102,
            sender_name="Liza Soy",
            merchant_name="Green Bakery Sensok",
            tel="012345678",
            tel_clean="012345678",
            business_clean="Coffee Shop / Cafe",
            status_clean="Existing",
            khqr_stage="CONVERTED",
            bank="CMCB (POS)",
            has_aba=0,
            has_cmcb=1,
            remark="Meeting signed form and deployed new KHQR",
            latitude=11.5916,
            longitude=104.8751,
            district_khan="Sen Sok",
            form_msg_id=1003,
            location_msg_id=1004,
        )
        m_id2 = resolve_or_create_merchant(self.conn, v2)
        v2.merchant_id = m_id2
        row_id2 = upsert_merchant_report(self.conn, v2)
        link_visit_to_entities(self.conn, row_id2, merchant_id=m_id2)
        # Assert both visits merged into the SAME merchant ID
        self.assertEqual(m_id1, m_id2)

        merchant = get_merchant_by_id(self.conn, m_id1)
        self.assertEqual(merchant["total_visits"], 2)
        self.assertEqual(merchant["is_onboarded"], 1)
        self.assertEqual(merchant["current_khqr_stage"], "CONVERTED")
        self.assertEqual(merchant["has_aba"], 1)
        self.assertEqual(merchant["has_cmcb"], 1)
        self.assertIn("Liza Soy", merchant["assigned_reps"])
        self.assertIn("Samol Touch", merchant["assigned_reps"])

        # Check visit history timeline
        timeline = get_merchant_visits(self.conn, m_id1)
        self.assertEqual(len(timeline), 2)
        self.assertEqual(timeline[0]["visit_no"], 1)
        self.assertEqual(timeline[0]["sales_rep"], "Samol Touch")
        self.assertEqual(timeline[1]["visit_no"], 2)
        self.assertEqual(timeline[1]["sales_rep"], "Liza Soy")

    def test_mall_different_store_separation(self):
        # Store A inside AEON Mall (GPS: 11.5910, 104.8750)
        v1 = MerchantReportRecord(
            report_time="2026-09-03T10:00:00Z",
            sender_id=101,
            sender_name="Samol Touch",
            merchant_name="G2000 Sensok",
            tel="TELEGRAM",
            tel_clean="TELEGRAM",
            latitude=11.5910,
            longitude=104.8750,
            district_khan="Sen Sok",
        )
        m_id1 = resolve_or_create_merchant(self.conn, v1)

        # Store B inside AEON Mall at EXACT SAME coordinates (GPS: 11.5910, 104.8750)
        v2 = MerchantReportRecord(
            report_time="2026-09-03T10:15:00Z",
            sender_id=101,
            sender_name="Samol Touch",
            merchant_name="Lacoste Sensok",
            tel="TELEGRAM",
            tel_clean="TELEGRAM",
            latitude=11.5910,
            longitude=104.8750,
            district_khan="Sen Sok",
        )
        m_id2 = resolve_or_create_merchant(self.conn, v2)

        # Store C inside AEON Mall at EXACT SAME coordinates
        v3 = MerchantReportRecord(
            report_time="2026-09-03T10:30:00Z",
            sender_id=101,
            sender_name="Samol Touch",
            merchant_name="Potato Corner Sensok",
            tel="TELEGRAM",
            tel_clean="TELEGRAM",
            latitude=11.5910,
            longitude=104.8750,
            district_khan="Sen Sok",
        )
        m_id3 = resolve_or_create_merchant(self.conn, v3)

        # MUST BE 3 DISTINCT MERCHANTS
        self.assertNotEqual(m_id1, m_id2)
        self.assertNotEqual(m_id2, m_id3)
        self.assertNotEqual(m_id1, m_id3)

        all_m = get_all_merchants(self.conn)
        self.assertEqual(len(all_m), 3)

    def test_multibranch_separation(self):
        # Branch 1: Express 41 on St 271
        v1 = MerchantReportRecord(
            report_time="2026-09-04T10:00:00Z",
            sender_id=101,
            sender_name="Samol Touch",
            merchant_name="Express 41 (271)",
            tel="098888999",
            tel_clean="098888999",
            latitude=11.5242,
            longitude=104.8769,
            district_khan="Pur SenChey",
        )
        m_id1 = resolve_or_create_merchant(self.conn, v1)

        # Branch 2: Express 41 in Toul Sangke (different location > 5km away)
        v2 = MerchantReportRecord(
            report_time="2026-09-05T11:00:00Z",
            sender_id=102,
            sender_name="Phann Channratana",
            merchant_name="Express 41 TSK",
            tel="098888999",  # Same corporate phone
            latitude=11.5949,
            longitude=104.9282,
            district_khan="Russey Keo",
        )
        m_id2 = resolve_or_create_merchant(self.conn, v2)

        # Distinct branches across different locations must remain distinct physical merchant records
        self.assertNotEqual(m_id1, m_id2)


if __name__ == "__main__":
    unittest.main()
