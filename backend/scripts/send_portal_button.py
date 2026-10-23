"""Script to send an interactive Sales Portal button directly into the Telegram group.
Automatically reads MINI_APP_BOT_TOKEN and MINI_APP_CHAT_ID from .env.
"""

import os
import sys
import json
import urllib.request
from pathlib import Path

# Load settings from market_bot config
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.market_bot.config import Settings

def main():
    settings = Settings.load()
    
    token = settings.mini_app_bot_token or settings.telegram_bot_token
    chat_id = settings.mini_app_chat_id or settings.target_chat_id
    
    if not token:
        print("ERROR: Neither MINI_APP_BOT_TOKEN nor TELEGRAM_BOT_TOKEN is set in environment!")
        sys.exit(1)
        
    if not chat_id:
        print("ERROR: Neither MINI_APP_CHAT_ID nor TARGET_CHAT_ID is set in environment!")
        sys.exit(1)

    # Allow custom portal URL via argument or prompt, default to current server
    app_url = os.getenv("PORTAL_URL", "https://your-domain.com/?portal=sales")
    if len(sys.argv) > 1:
        app_url = sys.argv[1]

    payload = {
        "chat_id": chat_id,
        "text": "📊 *CMCB Retail Field Operations*\n\nWelcome team! Tap below to open your daily route, view assigned merchant stores, and track territory coverage.",
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [[
                {
                    "text": "🚀 Open Field Sales Portal",
                    "web_app": {"url": app_url}
                }
            ]]
        }
    }

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                msg_id = data["result"]["message_id"]
                print(f" SUCCESS! Message sent to group {chat_id} (Message ID: {msg_id})")
                print("👉 Go to Telegram and tap 'Pin' on that message so it stays permanently at the top of the group!")
            else:
                print(" Telegram API returned error:", data)
    except Exception as e:
        print(f" Failed to send message: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
