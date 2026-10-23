import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv(interpolate=False)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# OWASP PBKDF2-HMAC-SHA256 hash (600,000 iterations + 16-byte random salt) for default admin
DEFAULT_ADMIN_PASSWORD_HASH = (
    "pbkdf2:sha256:600000:7b569186f5758a61d2e105dbefc7e915:f8bbf2434b5aa3db164cf9c0c7bb464a3763a5d397cd6bd91708ad931beae856"
)

@dataclass
class Settings:
    telegram_bot_token: str
    target_chat_id: Optional[int] = None
    target_topic_id: Optional[int] = None
    environment: str = "test"  # "test" or "production"
    db_path: Path = BASE_DIR / "data" / "market_reports_sheets_test.db"
    archive_path: Path = BASE_DIR / "data" / "captured_updates.jsonl"
    correlation_window_seconds: int = 900  # 15 minutes
    polling_timeout_seconds: int = 15
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    khans_geojson_path: Path = BASE_DIR / "boundaries" / "phnom_penh_khans.json"
    frontend_dist_path: Path = BASE_DIR / "frontend" / "dist"
    admin_username: str = "admin"
    admin_password_hash: str = DEFAULT_ADMIN_PASSWORD_HASH
    auth_secret_key: str = "cmcb-market-insight-admin-auth-secret-2026"
    auth_source: str = "env"  # Explicit compatibility mode for non-sheet installations/tests.
    users_sheet_tab: str = "Users"
    users_refresh_seconds: int = 60
    session_seconds: int = 28800
    mini_app_bot_token: Optional[str] = None
    mini_app_chat_id: Optional[int] = None
    visit_data_source: str = "google_sheets"
    google_sheets_id: str = "1wM7DTHizhg_A3h0qV3EhX4os4hk46uolW-ESQSJkgZs"
    google_sheets_tab: str = "retail_data"
    google_sheets_gid: str = "1298094173"
    google_sheets_refresh_seconds: int = 15
    google_sheets_credentials_file: Optional[Path] = None
    @classmethod
    def load(cls) -> "Settings":
        bot_token = (os.getenv("TELEGRAM_BOT_API") or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or "").strip()
        env_mode = os.getenv("ENVIRONMENT", "test").strip().lower()

        source = os.getenv("VISIT_DATA_SOURCE", "google_sheets").strip().lower()
        if source not in ("google_sheets", "telegram"):
            raise ValueError("VISIT_DATA_SOURCE must be google_sheets or telegram")
        refresh_seconds = int(os.getenv("GOOGLE_SHEETS_REFRESH_SECONDS") or "15")
        if refresh_seconds < 15:
            raise ValueError("GOOGLE_SHEETS_REFRESH_SECONDS must be at least 15")
        credentials_file = (
            os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or ""
        ).strip()

        # Keep Google Sheets caches separate from the original Telegram databases.
        custom_db_path = os.getenv("DATABASE_PATH")
        if custom_db_path:
            db_path = Path(custom_db_path)
        elif source == "google_sheets":
            cache_name = "market_reports_sheets.db" if env_mode == "production" else "market_reports_sheets_test.db"
            db_path = BASE_DIR / "data" / cache_name
        elif env_mode == "production":
            db_path = BASE_DIR / "data" / "market_reports.db"
        else:
            db_path = BASE_DIR / "data" / "market_reports_test.db"

        chat_id_raw = os.getenv("TARGET_CHAT_ID") or os.getenv("TEST_TARGET_CHAT_ID")
        chat_id = None
        if chat_id_raw and chat_id_raw.strip().lower() not in ["0", "all", "none", "*"]:
            try:
                chat_id = int(chat_id_raw.strip())
            except ValueError:
                pass

        topic_id_raw = os.getenv("TARGET_TOPIC_ID")
        topic_id = None
        if topic_id_raw:
            try:
                topic_id = int(topic_id_raw.strip())
            except ValueError:
                pass

        window_raw = os.getenv("CORRELATION_WINDOW_SECONDS")
        window = int(window_raw) if window_raw and window_raw.isdigit() else 900

        port_raw = os.getenv("PORT", os.getenv("SERVER_PORT", "8000"))
        port = int(port_raw) if port_raw.isdigit() else 8000

        # Resolve frontend dist path (supports both Docker container /app/frontend/dist and local repo)
        local_dist = BASE_DIR.parent / "frontend" / "dist"
        docker_dist = BASE_DIR / "frontend" / "dist"
        frontend_dist = local_dist if local_dist.exists() else (docker_dist if docker_dist.exists() else local_dist)

        # Resolve GeoJSON boundaries path (checks un-shadowed /app/boundaries first)
        candidate_paths = [
            BASE_DIR / "boundaries" / "phnom_penh_khans.json",
            BASE_DIR.parent / "frontend" / "src" / "data" / "boundaries" / "phnom_penh_khans.json",
            BASE_DIR / "data" / "boundaries" / "phnom_penh_khans.json",
        ]
        geojson_path = next((p for p in candidate_paths if p.exists()), candidate_paths[0])

        return cls(
            telegram_bot_token=bot_token,
            visit_data_source=source,
            google_sheets_id=(os.getenv("GOOGLE_SHEETS_ID") or "1wM7DTHizhg_A3h0qV3EhX4os4hk46uolW-ESQSJkgZs").strip(),
            google_sheets_tab=(os.getenv("GOOGLE_SHEETS_TAB") or "retail_data").strip(),
            google_sheets_gid=(os.getenv("GOOGLE_SHEETS_GID") or "1298094173").strip(),
            google_sheets_refresh_seconds=refresh_seconds,
            google_sheets_credentials_file=Path(credentials_file).expanduser() if credentials_file else None,
            target_chat_id=chat_id,
            target_topic_id=topic_id,
            environment=env_mode,
            db_path=db_path,
            correlation_window_seconds=window,
            server_host=os.getenv("HOST", os.getenv("SERVER_HOST", "127.0.0.1")),
            server_port=port,
            frontend_dist_path=frontend_dist,
            khans_geojson_path=geojson_path,
            auth_source=(os.getenv("AUTH_SOURCE") or ("users" if source == "google_sheets" else "env")).strip().lower(),
            users_sheet_tab=(os.getenv("USERS_SHEET_TAB") or "Users").strip(),
            users_refresh_seconds=max(15, int(os.getenv("USERS_REFRESH_SECONDS") or "60")),
            session_seconds=max(300, min(86400, int(os.getenv("SESSION_SECONDS") or "28800"))),
            admin_username=(os.getenv("ADMIN_USERNAME") or "admin").strip(),
            admin_password_hash=(os.getenv("ADMIN_PASSWORD_HASH") or os.getenv("ADMIN_PASSWORD") or DEFAULT_ADMIN_PASSWORD_HASH).strip(),
            auth_secret_key=(os.getenv("AUTH_SECRET_KEY") or "cmcb-market-insight-admin-auth-secret-2026").strip(),
            mini_app_bot_token=(os.getenv("MINI_APP_BOT_TOKEN") or "").strip() or None,
            mini_app_chat_id=int(os.getenv("MINI_APP_CHAT_ID").strip()) if os.getenv("MINI_APP_CHAT_ID") and os.getenv("MINI_APP_CHAT_ID").strip().lstrip("-").isdigit() else None,
        )
