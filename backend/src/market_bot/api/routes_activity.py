from fastapi import Request
from ..core.source_scope import get_request_connection
"""Admin endpoints for watching salesperson reporting activity."""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..core.activity_calendar import activity_calendar
from ..config import Settings
from ..core.activity import ICT, activity_feed, activity_overview, movement_routes, sender_activity, drop_detail
from ..db.storage import get_connection

router = APIRouter(prefix="/api/activity", tags=["Sales Activity"])


def get_db(request: Request):
    conn = get_request_connection(request, activity_only=True)
    try:
        yield conn
    finally:
        conn.close()


def get_detail_db(request: Request):
    # Opened popups need the scoped visit record; routine map/feed polling stays lightweight.
    conn = get_request_connection(request)
    try:
        yield conn
    finally:
        conn.close()


@router.get("/drops/{drop_id}")
def get_drop_detail(drop_id: int, conn=Depends(get_detail_db)):
    payload = drop_detail(conn, drop_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Drop not found in your permitted channels.")
    return payload


def resolve_day(conn, requested: Optional[str]) -> str:
    if requested:
        try:
            return date.fromisoformat(requested).isoformat()
        except ValueError:
            raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD")
    latest = conn.execute("SELECT MAX(local_date) FROM sales_submissions").fetchone()[0]
    return latest or datetime.now(ICT).date().isoformat()


@router.get("")
def get_activity(
    request: Request,
    day: Optional[str] = Query(None, alias="date"),
    threshold_minutes: Optional[float] = Query(None, gt=0, le=1440),
    conn=Depends(get_db),
):
    payload = activity_overview(conn, resolve_day(conn, day), threshold_minutes)
    sync = getattr(request.app.state, "sheets_sync", None)
    if sync is not None:
        payload["source_status"] = sync.public_status(bool(request.state.principal.get("all_sources")))
    else:
        previous = conn.execute(
            "SELECT value FROM sync_state WHERE key='google_sheets_last_success'"
        ).fetchone()
        payload["source_status"] = {
            "state": "cached", "last_success": previous[0] if previous else None, "error": None,
        }
    return payload



@router.get("/feed")
def get_activity_feed(
    day: Optional[str] = Query(None, alias="date"),
    sender_id: Optional[int] = Query(None, gt=0),
    threshold_minutes: Optional[float] = Query(None, gt=0, le=1440),
    late_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn=Depends(get_db),
):
    return activity_feed(conn, resolve_day(conn, day), threshold_minutes, sender_id, limit, offset, late_only)


@router.get("/routes")
def get_movement_routes(
    day: Optional[str] = Query(None, alias="date"),
    sender_id: Optional[int] = Query(None, gt=0),
    conn=Depends(get_db),
):
    return movement_routes(conn, resolve_day(conn, day), sender_id)


@router.get("/calendar")
def get_activity_calendar(conn=Depends(get_db)):
    return activity_calendar(conn)


@router.get("/{sender_id}/drops")
def get_sender_drops(
    sender_id: int,
    day: Optional[str] = Query(None, alias="date"),
    threshold_minutes: Optional[float] = Query(None, gt=0, le=1440),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn=Depends(get_db),
):
    if not conn.execute(
        "SELECT 1 FROM sales_submissions WHERE sender_id=? LIMIT 1", (sender_id,)
    ).fetchone():
        raise HTTPException(status_code=404, detail="Sender has no observed report submissions")
    return sender_activity(conn, sender_id, resolve_day(conn, day), threshold_minutes, limit, offset)
