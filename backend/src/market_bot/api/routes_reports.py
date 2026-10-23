from fastapi import Request
from ..core.source_scope import get_request_connection
import tempfile
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from ..config import Settings
from ..core.auth import require_all_sources
from ..db.models import DeadLetterResponse, MerchantReportResponse, StatsSummaryResponse
from ..db.storage import get_all_reports, get_connection, get_dlq_items, get_report_by_id, get_stats_summary

router = APIRouter(prefix="/api/reports", tags=["Reports"])


def get_db(request: Request):
    conn = get_request_connection(request)
    try:
        yield conn
    finally:
        conn.close()


@router.get("", response_model=List[MerchantReportResponse])
def list_reports(
    khan: Optional[str] = Query(None, description="Filter by District / Khan name"),
    stage: Optional[str] = Query(None, description="Filter by KHQR stage (CONVERTED, PIPELINE, TARGET)"),
    sender: Optional[str] = Query(None, description="Filter by sales representative name"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    conn=Depends(get_db),
):
    """List structured merchant reports with optional filters."""
    return get_all_reports(conn, khan=khan, stage=stage, sender=sender, limit=limit, offset=offset)


@router.get("/stats", response_model=StatsSummaryResponse)
def get_stats(conn=Depends(get_db)):
    """Retrieve operational KPIs: total visits, converted count, active vs cold districts."""
    return get_stats_summary(conn)


@router.get("/dlq", response_model=List[DeadLetterResponse])
def list_dlq(limit: int = Query(50, ge=1, le=200), conn=Depends(get_db)):
    """Retrieve Dead-Letter Queue items (missing GPS pins, unparsed messages)."""
    return get_dlq_items(conn, limit=limit)

@router.get("/export/excel")
def export_excel(principal: dict = Depends(require_all_sources)):
    """Download all verified merchant visits as a formatted Excel workbook."""
    settings = Settings.load()
    import sys
    backend_dir = str(Path(__file__).resolve().parent.parent.parent.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from scripts.export_excel import export_to_excel

    temp_dir = Path(tempfile.gettempdir())
    export_path = temp_dir / "CMCB_Market_Visit_Reports.xlsx"
    export_to_excel(settings.db_path, export_path)

    return FileResponse(
        path=str(export_path),
        filename="CMCB_Market_Visit_Reports.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/{report_id}", response_model=MerchantReportResponse)
def get_report(report_id: int, conn=Depends(get_db)):
    """Retrieve a single merchant report by its ID."""
    report = get_report_by_id(conn, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Merchant report not found")
    return report
