import json
import sqlite3
import unittest
from pathlib import Path
from src.market_bot.core.parser import SenderInfo
from src.market_bot.core.rm_resolver import resolve_or_create_rm
from src.market_bot.db.models import MerchantReportRecord
from src.market_bot.db.storage import (
    get_all_rms,
    get_rm_by_id,
    get_rm_habits,
    get_rm_visits,
    init_db,
    link_visit_to_entities,
    recalculate_rm_aggregates,
    upsert_merchant_report,
)


class TestRMResolver(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("data/test_rms_temp.db")
        if self.db_path.exists():
            self.db_path.unlink()
        init_db(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_rm_creation_and_visit_linking(self):
        sender = SenderInfo(sender_id=777, sender_name="Liza Soy", username="lizasoy")
        rm_id = resolve_or_create_rm(self.conn, sender, "2026-09-03T10:00:00Z")
        self.assertIsNotNone(rm_id)

        # Create visit linked to this RM
        visit = MerchantReportRecord(
            report_time="2026-09-03T10:00:00Z",
            sender_id=777,
            sender_name="Liza Soy",
            rm_id=rm_id,
            merchant_name="96 Coffee",
            business_clean="Coffee Shop / Cafe",
            district_khan="Sen Sok",
            status_clean="Existing",
            khqr_stage="CONVERTED",
            remark="Deployed new KHQR",
            latitude=11.5910,
            longitude=104.8750,
        )
        v_id = upsert_merchant_report(self.conn, visit)
        link_visit_to_entities(self.conn, v_id, rm_id=rm_id)
        recalculate_rm_aggregates(self.conn, rm_id)

        rm = get_rm_by_id(self.conn, rm_id)
        self.assertEqual(rm["canonical_name"], "Liza Soy")
        self.assertEqual(rm["total_visits_logged"], 1)
        self.assertEqual(rm["onboarded_count"], 1)
        self.assertEqual(rm["conversion_rate"], 100.0)

    def test_rm_habits_extraction(self):
        sender = SenderInfo(sender_id=888, sender_name="Samol Touch", username="samol")
        rm_id = resolve_or_create_rm(self.conn, sender, "2026-09-03T10:00:00Z")

        # Add 3 visits across different khans and categories
        visits = [
            ("2026-09-03T10:00:00Z", "Sen Sok", "Coffee Shop / Cafe", "TARGET"),
            ("2026-09-03T11:00:00Z", "Sen Sok", "Phone Shop", "PIPELINE"),
            ("2026-09-04T12:00:00Z", "Mean Chey", "Coffee Shop / Cafe", "CONVERTED"),
        ]
        for idx, (t, k, cat, stage) in enumerate(visits, start=1):
            v = MerchantReportRecord(
                report_time=t,
                sender_id=888,
                sender_name="Samol Touch",
                rm_id=rm_id,
                merchant_name=f"Store in {k} #{idx}",
                business_clean=cat,
                district_khan=k,
                status_clean="OP",
                khqr_stage=stage,
                latitude=11.5000,
                longitude=104.8000,
                form_msg_id=100 + idx,
            )
            v_id = upsert_merchant_report(self.conn, v)
            link_visit_to_entities(self.conn, v_id, rm_id=rm_id)

        recalculate_rm_aggregates(self.conn, rm_id)

        habits = get_rm_habits(self.conn, rm_id)
        self.assertIsNotNone(habits)
        self.assertEqual(habits["top_districts"].get("Sen Sok"), 2)
        self.assertEqual(habits["top_districts"].get("Mean Chey"), 1)
        self.assertEqual(habits["top_categories"].get("Coffee Shop / Cafe"), 2)
        self.assertEqual(habits["active_working_days"], 2)

    def test_rm_ranking_sort_options(self):
        # Create 2 RMs
        r1 = resolve_or_create_rm(self.conn, SenderInfo(sender_id=1, sender_name="Rep High Visits"), "2026-09-03T10:00:00Z")
        r2 = resolve_or_create_rm(self.conn, SenderInfo(sender_id=2, sender_name="Rep High Converter"), "2026-09-03T10:00:00Z")

        # Rep 1: 5 visits, 1 converted
        for i in range(5):
            stage = "CONVERTED" if i == 0 else "TARGET"
            v = MerchantReportRecord(
                report_time=f"2026-09-03T1{i}:00:00Z",
                sender_id=1,
                sender_name="Rep High Visits",
                rm_id=r1,
                merchant_name=f"Store {i}",
                khqr_stage=stage,
                latitude=11.5000,
                longitude=104.8000,
                form_msg_id=200 + i,
            )
            v_id = upsert_merchant_report(self.conn, v)
        recalculate_rm_aggregates(self.conn, r1)

        # Rep 2: 2 visits, 2 converted (100% conversion)
        for i in range(2):
            v = MerchantReportRecord(
                report_time=f"2026-09-03T1{i}:00:00Z",
                sender_id=2,
                sender_name="Rep High Converter",
                rm_id=r2,
                merchant_name=f"Store {i+10}",
                khqr_stage="CONVERTED",
                latitude=11.5000,
                longitude=104.8000,
                form_msg_id=300 + i,
            )
            v_id = upsert_merchant_report(self.conn, v)
        recalculate_rm_aggregates(self.conn, r2)

        # Sort by visits -> Rep 1 first
        by_visits = get_all_rms(self.conn, sort_by="visits")
        self.assertEqual(by_visits[0]["canonical_name"], "Rep High Visits")

        # Sort by onboarded -> Rep 2 first
        by_onboarded = get_all_rms(self.conn, sort_by="onboarded")
        self.assertEqual(by_onboarded[0]["canonical_name"], "Rep High Converter")

        # Sort by conversion_rate -> Rep 2 first (100% vs 20%)
        by_rate = get_all_rms(self.conn, sort_by="conversion_rate")
        self.assertEqual(by_rate[0]["canonical_name"], "Rep High Converter")
        self.assertEqual(by_rate[0]["conversion_rate"], 100.0)


if __name__ == "__main__":
    unittest.main()
