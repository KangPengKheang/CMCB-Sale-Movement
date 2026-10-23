import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from .api import routes_activity, routes_auth, routes_map, routes_merchants, routes_reports, routes_rms, routes_sales, routes_transactions
from .core.auth import require_admin, require_all_sources, require_operations_admin
from .core.users_auth import UsersDirectory
from .clients.telegram import AsyncTelegramClient
from .config import Settings
from .core.engine import process_update
from .core.sheets_sync import GoogleSheetsSync
from .db.storage import get_connection, init_db, sweep_expired_events

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("market_bot.app")

# Global background worker control
polling_task: Optional[asyncio.Task] = None
is_running = False


async def background_polling_loop(settings: Settings, pp_features: List[Dict[str, Any]]):
    """
    Continuous background long-polling worker managed by FastAPI lifespan.
    Safely ingests and correlates sales messages from Telegram.
    """
    global is_running
    logger.info("[*] Initializing Telegram Bot API Client...")
    tg = AsyncTelegramClient(bot_token=settings.telegram_bot_token)

    me_res = await tg.get_me()
    if not me_res.get("ok"):
        logger.warning(
            f"[!] Telegram authentication failed: {me_res.get('description')}. "
            f"Poller will idle. Please provide a valid TELEGRAM_BOT_TOKEN."
        )
        await tg.close()
        return

    bot_info = me_res.get("result", {})
    logger.info(f"[+] Bot active: @{bot_info.get('username')} (ID: {bot_info.get('id')})")
    logger.info(f"[+] Environment: {settings.environment.upper()} | DB: {settings.db_path.name}")
    logger.info("[+] Starting Telegram long-polling loop...")

    offset: Optional[int] = None
    last_sweep = asyncio.get_event_loop().time()
    conn = get_connection(settings.db_path)

    try:
        while is_running:
            try:
                updates_res = await tg.get_updates(offset=offset, timeout=settings.polling_timeout_seconds)
                if not updates_res.get("ok"):
                    logger.warning(f"Telegram getUpdates error: {updates_res.get('description')}")
                    await asyncio.sleep(2)
                    continue

                updates = updates_res.get("result", [])
                for update in updates:
                    update_id = update.get("update_id", 0)
                    try:
                        # 1. Audit archive
                        settings.archive_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(settings.archive_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps(update, ensure_ascii=False) + "\n")

                        # 2. Filter check
                        msg = update.get("message") or update.get("edited_message")
                        if msg:
                            chat_id = msg.get("chat", {}).get("id")
                            topic_id = msg.get("message_thread_id")

                            if settings.target_chat_id is not None and chat_id != settings.target_chat_id:
                                continue
                            if settings.target_topic_id is not None and topic_id != settings.target_topic_id:
                                continue

                        # 3. Process update through correlation engine
                        report = process_update(
                            conn=conn,
                            update=update,
                            pp_features=pp_features,
                            correlation_window_seconds=settings.correlation_window_seconds,
                        )

                        if report:
                            logger.info(f"[✓] Visit Recorded: {report.merchant_name} (Khan {report.district_khan}) by {report.sender_name}")

                    except Exception as err:
                        logger.error(f"Error processing update #{update_id}: {err}", exc_info=True)
                    finally:
                        offset = update_id + 1

                # Periodic sweep for expired events every 60s
                current_time = asyncio.get_event_loop().time()
                if current_time - last_sweep > 60:
                    expired = sweep_expired_events(conn, settings.correlation_window_seconds)
                    if expired > 0:
                        logger.info(f"[*] Sweep: quarantined {expired} expired unpaired events to DLQ.")
                    last_sweep = current_time

            except asyncio.CancelledError:
                logger.info("Polling worker received cancellation.")
                break
            except Exception as e:
                logger.error(f"Unexpected error in polling loop: {e}", exc_info=True)
                await asyncio.sleep(2)
    finally:
        conn.close()
        await tg.close()
        logger.info("Telegram background polling worker stopped cleanly.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager: startup and shutdown."""
    global is_running, polling_task
    settings = Settings.load()
    logger.info(f"Starting Market Improvement Bot Backend ({settings.environment.upper()} mode)")

    # 1. Initialize SQLite storage
    init_db(settings.db_path)

    # 2. Load Phnom Penh boundaries
    pp_features = []
    if settings.khans_geojson_path.exists():
        try:
            with open(settings.khans_geojson_path, "r", encoding="utf-8") as f:
                pp_geojson = json.load(f)
                pp_features = pp_geojson.get("features", [])
                logger.info(f"Loaded {len(pp_features)} district boundaries from {settings.khans_geojson_path}")
        except Exception as e:
            logger.warning(f"Could not load boundary geojson from {settings.khans_geojson_path}: {e}")
    else:
        logger.warning(f"District boundaries file not found at: {settings.khans_geojson_path}")

    # 3. Run exactly one visit source; keep Mini App authentication independent.
    sheets_task = None
    if settings.visit_data_source == "google_sheets":
        sync = GoogleSheetsSync(settings, pp_features)
        app.state.sheets_sync = sync
        sheets_task = asyncio.create_task(sync.run())
        logger.info("Google Sheets visit source: %s (refresh interval %ss)",
                    settings.google_sheets_tab, settings.google_sheets_refresh_seconds)
    elif settings.telegram_bot_token:
        is_running = True
        polling_task = asyncio.create_task(background_polling_loop(settings, pp_features))
    else:
        logger.info("[*] TELEGRAM_BOT_TOKEN not provided. Bot poller is disabled. Serving REST APIs only.")

    yield

    # Teardown
    is_running = False
    if sheets_task and not sheets_task.done():
        sheets_task.cancel()
        try:
            await sheets_task
        except asyncio.CancelledError:
            pass
    if polling_task and not polling_task.done():
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    logger.info("Market Improvement Bot Backend stopped cleanly.")


def create_app() -> FastAPI:
    """FastAPI Application Factory."""
    settings = Settings.load()
    app = FastAPI(
        title="CMCB Market Improvement Bot API",
        description="Backend service for Google Sheets visit synchronization, optional Telegram ingestion, and KHQR map analytics.",
        version="1.0.0",
        lifespan=lifespan,
    )

    if settings.auth_source == "users":
        app.state.users_directory = UsersDirectory(settings)

    # Enable CORS for React Frontend (khqr-map)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes_auth.router)
    app.include_router(routes_activity.router, dependencies=[Depends(require_admin)])
    app.include_router(routes_reports.router, dependencies=[Depends(require_admin)])
    app.include_router(routes_merchants.router, dependencies=[Depends(require_admin)])
    app.include_router(routes_rms.router, dependencies=[Depends(require_admin)])
    app.include_router(routes_map.router, dependencies=[Depends(require_admin)])
    app.include_router(routes_transactions.router, dependencies=[Depends(require_all_sources)])
    app.include_router(routes_sales.router, dependencies=[Depends(require_admin)] if settings.auth_source == "users" else [])
    @app.get("/api/health", tags=["Health"])
    def health_check():
        return {
            "status": "online",
            "service": "CMCB Market Improvement Bot",
            "environment": settings.environment,
            "visit_data_source": settings.visit_data_source,
            "database": settings.db_path.name,
            "correlation_window_seconds": settings.correlation_window_seconds,
        }

    @app.get("/api/source/status", tags=["Data Source"], dependencies=[Depends(require_admin)])
    def data_source_status(request: Request):
        sync = getattr(app.state, "sheets_sync", None)
        if sync is not None:
            return sync.public_status(bool(request.state.principal.get("all_sources")))
        return {"source": settings.visit_data_source, "state": "not_running"}

    # Serve the React frontend (frontend/dist) as static files when present (MUST be mounted last)
    if settings.frontend_dist_path.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount(
            "/",
            StaticFiles(directory=str(settings.frontend_dist_path), html=True),
            name="frontend",
        )

    return app

app = create_app()
