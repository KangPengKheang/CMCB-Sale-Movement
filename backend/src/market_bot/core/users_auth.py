"""Read-only Users worksheet authentication. No sheet passwords are persisted or returned."""
import hashlib
import hmac
import json
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Optional

from ..clients.google_sheets import GoogleSheetsClient
from ..config import Settings


class UsersUnavailable(RuntimeError):
    pass


def normalize_identity(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value)).strip().casefold()


def parse_allowed_sources(value: str):
    raw = str(value).strip()
    if not raw:
        return ()
    try:
        values = json.loads(raw) if raw.startswith("[") else re.split(r"[,;|\n]+", raw)
    except (ValueError, TypeError):
        return ()
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        return ()
    names = sorted({item.strip() for item in values if item.strip()})
    if any(normalize_identity(item) in ("all", "*") for item in names):
        return None
    return tuple(names)


@dataclass(frozen=True)
class SheetUser:
    key: str
    username: str
    role: str
    allowed_sources: Optional[tuple]
    branch: str
    tele_id: str
    password_tag: str
    version: str

    def principal(self):
        return {
            "sub": self.key, "username": self.username, "role": self.role,
            "allowed_sources": list(self.allowed_sources) if self.allowed_sources is not None else None,
            "all_sources": self.allowed_sources is None, "branch": self.branch,
            "tele_id": self.tele_id, "auth_source": "users",
        }


class UsersDirectory:
    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        self.client = client or GoogleSheetsClient(settings)
        self._lock = threading.RLock()
        self._expires = 0.0
        self._ready = False
        self._users = {}
        self._passwords = {}
        self._revoked = {}
        self._attempts = {}

    def _tag(self, purpose: str, value: str) -> str:
        return hmac.new(self.settings.auth_secret_key.encode(), (purpose + "\0" + value).encode(), hashlib.sha256).hexdigest()

    def refresh(self, force=False):
        with self._lock:
            now = time.monotonic()
            if not force and now < self._expires:
                if not self._ready:
                    raise UsersUnavailable("User access cannot be verified right now. Please try again shortly.")
                return
            try:
                values = self.client.fetch_values(self.settings.users_sheet_tab)
                if not values:
                    raise ValueError("missing header")
                headers = [str(value).strip().lower().replace(" ", "_") for value in values[0]]
                named = [name for name in headers if name]
                required = {"username", "password", "allowed_sources", "role", "is_active"}
                if not required.issubset(headers) or len(named) != len(set(named)):
                    raise ValueError("invalid Users schema")
                users, password_counts, seen = {}, {}, set()
                for cells in values[1:]:
                    row = {name: str(cells[index]) if index < len(cells) and cells[index] is not None else "" for index, name in enumerate(headers) if name}
                    username = row["username"].strip()
                    password = row["password"]
                    role = normalize_identity(row["role"])
                    active = normalize_identity(row["is_active"]) in ("true", "1", "yes")
                    if password:
                        password_tag = self._tag("users-password", password)
                        password_counts[password_tag] = password_counts.get(password_tag, 0) + 1
                    if not username:
                        continue
                    tele_id = row.get("tele_id", "").strip()
                    key = normalize_identity(username) + "|" + tele_id
                    if key in seen:
                        users[key] = None
                        continue
                    seen.add(key)
                    if not password or not active or role not in ("admin", "sro", "rm"):
                        users[key] = None
                        continue
                    sources = parse_allowed_sources(row["allowed_sources"])
                    tag = self._tag("users-password", password)
                    version = self._tag("users-account", json.dumps([key, tag, role, sources, row.get("branch", "").strip()], ensure_ascii=False))
                    user = SheetUser(key, username, role, sources, row.get("branch", "").strip(), tele_id, tag, version)
                    users[key] = user
                # Password alone identifies the account. Never choose between shared credentials,
                # including collisions with inactive, invalid or unnamed rows.
                self._users = {key: user for key, user in users.items()
                               if user is not None and password_counts[user.password_tag] == 1}
                self._passwords = {user.password_tag: user.key for user in self._users.values()}
                self._ready = True
                self._expires = time.monotonic() + self.settings.users_refresh_seconds
            except Exception:
                self._ready = False
                self._expires = time.monotonic() + min(10, self.settings.users_refresh_seconds)
                raise UsersUnavailable("User access cannot be verified right now. Check the Users worksheet access and required columns.") from None

    def authenticate(self, password: str, client_host: str):
        self.refresh()
        with self._lock:
            now = time.monotonic()
            # Bounded, per-client throttling; usernames/passwords are never stored in attempt logs.
            self._attempts = {key: value for key, value in self._attempts.items() if value[1] > now}
            count, until = self._attempts.get(client_host, (0, now + 300))
            if count >= 20:
                return None, True
            self._attempts[client_host] = (count + 1, until)
            tag = self._tag("users-password", password)
            user = self._users.get(self._passwords.get(tag))
            matched = hmac.compare_digest(user.password_tag if user else "0" * 64, tag)
            if not user or not matched:
                return None, False
            self._attempts.pop(client_host, None)
            return user, False

    def validate(self, payload: dict):
        self.refresh()
        with self._lock:
            now = time.time()
            self._revoked = {key: expiry for key, expiry in self._revoked.items() if expiry > now}
            if payload.get("nonce") in self._revoked:
                return None
            user = self._users.get(payload.get("sub"))
            version = payload.get("users_version")
            return user if user and isinstance(version, str) and hmac.compare_digest(user.version, version) else None

    def revoke(self, payload: dict):
        with self._lock:
            if payload.get("nonce"):
                self._revoked[payload["nonce"]] = payload.get("exp", time.time())
