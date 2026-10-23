from fastapi import Request
from ..core.source_scope import get_request_connection
import json
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from ..config import Settings
from ..db.storage import get_all_merchants, get_all_reports, get_connection

router = APIRouter(prefix="/api/map", tags=["Map"])


def get_db(request: Request):
    conn = get_request_connection(request)
    try:
        yield conn
    finally:
        conn.close()


@router.get("/geojson")
def get_map_geojson(conn=Depends(get_db)) -> Dict[str, Any]:
    """
    Returns all verified individual visit reports as a GeoJSON FeatureCollection.
    """
    reports = get_all_reports(conn, limit=5000)
    features = []

    for r in reports:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [r["longitude"], r["latitude"]],
            },
            "properties": {
                "id": r["id"],
                "merchant_id": r["merchant_id"],
                "merchant_name": r["merchant_name"],
                "business": r["business_clean"] or r["business"],
                "tel": r["tel_clean"] or r["tel"],
                "bank": r["bank"],
                "status": r["status_clean"] or r["status"],
                "khqr_stage": r["khqr_stage"],
                "district_khan": r["district_khan"],
                "sender_name": r["sender_name"],
                "report_time": r["report_time"],
                "map_url": r["map_url"],
                "photo_count": r["photo_count"],
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/merchants-geojson")
def get_merchants_map_geojson(conn=Depends(get_db)) -> Dict[str, Any]:
    """
    Returns unique consolidated merchant entities as a GeoJSON FeatureCollection.
    """
    merchants = get_all_merchants(conn, limit=5000)
    features = []

    for m in merchants:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [m["longitude"], m["latitude"]],
            },
            "properties": {
                "merchant_id": m["id"],
                "merchant_name": m["canonical_name"],
                "business": m["business_category"],
                "tel": m["tel"],
                "district_khan": m["district_khan"],
                "total_visits": m["total_visits"],
                "first_visit_date": m["first_visit_date"],
                "latest_visit_date": m["latest_visit_date"],
                "current_status": m["current_status"],
                "current_khqr_stage": m["current_khqr_stage"],
                "is_onboarded": m["is_onboarded"],
                "has_aba": m["has_aba"],
                "has_acleda": m["has_acleda"],
                "has_cmcb": m["has_cmcb"],
                "assigned_reps": m["assigned_reps"],
                "latest_remark": m["latest_remark"],
                "map_url": m["map_url"],
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/khan-stats")
def get_khan_stats(conn=Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Returns visit density and cold-zone status for each Phnom Penh district.
    """
    settings = Settings.load()
    pp_khans = []
    if settings.khans_geojson_path.exists():
        try:
            with open(settings.khans_geojson_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                pp_khans = [f["properties"].get("hrname") for f in data.get("features", []) if f.get("properties", {}).get("hrname")]
        except Exception:
            pass

    # Guaranteed fallback to the 14 standard administrative khans if GeoJSON file could not be opened
    DEFAULT_KHANS = [
        "Chamkar Mon", "Doun Penh", "Prampir Meakkakra", "Tuol Kouk",
        "Dangkao", "Mean Chey", "Russey Keo", "Sen Sok",
        "Pur SenChey", "Chroy Changvar", "Prek Pnov", "Chbar Ampov",
        "Boeng Keng Kang", "Kamboul",
    ]
    if not pp_khans:
        pp_khans = DEFAULT_KHANS

    cur = conn.cursor()
    cur.execute(
        """
        SELECT district_khan, count(*) as cnt
        FROM merchant_reports
        WHERE district_khan != 'Other / Outside PP'
        GROUP BY district_khan;
        """
    )
    counts = {}
    for r in cur.fetchall():
        name = r["district_khan"]
        if name:
            counts[name.strip().lower()] = r["cnt"]

    stats = []
    for khan in pp_khans:
        cnt = counts.get(khan.strip().lower(), 0)
        stats.append({
            "khan_name": khan,
            "visit_count": cnt,
            "is_cold_zone": (cnt == 0),
        })

    stats.sort(key=lambda x: -x["visit_count"])
    return stats
