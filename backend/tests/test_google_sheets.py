import csv
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.market_bot.clients.google_sheets import GoogleSheetsClient, GoogleSheetsError
from src.market_bot.config import Settings
from src.market_bot.core.sheets_sync import (
    GoogleSheetsSync, build_snapshot, parse_timestamp, publish_snapshot,
)
from src.market_bot.db.storage import get_connection, init_connection, init_db

HEADERS = [
    "Source_Channel", "Sender_ID", "Sender_Name", "Name", "Tel", "Business",
    "Purpose", "Bank", "Amount", "Interest", "Loan_Type", "Tenure", "Maturity",
    "Status", "Estimated_USD", "Potential_Level", "Potential_Product", "Remark",
    "Message_Date", "Latitude", "Longitude", "Raw_Text", "Has_Image", "Has_Location",
]


def row(**changes):
    data = {
        "Source_Channel": "test", "Sender_ID": "123", "Sender_Name": "Sample RM",
        "Name": "Sample Coffee", "Tel": "012345678", "Business": "Coffee Shop",
        "Bank": "ABA", "Status": "OP", "Remark": "Follow up",
        "Message_Date": "2026-10-13 09:30:00", "Latitude": "11.56",
        "Longitude": "104.92", "Has_Image": "TRUE", "Has_Location": "TRUE",
    }
    data.update(changes)
    return [data.get(h, "") for h in HEADERS]


def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_connection(conn)
    return conn


class SheetSnapshotTests(unittest.TestCase):
    def snapshot(self, rows):
        conn, counts = build_snapshot([HEADERS, *rows], [], "test-sheet")
        self.addCleanup(conn.close)
        return conn, counts

    def test_cambodia_dates_and_single_digit_hour(self):
        self.assertEqual(parse_timestamp("2026-10-13 9:30:00"), "2026-10-13T02:30:00Z")
        self.assertEqual(parse_timestamp("2026-10-13T09:30:00+07:00"), "2026-10-13T02:30:00Z")
        with self.assertRaises(ValueError):
            parse_timestamp("")

    def test_maps_real_headers_and_quarantines_missing_gps(self):
        conn, counts = self.snapshot([row(), row(Name="Missing GPS", Latitude="")])
        report = dict(conn.execute("SELECT * FROM merchant_reports").fetchone())
        self.assertEqual(counts["visits"], 1)
        self.assertEqual(counts["quarantined"], 1)
        self.assertEqual(report["report_time"], "2026-10-13T02:30:00Z")
        self.assertEqual(report["tel_clean"], "012345678")
        self.assertEqual(report["has_aba"], 1)
        self.assertEqual(report["photo_count"], 1)
        self.assertIsNone(report["form_msg_id"])

    def test_reordered_rows_keep_ids_and_exact_duplicates_are_removed(self):
        a = row()
        b = row(Message_Date="2026-10-14 09:30:00")
        first, counts = self.snapshot([a, b, a])
        second, _ = self.snapshot([b, a])
        self.assertEqual(counts["duplicates"], 1)
        for table in ("merchant_reports", "merchants", "rms"):
            ids1 = [r[0] for r in first.execute(f"SELECT id FROM {table} ORDER BY id")]
            ids2 = [r[0] for r in second.execute(f"SELECT id FROM {table} ORDER BY id")]
            self.assertEqual(ids1, ids2)
        merchant = first.execute("SELECT * FROM merchants").fetchone()
        self.assertEqual(merchant["total_visits"], 2)

    def test_corrected_duplicate_uses_later_sheet_row(self):
        conn, counts = self.snapshot([row(), row(Remark="signed form")])
        self.assertEqual(counts["visits"], 1)
        self.assertEqual(counts["duplicates"], 1)
        self.assertEqual(conn.execute("SELECT remark FROM merchant_reports").fetchone()[0], "signed form")

    def test_distinct_stores_at_same_coordinates_stay_separate(self):
        conn, counts = self.snapshot([row(), row(Name="Another Hardware Store")])
        self.assertEqual(counts["merchants"], 2)

    def test_snapshot_edit_and_delete_recompute_aggregates(self):
        target = memory_db()
        self.addCleanup(target.close)
        initial, _ = self.snapshot([row(), row(Message_Date="2026-10-14 09:30:00", Remark="signed form")])
        publish_snapshot(target, initial, "first", "test-sheet")
        report_id = target.execute(
            "SELECT id FROM merchant_reports WHERE report_time='2026-10-13T02:30:00Z'"
        ).fetchone()[0]
        updated, _ = self.snapshot([row(Remark="owner unavailable")])
        publish_snapshot(target, updated, "second", "test-sheet")
        self.assertEqual(target.execute("SELECT id FROM merchant_reports").fetchone()[0], report_id)
        merchant = target.execute("SELECT * FROM merchants").fetchone()
        self.assertEqual(merchant["total_visits"], 1)
        self.assertEqual(merchant["is_onboarded"], 0)
        self.assertEqual(target.execute("SELECT total_visits_logged FROM rms").fetchone()[0], 1)

    def test_publish_preserves_transaction_uploads(self):
        target = memory_db()
        self.addCleanup(target.close)
        target.execute(
            "INSERT INTO upload_logs(filename,file_size_bytes,snapshot_weeks,raw_rows,clean_rows,status) "
            "VALUES ('test.xlsx',1,'[]',1,1,'SUCCESS')"
        )
        target.commit()
        snapshot, _ = self.snapshot([row()])
        publish_snapshot(target, snapshot, "digest", "test-sheet")
        self.assertEqual(target.execute("SELECT COUNT(*) FROM upload_logs").fetchone()[0], 1)

    def test_publish_rolls_back_on_error(self):
        target = memory_db()
        self.addCleanup(target.close)
        original, _ = self.snapshot([row()])
        publish_snapshot(target, original, "old", "test-sheet")
        # Force a constraint error after the publication has deleted the old rows.
        broken, _ = self.snapshot([row(Name="New Merchant")])
        broken.execute("UPDATE merchant_reports SET merchant_name='Rejected'")
        broken.commit()
        target.execute(
            "CREATE TRIGGER reject_insert BEFORE INSERT ON merchant_reports "
            "WHEN NEW.merchant_name='Rejected' BEGIN SELECT RAISE(ABORT,'test'); END"
        )
        target.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            publish_snapshot(target, broken, "new", "test-sheet")
        self.assertEqual(target.execute("SELECT merchant_name FROM merchant_reports").fetchone()[0], "Sample Coffee")

    def test_existing_non_sheet_database_is_protected(self):
        target, _ = self.snapshot([row()])
        new, _ = self.snapshot([row(Name="Other")])
        with self.assertRaises(GoogleSheetsError):
            publish_snapshot(target, new, "digest", "test-sheet")
        self.assertEqual(target.execute("SELECT merchant_name FROM merchant_reports").fetchone()[0], "Sample Coffee")

    def test_empty_and_invalid_schema_cannot_replace_cache(self):
        for values in ([], [HEADERS], [["Name"], ["shop"]]):
            with self.subTest(values=values):
                with self.assertRaises(GoogleSheetsError):
                    build_snapshot(values, [], "test-sheet")

    def test_nonfinite_gps_is_quarantined(self):
        _, counts = self.snapshot([row(), row(Name="Invalid GPS", Latitude="nan")])
        self.assertEqual(counts["visits"], 1)
        self.assertEqual(counts["quarantined"], 1)


    def test_last_duplicate_row_can_restore_an_earlier_version(self):
        conn, counts = self.snapshot([row(Remark="original"), row(Remark="updated"), row(Remark="original")])
        self.assertEqual(counts["visits"], 1)
        self.assertEqual(counts["duplicates"], 2)
        self.assertEqual(conn.execute("SELECT remark FROM merchant_reports").fetchone()[0], "original")


class SheetRefreshTests(unittest.TestCase):
    def test_successful_unchanged_check_advances_heartbeat_not_data_timestamp(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings(telegram_bot_token="", db_path=Path(folder) / "cache.db")
            init_db(settings.db_path)
            source = Mock()
            source.fetch_values.return_value = [HEADERS, row()]
            sync = GoogleSheetsSync(settings, [], source)
            with patch("src.market_bot.core.sheets_sync.utc_now", return_value="2026-10-16T10:00:00Z"):
                sync.refresh()
            with patch("src.market_bot.core.sheets_sync.utc_now", return_value="2026-10-16T10:01:00Z"):
                checked = sync.refresh()
            self.assertFalse(checked["changed"])
            self.assertEqual(checked["last_success"], "2026-10-16T10:00:00Z")
            self.assertEqual(checked["last_checked"], "2026-10-16T10:01:00Z")
            restricted = sync.public_status(False)
            self.assertNotIn("drops", restricted)
            self.assertNotIn("quarantined", restricted)
            self.assertEqual(restricted["last_checked"], checked["last_checked"])
            source.fetch_values.side_effect = GoogleSheetsError("Unavailable")
            failed = sync.refresh()
            self.assertEqual(failed["state"], "error")
            self.assertEqual(failed["last_checked"], checked["last_checked"])

    def test_network_failure_and_unchanged_sheet_preserve_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings(telegram_bot_token="", db_path=Path(folder) / "cache.db")
            init_db(settings.db_path)
            client = Mock()
            client.fetch_values.return_value = [HEADERS, row()]
            sync = GoogleSheetsSync(settings, [], client=client)
            self.assertEqual(sync.refresh()["state"], "ready")
            self.assertFalse(sync.refresh()["changed"])
            client.fetch_values.side_effect = GoogleSheetsError("Unavailable")
            self.assertEqual(sync.refresh()["state"], "error")
            conn = get_connection(settings.db_path)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM merchant_reports").fetchone()[0], 1)
            finally:
                conn.close()


class SheetClientTests(unittest.TestCase):
    def test_public_csv_targets_configured_gid(self):
        output = io.StringIO()
        csv.writer(output).writerows([HEADERS, row()])
        response = Mock()
        response.read.return_value = output.getvalue().encode()
        response.headers = {"Content-Type": "text/csv"}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        settings = Settings(telegram_bot_token="")
        with patch("src.market_bot.clients.google_sheets.urlopen", return_value=response) as opener:
            values = GoogleSheetsClient(settings).fetch_values()
        self.assertEqual(values[0], HEADERS)
        self.assertIn("gid=1298094173", opener.call_args.args[0].full_url)

    def test_sign_in_html_is_rejected(self):
        response = Mock()
        response.read.return_value = b"<!doctype html><html>Sign in</html>"
        response.headers = {"Content-Type": "text/html"}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("src.market_bot.clients.google_sheets.urlopen", return_value=response):
            with self.assertRaises(GoogleSheetsError):
                GoogleSheetsClient(Settings(telegram_bot_token="")).fetch_values()


    def test_service_account_uses_readonly_scope_and_tab_name(self):
        settings = Settings(telegram_bot_token="", google_sheets_credentials_file=Path("not-read.json"))
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"values": [HEADERS, row()]}
        session = Mock()
        session.get.return_value = response
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        with patch("google.oauth2.service_account.Credentials.from_service_account_file") as credentials:
            with patch("google.auth.transport.requests.AuthorizedSession", return_value=session):
                result = GoogleSheetsClient(settings).fetch_values()
        self.assertEqual(result[0], HEADERS)
        self.assertEqual(
            credentials.call_args.kwargs["scopes"],
            ["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        self.assertIn("retail_data", session.get.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
