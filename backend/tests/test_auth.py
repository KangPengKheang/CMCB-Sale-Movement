import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from src.market_bot.app import create_app
from src.market_bot.config import Settings
from src.market_bot.core.auth import hash_password, verify_password
from src.market_bot.db.storage import init_db

class TestAdminAuth(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.settings = Settings(telegram_bot_token="", db_path=Path(folder.name)/"auth.db", auth_source="env")
        init_db(self.settings.db_path)
        from src.market_bot.core.sheets_sync import GoogleSheetsSync
        from tests.test_google_sheets import HEADERS, row
        source = Mock()
        source.fetch_values.return_value = [HEADERS, row()]
        self.assertEqual(GoogleSheetsSync(self.settings, [], source).refresh()["state"], "ready")
        settings_patch = patch.object(Settings, "load", return_value=self.settings)
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        self.client = TestClient(create_app())
        self.addCleanup(self.client.close)

    def test_admin_login_success(self):
        res = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "cmcbmarketinsightadmin"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("token", data)
        self.assertEqual(data["username"], "admin")

    def test_admin_login_invalid_password(self):
        res = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong_password_123"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid", res.json().get("detail", ""))

    def test_auth_me_with_valid_token(self):
        login_res = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "cmcbmarketinsightadmin"},
        )
        token = login_res.json()["token"]

        me_res = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["username"], "admin")
        self.assertTrue(me_res.json()["authenticated"])

    def test_protected_admin_endpoint_requires_auth(self):
        # Using a simulated external client IP
        res = self.client.get(
            "/api/reports/stats",
            headers={"Authorization": "Bearer invalid_token"},
        )
        self.assertEqual(res.status_code, 401)

    def test_protected_admin_endpoint_succeeds_with_bearer_token(self):
        login_res = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "cmcbmarketinsightadmin"},
        )
        token = login_res.json()["token"]

        res = self.client.get(
            "/api/reports/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 200)

    def test_sales_endpoints_remain_public(self):
        # Sales portal must remain accessible without admin login
        res = self.client.get("/api/sales/profile")
        self.assertEqual(res.status_code, 200)

    def test_pbkdf2_hash_and_verify(self):
        secret = "super_secure_bank_pwd_2026"
        hashed = hash_password(secret, iterations=50000)
        self.assertTrue(hashed.startswith("pbkdf2:sha256:50000:"))
        self.assertTrue(verify_password(secret, hashed))
        self.assertFalse(verify_password("wrong_password", hashed))
    def test_raw_password_fallback(self):
        self.assertTrue(verify_password("plain_text_pass", "plain_text_pass"))
        self.assertFalse(verify_password("wrong_pass", "plain_text_pass"))
if __name__ == "__main__":
    unittest.main()
