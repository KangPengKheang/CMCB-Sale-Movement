import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from src.market_bot.app import create_app
from src.market_bot.config import Settings
from src.market_bot.core.auth import create_admin_token
from src.market_bot.core.sheets_sync import GoogleSheetsSync
from src.market_bot.core.users_auth import UsersDirectory, UsersUnavailable, parse_allowed_sources
from src.market_bot.db.storage import get_connection, init_db
from tests.test_google_sheets import HEADERS, row

USER_HEADERS = ["username", "password", "allowed_sources", "role", "is_active", "branch", "Tele_ID"]


class UsersLoginTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.settings = Settings(telegram_bot_token="", db_path=Path(self.folder.name)/"cache.db",
                                 auth_source="users", auth_secret_key="isolated-test-session-secret")
        init_db(self.settings.db_path)
        source = Mock()
        source.fetch_values.return_value = [HEADERS,
            row(Source_Channel="Source A", Message_Date="2026-10-13 09:00:00", Remark="VISIBLE_A"),
            row(Source_Channel="Source B", Message_Date="2026-10-13 09:30:00", Remark="PRIVATE_B"),
            row(Source_Channel="Source A", Message_Date="2026-10-13 10:00:00", Remark="VISIBLE_A_LAST"),
            row(Source_Channel="Source B", Message_Date="2026-10-14 10:00:00", Remark="PRIVATE_B_LAST"),
            row(Source_Channel="Source B", Sender_ID="456", Sender_Name="PRIVATE_B_PERSON", Name="PRIVATE_B_STORE",
                Latitude="12.00", Longitude="105.00", Message_Date="2026-10-13 10:30:00"),
            row(Source_Channel="Source A", Sender_ID="789", Sender_Name="GPS missing A", Name="No GPS A",
                Latitude="", Longitude="", Message_Date="2026-10-13 11:00:00"),
        ]
        sync = GoogleSheetsSync(self.settings, [], source)
        self.assertEqual(sync.refresh()["state"], "ready")
        self.values = [USER_HEADERS,
            ["root", "root-test-password", "All", "admin", "TRUE", "HQ", "1"],
            ["viewer", "viewer-test-password", "Source A", "rm", "TRUE", "A", "2"],
            ["supervisor", "supervisor-test-password", "Source A, Source B", "sro", "TRUE", "AB", "3"],
            ["disabled", "disabled-test-password", "All", "admin", "FALSE", "HQ", "4"],
            ["empty", "empty-test-password", "", "rm", "TRUE", "", "5"],
            ["limited-admin", "limited-admin-password", "Source A", "admin", "TRUE", "A", "6"],
        ]
        self.user_source = Mock()
        self.user_source.fetch_values.side_effect = lambda *args: [list(record) for record in self.values]
        self.directory = UsersDirectory(self.settings, self.user_source)
        self.patch = patch.object(Settings, "load", return_value=self.settings)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.app = create_app()
        self.app.state.users_directory = self.directory
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def login(self, username="viewer", password="viewer-test-password"):
        result = self.client.post("/api/auth/login", json={"password": password})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["username"].casefold(), username.casefold())
        return result, {"Authorization": "Bearer " + result.json()["token"]}

    def test_users_login_role_scope_and_cookie_do_not_disclose_password(self):
        result, headers = self.login("viewer")
        self.assertEqual(result.json()["role"], "rm")
        self.assertEqual(result.json()["allowed_sources"], ["Source A"])
        self.assertFalse(result.json()["all_sources"])
        self.assertNotIn("viewer-test-password", result.text)
        cookie = result.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        current = self.client.get("/api/auth/me", headers=headers).json()
        self.assertEqual(current["username"], "viewer")
        self.assertNotIn("password_tag", current)
        self.assertEqual(self.client.get("/api/activity").status_code, 200)  # Authenticated cookie.

    def test_case_calendar_api_limits_counts_and_people_to_account_channels(self):
        _, headers = self.login()
        response = self.client.get("/api/activity/calendar", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual({person["sender_id"] for person in response.json()["senders"]}, {123, 789})
        self.assertNotIn("PRIVATE_B_PERSON", response.text)
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/activity/calendar").status_code, 401)

    def test_password_only_login_and_exact_password(self):
        self.login()
        self.assertEqual(self.client.post("/api/auth/login", json={"username":"viewer","password":" viewer-test-password "}).status_code, 401)

    def test_wrong_disabled_unknown_and_legacy_credentials_are_rejected(self):
        for username,password in [("viewer","wrong"),("disabled","disabled-test-password"),("unknown","x"),("admin","cmcbmarketinsightadmin")]:
            with self.subTest(username=username):
                result = self.client.post("/api/auth/login", json={"username":username,"password":password})
                self.assertEqual(result.status_code, 401)

    def test_anonymous_localhost_cannot_bypass_any_portal(self):
        local = TestClient(self.app, client=("127.0.0.1",54321))
        self.addCleanup(local.close)
        for url in ["/api/activity","/api/activity/feed","/api/activity/routes","/api/reports/stats",
                    "/api/merchants","/api/rms","/api/map/geojson","/api/sales/profile","/api/source/status"]:
            with self.subTest(url=url):
                self.assertEqual(local.get(url).status_code, 401)

    def test_activity_dates_feed_timeline_and_routes_only_use_allowed_rows(self):
        _,headers = self.login()
        data = self.client.get("/api/activity",headers=headers).json()
        self.assertEqual(data["date"],"2026-10-13")
        self.assertEqual(data["available_dates"],["2026-10-13"])
        self.assertEqual(data["summary"]["drop_count"],3)
        self.assertEqual([channel["name"] for channel in data["channels"]],["Source A"])
        self.assertEqual({person["sender_id"] for person in data["senders"]},{123,789})
        feed = self.client.get("/api/activity/feed",headers=headers).json()
        self.assertEqual({entry["source_channel"] for entry in feed["entries"]},{"Source A"})
        timeline = self.client.get("/api/activity/123/drops",headers=headers).json()
        self.assertEqual([entry["gap_seconds"] for entry in timeline["drops"]],[None,3600])
        self.assertEqual({person["sender_id"] for person in self.client.get("/api/activity/routes",headers=headers).json()["tracks"]},{123})
        self.assertEqual(self.client.get("/api/activity/456/drops",headers=headers).status_code,404)
        self.assertEqual(self.client.get("/api/activity/routes?sender_id=456",headers=headers).json()["tracks"],[])
        self.assertEqual(self.client.get("/api/activity?date=2026-10-14",headers=headers).json()["summary"]["drop_count"],0)

    def test_derived_merchant_rm_stats_and_other_views_do_not_leak_denied_rows(self):
        _,headers = self.login()
        stats = self.client.get("/api/reports/stats",headers=headers).json()
        self.assertEqual(stats["total_visits"],2)
        self.assertEqual(stats["total_merchants"],1)
        for url in ["/api/reports","/api/reports/dlq","/api/merchants","/api/rms",
                    "/api/map/geojson","/api/map/merchants-geojson","/api/map/khan-stats",
                    "/api/sales/profile","/api/sales/today","/api/sales/store-map",
                    "/api/sales/customers","/api/sales/visits?time_range=all"]:
            with self.subTest(url=url):
                response=self.client.get(url,headers=headers)
                self.assertEqual(response.status_code,200,response.text)
                self.assertNotIn("PRIVATE_B",response.text)
        merchants=self.client.get("/api/merchants",headers=headers).json()
        self.assertEqual(merchants[0]["total_visits"],2)
        detail=self.client.get("/api/merchants/"+str(merchants[0]["id"]),headers=headers)
        self.assertEqual(detail.status_code,200)
        self.assertNotIn("PRIVATE_B",detail.text)
        self.assertIn("VISIBLE_A_LAST",detail.text)

    def test_direct_denied_report_and_merchant_ids_are_not_readable(self):
        _,headers=self.login()
        conn=get_connection(self.settings.db_path)
        self.addCleanup(conn.close)
        denied=conn.execute("SELECT id,merchant_id,rm_id FROM merchant_reports WHERE sender_id=456").fetchone()
        for url in ["/api/reports/"+str(denied["id"]),"/api/merchants/"+str(denied["merchant_id"]),"/api/rms/"+str(denied["rm_id"])]:
            self.assertEqual(self.client.get(url,headers=headers).status_code,404)

    def test_restricted_export_transactions_and_admin_role_are_not_bypasses(self):
        for username,password in [("viewer","viewer-test-password"),("limited-admin","limited-admin-password")]:
            _,headers=self.login(username,password)
            for url in ["/api/reports/export/excel","/api/transactions/weeks"]:
                self.assertEqual(self.client.get(url,headers=headers).status_code,403)
            self.assertEqual(self.client.post("/api/transactions/upload",headers=headers,files={"file":("test.xlsx",b"not-a-workbook")}).status_code,403)

    def test_empty_sources_are_empty_access_not_all(self):
        _,headers=self.login("empty","empty-test-password")
        data=self.client.get("/api/activity",headers=headers).json()
        self.assertEqual(data["summary"]["drop_count"],0)
        self.assertEqual(data["senders"],[])
        self.assertEqual(data["channels"],[])
        self.assertEqual(self.client.get("/api/reports/stats",headers=headers).json()["total_visits"],0)

    def test_all_and_multi_source_readers_get_exact_authorized_data(self):
        _,headers=self.login("root","root-test-password")
        self.assertTrue(self.client.get("/api/auth/me",headers=headers).json()["all_sources"])
        self.assertEqual(self.client.get("/api/activity?date=2026-10-13",headers=headers).json()["summary"]["drop_count"],5)
        _,headers=self.login("supervisor","supervisor-test-password")
        self.assertEqual(self.client.get("/api/activity?date=2026-10-13",headers=headers).json()["summary"]["drop_count"],5)
        self.assertEqual(self.client.get("/api/auth/me",headers=headers).json()["role"],"sro")
        self.assertEqual(self.client.get("/api/reports/export/excel",headers=headers).status_code,403)

    def test_logout_revokes_bearer_token(self):
        _,headers=self.login()
        self.assertEqual(self.client.post("/api/auth/logout",headers=headers).status_code,200)
        self.assertEqual(self.client.get("/api/auth/me",headers=headers).status_code,401)

    def test_permission_password_and_active_changes_invalidate_existing_sessions(self):
        _,headers=self.login()
        self.values[2][2]="Source B"
        self.directory.refresh(force=True)
        self.assertEqual(self.client.get("/api/activity",headers=headers).status_code,401)
        _,headers=self.login()
        feed=self.client.get("/api/activity/feed?date=2026-10-13",headers=headers).json()
        self.assertEqual({entry["source_channel"] for entry in feed["entries"]},{"Source B"})
        self.values[2][1]="changed-password"
        self.directory.refresh(force=True)
        self.assertEqual(self.client.get("/api/auth/me",headers=headers).status_code,401)
        self.assertEqual(self.client.post("/api/auth/login",json={"username":"viewer","password":"viewer-test-password"}).status_code,401)
        _,headers=self.login("viewer","changed-password")
        self.values[2][4]="FALSE"
        self.directory.refresh(force=True)
        self.assertEqual(self.client.get("/api/activity",headers=headers).status_code,401)

    def test_user_sheet_failure_fails_closed(self):
        _,headers=self.login()
        self.user_source.fetch_values.side_effect=RuntimeError("should not be exposed")
        with self.assertRaises(UsersUnavailable):
            self.directory.refresh(force=True)
        for url in ["/api/activity","/api/reports/stats","/api/sales/profile"]:
            response=self.client.get(url,headers=headers)
            self.assertEqual(response.status_code,503)
            self.assertNotIn("should not be exposed",response.text)

    def test_claimed_role_and_sources_never_override_users_row(self):
        self.directory.refresh()
        user=next(user for user in self.directory._users.values() if user.username=="viewer")
        token=create_admin_token(user.key,self.settings.auth_secret_key,600,{
            "auth_source":"users","users_version":user.version,"role":"admin","allowed_sources":None})
        headers={"Authorization":"Bearer "+token}
        self.assertEqual(self.client.get("/api/auth/me",headers=headers).json()["role"],"rm")
        self.assertEqual(self.client.get("/api/activity",headers=headers).json()["summary"]["drop_count"],3)
        self.assertEqual(self.client.get("/api/reports/export/excel",headers=headers).status_code,403)

    def test_legacy_token_or_invalid_header_cannot_use_valid_cookie(self):
        _,headers=self.login()
        token=create_admin_token("admin",self.settings.auth_secret_key)
        self.assertEqual(self.client.get("/api/activity",headers={"Authorization":"Bearer "+token}).status_code,401)
        self.assertEqual(self.client.get("/api/activity",headers={"Authorization":"Bearer invalid"}).status_code,401)

    def test_source_parser_is_explicit_and_supports_lists(self):
        self.assertIsNone(parse_allowed_sources("All"))
        self.assertIsNone(parse_allowed_sources("*"))
        self.assertEqual(parse_allowed_sources("Source A, Source B\nSource C"),("Source A","Source B","Source C"))
        self.assertEqual(parse_allowed_sources('["Source A, special", "Source B"]'),("Source A, special","Source B"))
        self.assertEqual(parse_allowed_sources(""),())
        self.assertEqual(parse_allowed_sources("[invalid"),())

    def test_same_display_name_with_unique_passwords_keeps_distinct_permissions(self):
        self.values.append(["viewer","other-password","Source B","rm","TRUE","B","22"])
        self.directory.refresh(force=True)
        result,_ = self.login()
        self.assertEqual(result.json()["allowed_sources"], ["Source A"])
        result,_ = self.login("viewer","other-password")
        self.assertEqual(result.json()["allowed_sources"], ["Source B"])

    def test_all_source_reader_still_cannot_upload(self):
        self.values.append(["all-reader","reader-password","All","sro","TRUE","HQ","20"])
        _,headers=self.login("all-reader","reader-password")
        self.assertEqual(self.client.get("/api/transactions/weeks",headers=headers).status_code,200)
        self.assertEqual(self.client.post("/api/transactions/upload",headers=headers,files={"file":("test.xlsx",b"x")}).status_code,403)

    def test_source_names_are_values_not_sql(self):
        self.values[2][2]="Source A' OR 1=1 --"
        _,headers=self.login()
        self.assertEqual(self.client.get("/api/activity",headers=headers).json()["summary"]["drop_count"],0)

    def test_unicode_username_and_password(self):
        name=chr(0x1780)+chr(0x1781)+" Person"
        password=" "+chr(0x1782)+"-secret "
        self.values.append([name,password,"Source A","rm","TRUE","A","33"])
        response,headers=self.login(name.upper(),password)
        self.assertEqual(response.json()["username"],name)
        self.assertEqual(self.client.get("/api/activity",headers=headers).json()["summary"]["drop_count"],3)

    def test_failed_login_attempts_are_throttled(self):
        for _ in range(20):
            self.assertEqual(self.client.post("/api/auth/login",json={"username":"viewer","password":"wrong"}).status_code,401)
        response=self.client.post("/api/auth/login",json={"username":"viewer","password":"wrong"})
        self.assertEqual(response.status_code,429)
        self.assertEqual(response.headers["retry-after"],"300")

    def test_inactive_duplicate_username_cannot_impersonate_an_active_account(self):
        self.values.append(["viewer","viewer-test-password","All","admin","FALSE","HQ","55"])
        self.directory.refresh(force=True)
        self.assertEqual(self.client.post("/api/auth/login",json={"username":"viewer","password":"viewer-test-password"}).status_code,401)
        self.assertEqual(self.client.post("/api/auth/login",json={"password":"viewer-test-password"}).status_code,401)
        self.assertEqual(self.client.post("/api/auth/login",json={"username":"55","password":"viewer-test-password"}).status_code,401)

    def test_duplicate_identity_with_inactive_row_disables_ambiguous_identity(self):
        self.values.append(["viewer","viewer-test-password","All","admin","FALSE","HQ","2"])
        self.directory.refresh(force=True)
        self.assertEqual(self.client.post("/api/auth/login",json={"username":"2","password":"viewer-test-password"}).status_code,401)

    def test_shared_password_never_selects_between_admin_and_limited_account(self):
        self.values.append(["collision","viewer-test-password","All","admin","TRUE","HQ","999"])
        response = self.client.post("/api/auth/login", json={"password":"viewer-test-password"})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("set-cookie", response.headers)
        self.assertNotIn("token", response.json())

    def test_password_collision_invalidates_existing_session_after_refresh(self):
        _,headers = self.login()
        self.values.append(["collision","viewer-test-password","All","admin","TRUE","HQ","999"])
        self.directory.refresh(force=True)
        self.assertEqual(self.client.get("/api/auth/me",headers=headers).status_code,401)

    def test_username_claim_cannot_change_password_selected_permissions(self):
        response = self.client.post("/api/auth/login", json={"username":"root","password":"viewer-test-password"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["username"],"viewer")
        self.assertEqual(response.json()["allowed_sources"],["Source A"])

    def test_empty_missing_and_case_changed_password_are_rejected(self):
        for payload,status in [({},422),({"password":""},422),({"password":"VIEWER-TEST-PASSWORD"},401)]:
            self.assertEqual(self.client.post("/api/auth/login",json=payload).status_code,status)

    def test_unnamed_duplicate_password_cannot_grant_access(self):
        self.values.append(["","viewer-test-password","All","admin","TRUE","HQ","999"])
        self.assertEqual(self.client.post("/api/auth/login",json={"password":"viewer-test-password"}).status_code,401)

    def test_source_normalization_preserves_access_without_per_row_callbacks(self):
        conn = get_connection(self.settings.db_path)
        try:
            source = "".join(chr(ord(ch)+0xFEE0) if ch.isascii() and ch.isalpha() else ch for ch in "Source A")
            conn.execute("UPDATE sales_submissions SET source_channel=? WHERE source_channel='Source A'", ("  "+source+"  ",))
            conn.execute("UPDATE dead_letter_queue SET raw_content='not valid JSON'")
            conn.commit()
        finally:
            conn.close()
        _, headers = self.login()
        result = self.client.get("/api/activity",headers=headers)
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()["summary"]["drop_count"],3)
        self.assertEqual(result.json()["channels"][0]["name"],source)
        self.assertEqual(self.client.get("/api/reports/dlq",headers=headers).json(),[])

    def test_activity_status_does_not_disclose_global_source_counts(self):
        _,headers=self.login()
        self.app.state.sheets_sync = GoogleSheetsSync(self.settings, [], self.user_source)
        self.app.state.sheets_sync.status.update(state="ready",drops=9999,last_checked="2026-10-16T10:00:00Z")
        for path in ["/api/activity","/api/source/status"]:
            result=self.client.get(path,headers=headers).json()
            status=result["source_status"] if path=="/api/activity" else result
            self.assertNotIn("drops",status)
            self.assertEqual(status["last_checked"],"2026-10-16T10:00:00Z")

    def test_activity_snapshot_preserves_scope_and_hides_unused_global_dimensions(self):
        from src.market_bot.core.source_scope import restrict_connection
        conn = get_connection(self.settings.db_path)
        try:
            restrict_connection(conn, ["Source A"], activity_only=True)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sales_submissions").fetchone()[0],3)
            for table in ("merchant_reports","dead_letter_queue","merchants","rms"):
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM "+table).fetchone()[0],0)
            with self.assertRaises(Exception):
                conn.execute("DELETE FROM sales_submissions")
        finally:
            conn.close()

    def test_drop_detail_endpoint_is_authenticated_and_source_scoped(self):
        conn=get_connection(self.settings.db_path)
        try:
            allowed=conn.execute("SELECT id FROM sales_submissions WHERE source_channel='Source A' AND has_gps=1 LIMIT 1").fetchone()[0]
            denied=conn.execute("SELECT id FROM sales_submissions WHERE source_channel='Source B' LIMIT 1").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(self.client.get("/api/activity/drops/"+str(allowed)).status_code,401)
        _,headers=self.login()
        result=self.client.get("/api/activity/drops/"+str(allowed),headers=headers)
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()["tel"],"012345678")
        self.assertEqual(result.json()["bank"],"ABA")
        self.assertEqual(result.json()["source_channel"],"Source A")
        for field in ("merchant_name","business","amount","interest","loan_type","maturity","status"):
            self.assertIn(field,result.json())
        self.assertEqual(self.client.get("/api/activity/drops/"+str(denied),headers=headers).status_code,404)
        self.assertEqual(self.client.get("/api/activity/drops/-123",headers=headers).status_code,404)
        _,headers=self.login("root","root-test-password")
        self.assertEqual(self.client.get("/api/activity/drops/"+str(denied),headers=headers).status_code,200)
