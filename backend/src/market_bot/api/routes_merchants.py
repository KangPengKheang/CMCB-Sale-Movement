from fastapi import Request
from ..core.source_scope import get_request_connection
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from ..config import Settings
from ..db.models import MerchantDetailResponse, MerchantResponse, VisitTimelineItem
from ..db.storage import (
    get_all_merchants,
    get_connection,
    get_merchant_by_id,
    get_merchant_visits,
)

router = APIRouter(prefix="/api/merchants", tags=["Merchants"])


def get_db(request: Request):
    conn = get_request_connection(request)
    try:
        yield conn
    finally:
        conn.close()


@router.get("", response_model=List[MerchantResponse])
def list_merchants(
    khan: Optional[str] = Query(None, description="Filter by District / Khan name"),
    stage: Optional[str] = Query(None, description="Filter by KHQR stage (CONVERTED, PIPELINE, TARGET)"),
    min_visits: int = Query(1, ge=1, description="Filter merchants with at least N visits (re-visits)"),
    search: Optional[str] = Query(None, description="Search by merchant name or telephone"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    conn=Depends(get_db),
):
    """
    List unique merchants with aggregated visit counts and current lifecycle stage.
    """
    return get_all_merchants(
        conn=conn,
        khan=khan,
        stage=stage,
        min_visits=min_visits,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/{merchant_id}", response_model=MerchantDetailResponse)
def get_merchant_detail(merchant_id: int, conn=Depends(get_db)):
    """
    Retrieve full merchant profile and chronological visit history timeline.
    """
    merchant = get_merchant_by_id(conn, merchant_id)
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    visits = get_merchant_visits(conn, merchant_id)
    merchant["visits"] = visits
    return merchant


@router.get("/{merchant_id}/timeline", response_model=List[VisitTimelineItem])
def get_merchant_timeline(merchant_id: int, conn=Depends(get_db)):
    """
    Retrieve chronological visit history timeline for a single merchant.
    """
    merchant = get_merchant_by_id(conn, merchant_id)
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return get_merchant_visits(conn, merchant_id)
