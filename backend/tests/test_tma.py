import hashlib
import hmac
import json
import time
import unittest
import urllib.parse
from src.market_bot.core.tma import (
    verify_telegram_init_data,
)


def _generate_test_init_data(user_dict: dict, bot_token: str, auth_date: int = None) -> str:
    """Helper to generate a cryptographically valid Telegram initData query string."""
    if auth_date is None:
        auth_date = int(time.time())

    params = {
        "query_id": "AAHdF6IQAAAAAN0XohD12345",
        "user": json.dumps(user_dict, separators=(",", ":")),
        "auth_date": str(auth_date),
    }

    # Construct data_check_string
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items(), key=lambda x: x[0])
    )

    # secret_key = HMAC_SHA256("WebAppData", bot_token)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()

    # hash = HMAC_SHA256(secret_key, data_check_string)
    computed_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    params["hash"] = computed_hash
    return urllib.parse.urlencode(params)


class TestTelegramMiniAppAuth(unittest.TestCase):
    def setUp(self):
        self.bot_token = "1234567890:ABCdefGhIJKlmNoPQRstuVWXyz"
        self.test_user = {
            "id": 8859478803,
            "first_name": "Liza",
            "last_name": "Soy",
            "username": "lizasoy",
        }

    def test_valid_init_data_passes(self):
        init_data = _generate_test_init_data(self.test_user, self.bot_token)
        result = verify_telegram_init_data(init_data, self.bot_token)

        self.assertIsNotNone(result)
        self.assertEqual(result["user"]["id"], 8859478803)
        self.assertEqual(result["user"]["first_name"], "Liza")
        self.assertEqual(result["user"]["username"], "lizasoy")

    def test_tampered_init_data_fails(self):
        init_data = _generate_test_init_data(self.test_user, self.bot_token)

        # Attacker tries to change user id to impersonate another RM
        tampered = init_data.replace("8859478803", "9999999999")
        result = verify_telegram_init_data(tampered, self.bot_token)
        self.assertIsNone(result, "tampered initData must be rejected")

    def test_wrong_bot_token_fails(self):
        init_data = _generate_test_init_data(self.test_user, self.bot_token)
        wrong_token = "9876543210:ZYXvutsRqPOnMLkJIhGfeDcBA"
        result = verify_telegram_init_data(init_data, wrong_token)
        self.assertIsNone(result, "signature signed by different bot token must fail")

    def test_expired_auth_date_fails(self):
        # auth_date 2 days ago (older than 24h)
        old_time = int(time.time()) - (86400 * 2)
        old_init_data = _generate_test_init_data(self.test_user, self.bot_token, auth_date=old_time)

        result = verify_telegram_init_data(old_init_data, self.bot_token, max_age_seconds=86400)
        self.assertIsNone(result, "replayed/expired initData must be rejected")


if __name__ == "__main__":
    unittest.main()
