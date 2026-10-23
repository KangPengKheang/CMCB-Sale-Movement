from fastapi import Request
from ..core.source_scope import get_request_connection
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from ..config import Settings
from ..db.models import RMDetailResponse, RMHabitsResponse, RMResponse, VisitTimelineItem
from ..db.storage import (
    get_all_rms,
    get_connection,
    get_rm_by_id,
    get_rm_habits,
    get_rm_visits,
)

router = APIRouter(prefix="/api/rms", tags=["Relationship Managers"])


def get_db(request: Request):
    conn = get_request_connection(request)
    try:
        yield conn
    finally:
        conn.close()


@router.get("", response_model=List[RMResponse])
def list_rms(
    sort_by: str = Query("visits", description="Ranking metric: visits, onboarded, conversion_rate, velocity, merchants"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn=Depends(get_db),
):
    """
    List Relationship Managers ranked by performance metrics (visits, conversions, velocity).
    """
    return get_all_rms(conn=conn, sort_by=sort_by, limit=limit, offset=offset)


@router.get("/{rm_id}", response_model=RMDetailResponse)
def get_rm_detail(rm_id: int, conn=Depends(get_db)):
    """
    Retrieve comprehensive RM profile with lifetime performance KPIs, top districts, and category specializations.
    """
    rm = get_rm_by_id(conn, rm_id)
    if not rm:
        raise HTTPException(status_code=404, detail="Relationship Manager not found")

    top_d = json.loads(rm["top_districts"]) if rm["top_districts"] else {}
    top_c = json.loads(rm["top_categories"]) if rm["top_categories"] else {}
    visits = get_rm_visits(conn, rm_id, limit=20)

    rm_dict = dict(rm)
    rm_dict["top_districts"] = top_d
    rm_dict["top_categories"] = top_c
    rm_dict["recent_visits"] = visits
    return rm_dict


@router.get("/{rm_id}/habits", response_model=RMHabitsResponse)
def get_rm_visiting_habits(rm_id: int, conn=Depends(get_db)):
    """
    Retrieve deep-dive visiting habits for an RM (territory focus, sector specializations, velocity).
    """
    habits = get_rm_habits(conn, rm_id)
    if not habits:
        raise HTTPException(status_code=404, detail="Relationship Manager not found")
    return habits


@router.get("/{rm_id}/visits", response_model=List[VisitTimelineItem])
def get_rm_visit_feed(
    rm_id: int,
    limit: int = Query(100, ge=1, le=500),
    conn=Depends(get_db),
):
    """
    Retrieve chronological feed of all visits logged by this specific RM.
    """
    rm = get_rm_by_id(conn, rm_id)
    if not rm:
        raise HTTPException(status_code=404, detail="Relationship Manager not found")
    return get_rm_visits(conn, rm_id, limit=limit)
