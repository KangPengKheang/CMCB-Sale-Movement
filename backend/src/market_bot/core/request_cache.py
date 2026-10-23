"""Request-driven, disposable Sheets cache for Vercel Functions.

Only Google Sheets is authoritative. Each function process rebuilds its own
SQLite query cache; no timers or persistent function filesystem are required.
"""
import json
import threading
import time

from ..clients.google_sheets import GoogleSheetsError
from ..db.storage import init_db
from .sheets_sync import GoogleSheetsSync


class RequestSheetCache:
    def __init__(self, settings):
        self.settings = settings
        self.sync = None
        self._lock = threading.Lock()
        self._next_check = 0.0

    def ensure(self):
        # FastAPI can run concurrent requests in one function instance. Only one
        # request may initialize or refresh its snapshot at a time.
        with self._lock:
            if (self.sync is not None and self.sync.status.get("last_success")
                    and self.settings.db_path.exists() and time.monotonic() < self._next_check):
                return
            if self.sync is None or not self.settings.db_path.exists():
                init_db(self.settings.db_path)
                features = []
                if self.settings.khans_geojson_path.exists():
                    features = json.loads(self.settings.khans_geojson_path.read_text(encoding="utf-8")).get("features", [])
                self.sync = GoogleSheetsSync(self.settings, features)
            status = self.sync.refresh()
            self._next_check = time.monotonic() + self.settings.google_sheets_refresh_seconds
            if not status.get("last_success"):
                # A cold instance must never report an empty dashboard as valid
                # when the Sheet could not be loaded. Warm instances keep their
                # last complete snapshot on transient Sheet failures.
                raise GoogleSheetsError("Sheet data is temporarily unavailable. Please try again shortly.")
