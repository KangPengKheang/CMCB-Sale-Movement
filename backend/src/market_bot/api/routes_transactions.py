"""Transactions API Router
Provides endpoints for weekly mobile banking transaction ingestion,
snapshot querying, delta intelligence, target cluster zones, and
field sales strike mission Excel export.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import math
import os
import io
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool

from ..config import Settings
from ..core.auth import require_operations_admin
from ..db.storage import (
    get_connection,
    save_merchant_snapshots,
    log_transaction_upload,
    get_available_snapshot_weeks,
    get_weekly_merchant_snapshots,
)
from ..core.transaction_pipeline.landmarks import resolve_cluster_name
from ..scripts.export_missions_excel import export_strike_missions_to_excel

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])

def check_file_has_table(db_path: Path, table_name: str) -> bool:
    if not Path(db_path).exists():
        return False
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=? LIMIT 1;", (table_name,))
        has = cur.fetchone() is not None
        conn.close()
        return has
    except Exception:
        return False

def to_int(val: Any, default: int) -> int:
    if hasattr(val, "default"):
        val = val.default
    try:
        return int(val)
    except Exception:
        return default

def to_float(val: Any, default: float) -> float:
    if hasattr(val, "default"):
        val = val.default
    try:
        return float(val)
    except Exception:
        return default

def get_db():
    settings = Settings.load()
    db_file = settings.db_path
    if settings.visit_data_source == "telegram" and (not db_file.exists() or not check_file_has_table(db_file, "merchants_weekly_snapshot")):
        alt_file = settings.db_path.parent / "market_reports.db"
        if alt_file.exists() and check_file_has_table(alt_file, "merchants_weekly_snapshot"):
            db_file = alt_file
    conn = get_connection(db_file)
    try:
        yield conn
    finally:
        conn.close()

def get_raw_storage_dir(settings: Settings) -> Path:
    raw_dir = settings.db_path.parent / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir

def check_table_exists(cursor, table_name: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=? LIMIT 1;", (table_name,))
    return cursor.fetchone() is not None

# --- Spatial & Geometry Helpers ---

def get_distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dy = (lat1 - lat2) * 110574.0
    dx = (lng1 - lng2) * 108940.0
    return math.sqrt(dx * dx + dy * dy)

def compute_dbscan_clusters(merchants: List[Dict[str, Any]], eps_meters: float = 180.0, min_pts: int = 2) -> List[List[Dict[str, Any]]]:
    """Pure Python DBSCAN clustering on geographic coordinates."""
    clusters = []
    visited = set()
    assigned = set()

    for i in range(len(merchants)):
        if i in visited:
            continue
        visited.add(i)

        m_i = merchants[i]
        lat_i, lng_i = m_i["latitude"], m_i["longitude"]

        neighbors = []
        for j in range(len(merchants)):
            m_j = merchants[j]
            if get_distance_meters(lat_i, lng_i, m_j["latitude"], m_j["longitude"]) <= eps_meters:
                neighbors.append(j)

        if len(neighbors) < min_pts:
            continue

        cluster = [m_i]
        assigned.add(i)
        queue = list(neighbors)

        while queue:
            n_idx = queue.pop(0)
            if n_idx not in visited:
                visited.add(n_idx)
                m_n = merchants[n_idx]
                sub_neighbors = []
                for k in range(len(merchants)):
                    m_k = merchants[k]
                    if get_distance_meters(m_n["latitude"], m_n["longitude"], m_k["latitude"], m_k["longitude"]) <= eps_meters:
                        sub_neighbors.append(k)
                if len(sub_neighbors) >= min_pts:
                    for sn in sub_neighbors:
                        if sn not in queue and sn not in visited:
                            queue.append(sn)

            if n_idx not in assigned:
                assigned.add(n_idx)
                cluster.append(merchants[n_idx])

        cluster.sort(key=lambda m: m["transaction_count"], reverse=True)
        clusters.append(cluster)

    return clusters

def compute_convex_hull(points: List[List[float]]) -> List[List[float]]:
    if len(points) <= 2:
        return points

    pts = sorted(points, key=lambda p: (p[1], p[0]))

    def cross(o, a, b):
        return (a[1] - o[1]) * (b[0] - o[0]) - (a[0] - o[0]) * (b[1] - o[1])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]

def expand_polygon(hull: List[List[float]], buffer_meters: float = 28.0) -> List[List[float]]:
    if len(hull) == 1:
        lat, lng = hull[0][0], hull[0][1]
        d_lat = buffer_meters / 110574.0
        d_lng = buffer_meters / 108940.0
        return [
            [lat + d_lat, lng], [lat, lng + d_lng],
            [lat - d_lat, lng], [lat, lng - d_lng],
            [lat + d_lat, lng]
        ]
    if len(hull) == 2:
        p1, p2 = hull[0], hull[1]
        dx = (p2[1] - p1[1]) * 108940.0
        dy = (p2[0] - p1[0]) * 110574.0
        dist = math.sqrt(dx * dx + dy * dy) or 1.0
        nx, ny = -dy / dist, dx / dist
        b_lat = buffer_meters / 110574.0
        b_lng = buffer_meters / 108940.0
        return [
            [p1[0] + ny * b_lat - (dx / dist) * b_lat, p1[1] + nx * b_lng - (dy / dist) * b_lng],
            [p2[0] + ny * b_lat + (dx / dist) * b_lat, p2[1] + nx * b_lng + (dy / dist) * b_lng],
            [p2[0] - ny * b_lat + (dx / dist) * b_lat, p2[1] - nx * b_lng + (dy / dist) * b_lng],
            [p1[0] - ny * b_lat - (dx / dist) * b_lat, p1[1] - nx * b_lng - (dy / dist) * b_lng],
            [p1[0] + ny * b_lat - (dx / dist) * b_lat, p1[1] + nx * b_lng - (dy / dist) * b_lng]
        ]

    c_lat = sum(p[0] for p in hull) / len(hull)
    c_lng = sum(p[1] for p in hull) / len(hull)
    padded = []
    for p in hull:
        dy = (p[0] - c_lat) * 110574.0
        dx = (p[1] - c_lng) * 108940.0
        dist = math.sqrt(dx * dx + dy * dy) or 1.0
        factor = (dist + buffer_meters) / dist
        padded.append([c_lat + (p[0] - c_lat) * factor, c_lng + (p[1] - c_lng) * factor])
    padded.append(padded[0])
    return padded


@router.post("/upload", dependencies=[Depends(require_operations_admin)])
async def upload_weekly_transaction_file(
    file: UploadFile = File(...),
    conn=Depends(get_db)
):
    settings = Settings.load()
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported.")

    raw_dir = get_raw_storage_dir(settings)
    timestamp_prefix = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    clean_filename = f"{timestamp_prefix}_{file.filename}"
    saved_path = raw_dir / clean_filename

    # 1. Stream to disk directly instead of loading entire file into memory at once
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    file_size_bytes = saved_path.stat().st_size

    # 2. Wrapper to run the heavy pandas ETL and DB save in a separate thread
    # This prevents the FastAPI event loop from freezing (which caused Docker healthcheck failures/restarts)
    def process_and_save():
        from ..core.transaction_pipeline.runner import run_pipeline
        
        # ETL pipeline
        df_final, combined_metrics = run_pipeline(str(saved_path), filename=file.filename, db_conn=conn)
        
        # DB persistence
        snapshot_weeks = combined_metrics.get("weeks_processed", [])
        raw_count = combined_metrics.get("raw_rows", 0)
        
        inserted_count = save_merchant_snapshots(conn=conn, df_final=df_final)
        
        return df_final, combined_metrics, snapshot_weeks, raw_count, inserted_count

    try:
        # Offload the heavy lifting to a background thread
        df_final, combined_metrics, snapshot_weeks, raw_count, inserted_count = await run_in_threadpool(process_and_save)
        
        log_transaction_upload(
            conn=conn,
            filename=file.filename,
            file_size_bytes=file_size_bytes,
            weeks=snapshot_weeks,
            raw_rows=raw_count,
            clean_rows=inserted_count,
            status="SUCCESS",
            metrics=combined_metrics,
            error_message=None
        )
    except Exception as e:
        # Extract whatever partial info we have for logging the failure
        err_msg = str(e)
        log_transaction_upload(
            conn=conn,
            filename=file.filename,
            file_size_bytes=file_size_bytes,
            weeks=[],
            raw_rows=0,
            clean_rows=0,
            status="FAILED",
            metrics={},
            error_message=err_msg
        )
        raise HTTPException(status_code=500, detail=f"Pipeline processing or DB persistence failed: {err_msg}")

    return {
        "status": "success",
        "filename": file.filename,
        "raw_rows": raw_count,
        "clean_rows": inserted_count,
        "snapshot_weeks": snapshot_weeks,
        "message": f"Successfully processed {inserted_count:,} merchant records across {len(snapshot_weeks)} week(s)."
    }


@router.get("/weeks")
def list_snapshot_weeks(conn=Depends(get_db)):
    return get_available_snapshot_weeks(conn)


@router.get("/merchants")
def list_weekly_merchants(
    week: Optional[str] = Query("latest", description="ISO Week tag or 'latest'"),
    min_txns: int = Query(0, description="Minimum transactions threshold"),
    is_in_pp: Optional[bool] = Query(None, description="Filter for Phnom Penh boundary"),
    change_status: Optional[str] = Query(None, description="Filter: NEW_POPUP, SURGING, COOLING, STABLE"),
    bank_code: Optional[str] = Query(None, description="Filter by beneficiary bank code"),
    search: Optional[str] = Query(None, description="Search merchant name or ID"),
    limit: int = Query(5000, le=10000, description="Max records to return"),
    conn=Depends(get_db)
):
    return get_weekly_merchant_snapshots(
        conn=conn,
        week=week,
        min_txns=min_txns,
        is_in_pp=is_in_pp,
        change_status=change_status,
        bank_code=bank_code,
        search=search,
        limit=limit
    )


@router.get("/clusters")
def get_target_clusters(
    week: Optional[str] = Query("latest", description="ISO Week tag, 'all', or 'latest'"),
    min_txns: int = Query(11, description="Minimum transactions threshold (>10 txns)"),
    cluster_distance_meters: float = Query(180.0, description="Clustering distance in meters"),
    min_cluster_stores: int = Query(2, description="Minimum stores per cluster"),
    conn=Depends(get_db)
):
    cursor = conn.cursor()
    target_week = week
    int_min_txns = to_int(min_txns, 11)
    float_dist = to_float(cluster_distance_meters, 180.0)
    int_min_stores = to_int(min_cluster_stores, 2)

    has_table = check_table_exists(cursor, "merchants_weekly_snapshot")
    if has_table and target_week == "latest":
        cursor.execute("SELECT MAX(snapshot_week) FROM merchants_weekly_snapshot;")
        row = cursor.fetchone()
        if row and row[0]:
            target_week = row[0]
    merchants_list = []

    if has_table and target_week == "all":
        sql = """
        SELECT merchant_id, merchant_name, bank_code, MAX(transaction_count) as transaction_count, latitude, longitude
        FROM merchants_weekly_snapshot
        WHERE transaction_count >= ? AND is_in_pp = 1
          AND latitude IS NOT NULL AND longitude IS NOT NULL AND latitude > 0
        GROUP BY merchant_id
        ORDER BY transaction_count DESC;
        """
        cursor.execute(sql, (int_min_txns,))
        for r in cursor.fetchall():
            merchants_list.append({
                "merchant_id": str(r[0]),
                "merchant_name": str(r[1] or "Merchant"),
                "bank_code": str(r[2] or "N/A"),
                "transaction_count": int(r[3]),
                "latitude": float(r[4]),
                "longitude": float(r[5])
            })
    elif has_table and target_week:
        sql = """
        SELECT merchant_id, merchant_name, bank_code, transaction_count, latitude, longitude
        FROM merchants_weekly_snapshot
        WHERE snapshot_week = ? AND transaction_count >= ? AND is_in_pp = 1
          AND latitude IS NOT NULL AND longitude IS NOT NULL AND latitude > 0
        ORDER BY transaction_count DESC;
        """
        cursor.execute(sql, (target_week, int_min_txns))
        for r in cursor.fetchall():
            merchants_list.append({
                "merchant_id": str(r[0]),
                "merchant_name": str(r[1] or "Merchant"),
                "bank_code": str(r[2] or "N/A"),
                "transaction_count": int(r[3]),
                "latitude": float(r[4]),
                "longitude": float(r[5])
            })

    # Fallback to pre-bundled dataset if DB returned fewer than min_cluster_stores
    if len(merchants_list) < int_min_stores:
        json_path = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "src" / "data" / "merchants_data.json"
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    j_data = json.load(f)
                for item in j_data:
                    tx = int(item.get("TRANSACTION_COUNT") or item.get("txns") or 0)
                    lat = float(item.get("LATITUDE") or item.get("lat") or 0)
                    lng = float(item.get("LONGITUDE") or item.get("lng") or 0)
                    if tx >= int_min_txns and lat > 0 and lng > 0:
                        merchants_list.append({
                            "merchant_id": item.get("BKG_MERCHN_ID") or item.get("id") or "",
                            "merchant_name": item.get("BKG_MERCHN_NAME") or item.get("name") or "Merchant",
                            "bank_code": item.get("BENEFICIARY_BANK_CODE") or item.get("bank") or "N/A",
                            "transaction_count": tx,
                            "latitude": lat,
                            "longitude": lng
                        })
            except Exception:
                pass

    if len(merchants_list) < int_min_stores:
        return []

    # Run Pure-Python DBSCAN
    raw_clusters = compute_dbscan_clusters(merchants_list, eps_meters=float_dist, min_pts=int_min_stores)
    clusters_list = []
    for c_merchants in raw_clusters:
        pts = [[m["latitude"], m["longitude"]] for m in c_merchants]
        hull = compute_convex_hull(pts)
        poly = expand_polygon(hull, 28.0)

        center_lat = sum(m["latitude"] for m in c_merchants) / len(c_merchants)
        center_lng = sum(m["longitude"] for m in c_merchants) / len(c_merchants)
        total_vol = sum(m["transaction_count"] for m in c_merchants)

        top_name = c_merchants[0]["merchant_name"]
        naming = resolve_cluster_name(center_lat, center_lng, top_name, fallback_idx=len(clusters_list))

        merchant_cards = []
        for rank, m in enumerate(c_merchants, 1):
            merchant_cards.append({
                "rank": rank,
                "merchant_id": m["merchant_id"],
                "merchant_name": m["merchant_name"],
                "bank_code": m["bank_code"],
                "transaction_count": m["transaction_count"],
                "latitude": m["latitude"],
                "longitude": m["longitude"]
            })

        clusters_list.append({
            "id": len(clusters_list) + 1,
            "title": naming["title"],
            "district": naming["district"],
            "short_name": naming["short_name"],
            "center_lat": round(center_lat, 6),
            "center_lng": round(center_lng, 6),
            "polygon": poly,
            "store_count": len(c_merchants),
            "total_volume": total_vol,
            "merchants": merchant_cards
        })

    clusters_list.sort(key=lambda c: c["total_volume"], reverse=True)
    return clusters_list


@router.get("/export-missions")
def export_missions_excel(
    week: Optional[str] = Query("latest", description="ISO Week tag, 'all', or 'latest'"),
    min_txns: int = Query(11, description="Minimum transactions threshold (>10 txns)"),
    cluster_distance_meters: float = Query(180.0, description="Clustering distance in meters"),
    min_cluster_stores: int = Query(2, description="Minimum stores per cluster"),
    conn=Depends(get_db)
):
    cursor = conn.cursor()
    target_week = week
    week_label = "All Available Targets"

    has_table = check_table_exists(cursor, "merchants_weekly_snapshot")
    if has_table and target_week == "latest":
        cursor.execute("SELECT MAX(snapshot_week) FROM merchants_weekly_snapshot;")
        row = cursor.fetchone()
        if row and row[0]:
            target_week = row[0]

    if has_table and target_week and target_week != "all":
        cursor.execute("SELECT week_label FROM merchants_weekly_snapshot WHERE snapshot_week = ? LIMIT 1;", (target_week,))
        row = cursor.fetchone()
        if row and row[0]:
            week_label = row[0]
        else:
            week_label = f"Week {target_week}"

    clusters = get_target_clusters(
        week=target_week,
        min_txns=min_txns,
        cluster_distance_meters=cluster_distance_meters,
        min_cluster_stores=min_cluster_stores,
        conn=conn
    )

    wb = export_strike_missions_to_excel(clusters, week_label=week_label)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"CMCB_Field_Sales_Missions_{target_week or 'latest'}.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/logs")
def get_upload_logs(limit: int = 20, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, filename, file_size_bytes, snapshot_weeks, raw_rows, clean_rows, status, error_message, created_at
    FROM upload_logs
    ORDER BY id DESC
    LIMIT ?;
    """, (limit,))
    rows = cursor.fetchall()

    logs = []
    for r in rows:
        weeks = []
        try:
            weeks = json.loads(r["snapshot_weeks"])
        except Exception:
            pass
        logs.append({
            "id": r["id"],
            "filename": r["filename"],
            "file_size_bytes": r["file_size_bytes"],
            "snapshot_weeks": weeks,
            "raw_rows": r["raw_rows"],
            "clean_rows": r["clean_rows"],
            "status": r["status"],
            "error_message": r["error_message"],
            "created_at": r["created_at"]
        })
    return logs
