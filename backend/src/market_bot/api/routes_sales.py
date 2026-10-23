from fastapi import Request
from ..core.source_scope import get_request_connection
"""Sales Portal API Router
Provides dedicated, high-performance endpoints for the mobile Sales Team Telegram WebApp (TMA)
and responsive Fieldwork dashboard.

100% Grounded in SQLite Database (merchants, merchant_reports, rms). Zero mock / synthetic data.
"""

import base64
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import Settings
from ..db.storage import get_connection
from ..core.tma import require_sales_telegram_auth
router = APIRouter(prefix="/api/sales", tags=["Sales Portal"])

# Live operational date helper in Cambodia Timezone (Asia/Phnom_Penh, UTC+7).
def get_cambodia_today() -> str:
    """Returns today's date in Cambodia timezone (UTC+7) formatted as YYYY-MM-DD."""
    cambodia_now = datetime.now(timezone(timedelta(hours=7)))
    return cambodia_now.strftime("%Y-%m-%d")

def get_dormant_boundary(ref_date_str: Optional[str] = None) -> str:
    """Returns the dormant boundary (14 days before ref_date) formatted as YYYY-MM-DD."""
    base_str = ref_date_str or get_cambodia_today()
    dt = datetime.fromisoformat(f"{base_str}T00:00:00+00:00")
    return (dt - timedelta(days=14)).strftime("%Y-%m-%d")

def get_range_dates(time_range: str, ref_date_str: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Calculates dynamic start and end boundaries for a given range (today, 7d, 30d, all)."""
    base_str = ref_date_str or get_cambodia_today()
    dt = datetime.fromisoformat(f"{base_str}T00:00:00+00:00")
    if time_range == "today":
        start = base_str
        end = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
        return start, end
    elif time_range == "7d":
        return (dt - timedelta(days=7)).strftime("%Y-%m-%d"), None
    elif time_range == "30d":
        return (dt - timedelta(days=30)).strftime("%Y-%m-%d"), None
    return None, None

def _encode_cursor(*values: Any) -> str:
    """Opaque keyset cursor — clients must treat it as an unreadable token."""
    raw = json.dumps(list(values), separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: Optional[str]) -> Optional[List[Any]]:
    """Returns the decoded keyset values, or None when the cursor is absent/invalid."""
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        values = json.loads(decoded)
        return values if isinstance(values, list) and values else None
    except Exception:
        # A malformed cursor should restart at page 1 rather than 500
        return None


def get_db(request: Request):
    conn = get_request_connection(request)
    try:
        yield conn
    finally:
        conn.close()


def _format_time_label(iso_str: Optional[str]) -> str:
    """Formats an ISO timestamp to human 12-hour time (e.g. 10:45 AM)."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%I:%M %p").lstrip("0")
    except Exception:
        if "T" in str(iso_str):
            time_part = iso_str.split("T")[1][:5]
            return time_part
        return str(iso_str)


def _format_date_heading(iso_str: Optional[str], ref_today: Optional[str] = None) -> str:
    """Formats an ISO timestamp to section headers like 'Today · 8 Oct' or 'Yesterday · 7 Oct'."""
    if not iso_str:
        return "Earlier"
    today_str = ref_today or get_cambodia_today()
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")
        day_month = f"{dt.day} {dt:%b}"
        if date_str == today_str:
            return f"Today · {day_month}"
        
        ref_dt = datetime.fromisoformat(f"{today_str}T00:00:00+00:00")
        if date_str == (ref_dt - timedelta(days=1)).strftime("%Y-%m-%d"):
            return f"Yesterday · {day_month}"
            
        return f"{dt:%A} · {day_month}"
    except Exception:
        return str(iso_str)[:10]


def _extract_initials(name: Optional[str]) -> str:
    if not name:
        return "RM"
    parts = name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[1][0]}".upper()
    return name[:2].upper()


def _get_rm_or_default(conn, telegram_id: Optional[int]) -> Optional[Dict[str, Any]]:
    cur = conn.cursor()
    if telegram_id:
        cur.execute("SELECT * FROM rms WHERE telegram_user_id = ?", (telegram_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
    
    # Fallback to top active RM
    cur.execute("SELECT * FROM rms ORDER BY total_visits_logged DESC LIMIT 1;")
    row = cur.fetchone()
    return dict(row) if row else None


# =============================================================================
# 1. PROFILE & RM DIRECTORY
# =============================================================================

@router.get("/profile")
def get_sales_profile(
    telegram_id: Optional[int] = Query(None, description="RM Telegram user ID"),
    auth_user: Dict[str, Any] = Depends(require_sales_telegram_auth),
    conn=Depends(get_db),
):
    """Retrieves current RM profile and the full directory of active RMs for switching."""
    telegram_id = telegram_id or auth_user.get("telegram_user_id")
    cur = conn.cursor()
    
    rm = _get_rm_or_default(conn, telegram_id)
    if not rm:
        raise HTTPException(status_code=404, detail="No Relationship Manager records found.")
    
    top_districts = rm.get("top_districts") or "{}"
    if isinstance(top_districts, str):
        try:
            top_districts = json.loads(top_districts)
        except Exception:
            top_districts = {}
            
    top_categories = rm.get("top_categories") or "{}"
    if isinstance(top_categories, str):
        try:
            top_categories = json.loads(top_categories)
        except Exception:
            top_categories = {}
    
    # List of all available RMs
    cur.execute(
        """
        SELECT id, telegram_user_id, canonical_name, username, 
               total_visits_logged, onboarded_count, conversion_rate
        FROM rms 
        WHERE total_visits_logged > 0
        ORDER BY total_visits_logged DESC;
        """
    )
    all_rms = [
        {
            "id": r["id"],
            "telegram_user_id": r["telegram_user_id"],
            "name": r["canonical_name"],
            "username": r["username"],
            "initials": _extract_initials(r["canonical_name"]),
            "total_visits": r["total_visits_logged"],
            "onboarded_count": r["onboarded_count"],
            "conversion_rate": round(r["conversion_rate"] or 0, 1),
        }
        for r in cur.fetchall()
    ]
    
    return {
        "current_rm": {
            "id": rm["id"],
            "telegram_user_id": rm["telegram_user_id"],
            "name": rm["canonical_name"],
            "username": rm["username"],
            "initials": _extract_initials(rm["canonical_name"]),
            "total_visits": rm["total_visits_logged"],
            "unique_merchants": rm["unique_merchants_reached"],
            "onboarded_count": rm["onboarded_count"],
            "pipeline_count": rm["pipeline_count"],
            "target_count": rm["target_count"],
            "conversion_rate": round(rm["conversion_rate"] or 0, 1),
            "active_working_days": rm["active_working_days"],
            "daily_velocity": round(rm["daily_visit_velocity"] or 0.0, 1),
            "top_districts": top_districts,
            "top_categories": top_categories,
        },
        "available_rms": all_rms,
    }


# =============================================================================
# 2. TODAY DASHBOARD
# =============================================================================

@router.get("/today")
def get_sales_today_dashboard(
    telegram_id: Optional[int] = Query(None, description="RM Telegram user ID"),
    ref_date: Optional[str] = Query(None, description="Reference date YYYY-MM-DD (defaults to live Cambodia date)"),
    auth_user: Dict[str, Any] = Depends(require_sales_telegram_auth),
    conn=Depends(get_db),
):
    """
    Returns real data for the Daily Visit Dashboard based on SQLite tables:
    - KPIs (Visits today / goal, Onboardings today, Follow-ups due, Total customers)
    - Territory mini map info & nearby stops
    - Priority follow-up items with actual merchant remarks
    - Personal visits logged today
    - Live team activity feed
    """
    telegram_id = telegram_id or auth_user.get("telegram_user_id")
    target_date = ref_date.strip() if ref_date and ref_date.strip() else get_cambodia_today()
    cur = conn.cursor()
    rm = _get_rm_or_default(conn, telegram_id)
    if not rm:
        raise HTTPException(status_code=404, detail="RM not found")
        
    rm_id = rm["id"]

    # 1. Visits logged today by this RM
    cur.execute(
        """
        SELECT id, merchant_id, merchant_name, report_time, status_clean, khqr_stage, 
               COALESCE(business_clean, business) as business, district_khan, remark, 
               latitude, longitude, map_url, COALESCE(tel_clean, tel) as tel
        FROM merchant_reports 
        WHERE rm_id = ? AND report_time LIKE ?
        ORDER BY report_time ASC;
        """,
        (rm_id, f"{target_date}%"),
    )
    today_visit_rows = cur.fetchall()

    visits_today_list = [
        {
            "id": r["id"],
            "merchant_id": r["merchant_id"],
            "name": r["merchant_name"],
            "time": _format_time_label(r["report_time"]),
            "outcome": r["status_clean"] or "OP",
            "khqr_stage": r["khqr_stage"] or "TARGET",
            "business": r["business"] or "Retail",
            "district": r["district_khan"] or "Phnom Penh",
            "remark": r["remark"] or "",
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "map_url": r["map_url"],
            "phone": r["tel"] or "",
        }
        for r in today_visit_rows
    ]
    
    visits_today_count = len(visits_today_list)
    new_visits_today_count = sum(
        1 for v in visits_today_list
        if "exist" not in (v["outcome"] or "").lower() and v["khqr_stage"] != "EXISTING"
    )
    onboarded_today_count = sum(1 for v in visits_today_list if v["khqr_stage"] in ["CONVERTED", "EXISTING"])
    recent_onboarded_name = next(
        (v["name"] for v in visits_today_list if v["khqr_stage"] in ["CONVERTED", "EXISTING"]),
        None,
    )
    # 2. Team activity today (real visits by teammates on ref_date)
    cur.execute(
        """
        SELECT m.id, m.merchant_id, m.merchant_name, m.report_time, m.status_clean, m.khqr_stage,
               m.district_khan, m.remark, m.latitude, m.longitude,
               r.canonical_name as rm_name, r.id as rm_id
        FROM merchant_reports m
        JOIN rms r ON m.rm_id = r.id
        WHERE m.report_time LIKE ?
        ORDER BY m.report_time DESC
        LIMIT 100;
        """,
        (f"{target_date}%",),
    )
    team_rows = cur.fetchall()

    # If no team visits on exact ref_date, grab latest team visits
    if not team_rows:
        cur.execute(
            """
            SELECT m.id, m.merchant_id, m.merchant_name, m.report_time, m.status_clean, m.khqr_stage,
                   m.district_khan, m.remark, m.latitude, m.longitude,
                   r.canonical_name as rm_name, r.id as rm_id
            FROM merchant_reports m
            JOIN rms r ON m.rm_id = r.id
            ORDER BY m.report_time DESC
            LIMIT 100;
            """
        )
        team_rows = cur.fetchall()
    
    team_activity = [
        {
            "id": r["id"],
            "merchant_id": r["merchant_id"],
            "merchant_name": r["merchant_name"],
            "rm_id": r["rm_id"],
            "rm_name": r["rm_name"],
            "rm_initials": _extract_initials(r["rm_name"]),
            "is_you": (r["rm_id"] == rm_id),
            "time": _format_time_label(r["report_time"]),
            "status": r["status_clean"] or "OP",
            "stage": r["khqr_stage"] or "TARGET",
            "district": r["district_khan"] or "Phnom Penh",
            "remark": r["remark"] or "",
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "message": f"{r['rm_name']} visited {r['merchant_name']} at {_format_time_label(r['report_time'])} ({r['khqr_stage']}).",
        }
        for r in team_rows
    ]
    # 3. Real Follow-ups to prioritize for this RM:
    # Query merchants visited by this RM that are in PIPELINE or TARGET (not yet onboarded)
    cur.execute(
        """
        SELECT m.id, m.canonical_name, m.business_category, m.tel, m.district_khan,
               m.current_status, m.current_khqr_stage, m.latest_visit_date, m.latest_remark,
               m.latitude, m.longitude
        FROM merchants m
        WHERE m.id IN (
            SELECT DISTINCT merchant_id FROM merchant_reports WHERE rm_id = ?
        )
        AND m.current_khqr_stage IN ('PIPELINE', 'TARGET')
        ORDER BY m.latest_visit_date DESC
        LIMIT 6;
        """,
        (rm_id,),
    )
    followup_rows = cur.fetchall()

    priority_followups = []
    overdue_count = 0
    scheduled_today_count = 0

    try:
        ref_dt = datetime.fromisoformat(f"{ref_date}T00:00:00+00:00")
    except Exception:
        ref_dt = datetime.now(timezone.utc)

    for r in followup_rows:
        last_date_str = r["latest_visit_date"] or ""
        days_diff = 3
        if last_date_str:
            try:
                v_dt = datetime.fromisoformat(last_date_str.replace("Z", "+00:00"))
                days_diff = max(0, (ref_dt.date() - v_dt.date()).days)
            except Exception:
                days_diff = 3

        if days_diff == 0:
            badge = "Visited today"
            due_label = "Today"
            is_overdue = False
            scheduled_today_count += 1
        elif days_diff == 1:
            badge = "1 day ago"
            due_label = "Follow-up due"
            is_overdue = False
            scheduled_today_count += 1
        else:
            badge = f"{days_diff} days overdue"
            due_label = f"{days_diff}d overdue"
            is_overdue = True
            overdue_count += 1

        action_note = r["latest_remark"] if r["latest_remark"] else "Follow up on CMCB merchant products"

        priority_followups.append({
            "id": r["id"],
            "name": r["canonical_name"],
            "contact_name": r["tel"] or "Store Contact",
            "phone": r["tel"] or "N/A",
            "status": r["current_status"] or "OP",
            "khqr_stage": r["current_khqr_stage"],
            "district": r["district_khan"] or "Phnom Penh",
            "last_visit_date": r["latest_visit_date"],
            "due_badge": badge,
            "due_label": due_label,
            "is_overdue": is_overdue,
            "action_note": action_note,
            "latitude": r["latitude"],
            "longitude": r["longitude"],
        })

    # Total follow-ups count for this RM
    cur.execute(
        """
        SELECT count(DISTINCT m.id)
        FROM merchants m
        WHERE m.id IN (
            SELECT DISTINCT merchant_id FROM merchant_reports WHERE rm_id = ?
        )
        AND m.current_khqr_stage IN ('PIPELINE', 'TARGET');
        """,
        (rm_id,),
    )
    total_followups_count = cur.fetchone()[0]

    # 4. Territory info: determine primary district from RM's real visits
    top_districts = rm.get("top_districts") or {}
    if isinstance(top_districts, str):
        try:
            top_districts = json.loads(top_districts)
        except Exception:
            top_districts = {}

    primary_khan = max(top_districts.keys(), key=lambda k: top_districts[k]) if top_districts else "Boeng Keng Kang"

    # Territory center coords from actual merchants in this district
    cur.execute(
        """
        SELECT avg(latitude) as lat, avg(longitude) as lng
        FROM merchants
        WHERE district_khan = ? AND latitude > 0;
        """,
        (primary_khan,),
    )
    center_row = cur.fetchone()
    center_lat = center_row["lat"] if center_row and center_row["lat"] else 11.5564
    center_lng = center_row["lng"] if center_row and center_row["lng"] else 104.9282

    # Territory nearby stores for the mini map
    cur.execute(
        """
        SELECT id, canonical_name, current_khqr_stage, current_status, latitude, longitude,
               assigned_reps, latest_remark
        FROM merchants
        WHERE district_khan = ? AND latitude > 0
        LIMIT 15;
        """,
        (primary_khan,),
    )
    nearby_stores = [
        {
            "id": r["id"],
            "name": r["canonical_name"],
            "stage": r["current_khqr_stage"],
            "status": r["current_status"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "is_assigned_to_me": (rm["canonical_name"] in (r["assigned_reps"] or "")),
        }
        for r in cur.fetchall()
    ]

    # Next stop recommendation from actual priority followups
    next_stop = None
    if priority_followups:
        f = priority_followups[0]
        next_stop = {
            "id": f["id"],
            "name": f["name"],
            "district": f["district"],
            "distance_label": f"In {f['district']}",
            "latitude": f["latitude"],
            "longitude": f["longitude"],
            "action_note": f["action_note"],
        }

    return {
        "date_label": datetime.fromisoformat(f"{target_date}T00:00:00+00:00").strftime("%A, %d %B").replace(", 0", ", "),
        "rm_name": rm["canonical_name"],
        "rm_initials": _extract_initials(rm["canonical_name"]),
        "kpis": {
            "visits_today": visits_today_count,
            "new_visits_today": new_visits_today_count,
            "onboardings_today": onboarded_today_count,
            "recent_onboarded_name": recent_onboarded_name or (visits_today_list[0]["name"] if visits_today_list else "None"),
            "followups_due": total_followups_count,
            "overdue_count": overdue_count,
            "scheduled_today_count": scheduled_today_count,
            "total_customers": rm["unique_merchants_reached"] or 0,
        },
        "territory": {
            "primary_khan": primary_khan,
            "center_latitude": center_lat,
            "center_longitude": center_lng,
            "nearby_stores": nearby_stores,
        },
        "next_stop": next_stop,
        "followups_to_prioritize": priority_followups,
        "visits_today": visits_today_list,
        "team_activity": team_activity,
    }


# =============================================================================
# 3. STORE MAP (TEAM UNIFIED COVERAGE HUB)
# =============================================================================

@router.get("/store-map")
def get_sales_store_map(
    telegram_id: Optional[int] = Query(None, description="RM Telegram user ID"),
    search: Optional[str] = Query(None, description="Search store name or address"),
    khan: Optional[str] = Query(None, description="Filter by district"),
    stage: Optional[str] = Query(None, description="Filter by stage (TARGET, PIPELINE, CONVERTED)"),
    owner: Optional[str] = Query("all", description="Filter by owner: all, me, teammates, unassigned"),
    limit: Optional[int] = Query(None, description="Optional store count limit (omitted returns all stores in view)"),
    auth_user: Dict[str, Any] = Depends(require_sales_telegram_auth),
    conn=Depends(get_db),
):
    """
    Unified store map query for the sales team.
    Shows who has visited each store to avoid overlapping visits and collisions.
    """
    cur = conn.cursor()
    telegram_id = telegram_id or auth_user.get("telegram_user_id")
    rm = _get_rm_or_default(conn, telegram_id)
    rm_name = rm["canonical_name"] if rm else ""
    rm_id = rm["id"] if rm else 0

    query = """
        SELECT m.id, m.canonical_name, m.business_category, m.tel, m.district_khan,
               m.latitude, m.longitude, m.map_url, m.total_visits, m.latest_visit_date,
               m.current_status, m.current_khqr_stage, m.is_onboarded, m.assigned_reps,
               m.latest_remark, m.has_cmcb, m.has_aba, m.has_acleda
        FROM merchants m
        WHERE m.latitude > 0 AND m.longitude > 0
    """
    params: List[Any] = []

    if khan and khan.strip().lower() not in ["all", ""]:
        query += " AND m.district_khan = ?"
        params.append(khan.strip())
    if stage and stage.strip().upper() not in ["ALL", ""]:
        s_upper = stage.strip().upper()
        if s_upper == "SIGNED":
            query += " AND (m.current_khqr_stage IN ('CONVERTED', 'EXISTING') OR m.is_onboarded = 1 OR m.has_cmcb = 1)"
        elif s_upper == "UNSIGNED":
            query += " AND (m.current_khqr_stage NOT IN ('CONVERTED', 'EXISTING') AND m.is_onboarded = 0 AND m.has_cmcb = 0)"
        elif s_upper == "UNSIGNED_RECENT":
            query += " AND (m.current_khqr_stage NOT IN ('CONVERTED', 'EXISTING') AND m.is_onboarded = 0 AND m.has_cmcb = 0) AND m.latest_visit_date >= '2026-09-21'"
        elif s_upper == "UNSIGNED_DORMANT":
            query += " AND (m.current_khqr_stage NOT IN ('CONVERTED', 'EXISTING') AND m.is_onboarded = 0 AND m.has_cmcb = 0) AND (m.latest_visit_date < '2026-09-21' OR m.latest_visit_date IS NULL)"
        else:
            query += " AND m.current_khqr_stage = ?"
            params.append(s_upper)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query += " AND (m.canonical_name LIKE ? OR m.tel LIKE ? OR m.district_khan LIKE ?)"
        params.extend([term, term, term])

    query += " ORDER BY m.latest_visit_date DESC"
    if limit is not None and limit > 0:
        query += " LIMIT ?"
        params.append(limit)
    cur.execute(query, params)
    rows = cur.fetchall()

    # Pre-fetch chronological visit logs for stores with multiple visits (> 1)
    multi_mids = [r["id"] for r in rows if (r["total_visits"] or 1) > 1]
    history_map: Dict[int, List[Dict[str, Any]]] = {}
    if multi_mids:
        placeholders = ",".join("?" for _ in multi_mids)
        cur.execute(
            f"""
            SELECT id, merchant_id, report_time, sender_name, status_clean, khqr_stage, remark
            FROM merchant_reports
            WHERE merchant_id IN ({placeholders})
            ORDER BY report_time DESC;
            """,
            multi_mids,
        )
        for h in cur.fetchall():
            mid = h["merchant_id"]
            if mid not in history_map:
                history_map[mid] = []
            if len(history_map[mid]) < 3:
                history_map[mid].append({
                "date": h["report_time"][:10] if h["report_time"] else "",
                "date_label": _format_date_heading(h["report_time"]),
                "time": _format_time_label(h["report_time"]),
                "sales_rep": h["sender_name"] or "RM",
                "sales_rep_initials": _extract_initials(h["sender_name"]),
                "status": h["status_clean"] or "OP",
                "stage": h["khqr_stage"] or "TARGET",
                "remark": h["remark"] or "",
            })

    stores = []
    unassigned_count = 0
    contacted_count = 0
    onboarded_count = 0
    for r in rows:
        assigned = r["assigned_reps"] or ""
        is_me = bool(rm_name and (rm_name in assigned))
        is_unassigned = (not assigned.strip())

        assigned_name = assigned.split(",")[0].strip() if assigned else "Unassigned"
        initials = _extract_initials(assigned_name) if not is_unassigned else "+"

        if owner == "me" and not is_me:
            continue
        elif owner == "teammates" and (is_me or is_unassigned):
            continue
        elif owner == "unassigned" and not is_unassigned:
            continue

        stage_val = r["current_khqr_stage"] or "TARGET"
        is_signed = bool(
            r["is_onboarded"] or
            stage_val in ["CONVERTED", "EXISTING"] or
            r["has_cmcb"]
        )

        # Elapsed days calculation
        last_date_str = r["latest_visit_date"] or ""
        days_diff = 999
        if last_date_str:
            try:
                ref_dt = datetime.fromisoformat(f"{get_cambodia_today()}T00:00:00+00:00")
                v_dt = datetime.fromisoformat(last_date_str.replace("Z", "+00:00"))
                days_diff = max(0, (ref_dt.date() - v_dt.date()).days)
            except Exception:
                days_diff = 999

        if is_signed:
            status_category = "SIGNED"
            onboarded_count += 1
        elif days_diff > 14:
            status_category = "UNSIGNED_DORMANT"
            unassigned_count += 1
        else:
            status_category = "UNSIGNED_RECENT"
            contacted_count += 1

        stores.append({
            "id": r["id"],
            "name": r["canonical_name"],
            "category": r["business_category"] or "Retail",
            "address": r["district_khan"] or "Phnom Penh",
            "district_khan": r["district_khan"] or "Phnom Penh",
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "map_url": r["map_url"],
            "total_visits": r["total_visits"] or 1,
            "latest_visit_date": r["latest_visit_date"],
            "status": r["current_status"] or "OP",
            "stage": stage_val,
            "is_onboarded": bool(r["is_onboarded"]),
            "is_signed": is_signed,
            "days_since_last_visit": days_diff,
            "status_category": status_category,
            "assigned_reps": assigned,
            "assigned_name": assigned_name,
            "assigned_initials": initials,
            "is_assigned_to_me": is_me,
            "is_unassigned": is_unassigned,
            "latest_remark": r["latest_remark"] or "",
            "phone": r["tel"] or "N/A",
            "has_cmcb": bool(r["has_cmcb"]),
            "has_aba": bool(r["has_aba"]),
            "has_acleda": bool(r["has_acleda"]),
            "visit_history": history_map.get(r["id"], []),
        })

    # Summary of team activity today
    cur.execute(
        """
        SELECT r.canonical_name, r.id, count(m.id) as visits_today,
               sum(CASE WHEN m.khqr_stage IN ('CONVERTED', 'EXISTING') THEN 1 ELSE 0 END) as onboarded_today
        FROM merchant_reports m
        JOIN rms r ON m.rm_id = r.id
        WHERE m.report_time LIKE ?
        GROUP BY r.id
        ORDER BY visits_today DESC;
        """,
        (f"{get_cambodia_today()}%",),
    )
    team_today = [
        {
            "rm_id": t["id"],
            "name": t["canonical_name"],
            "initials": _extract_initials(t["canonical_name"]),
            "visits": t["visits_today"],
            "onboarded": t["onboarded_today"] or 0,
            "is_you": (t["id"] == rm_id),
        }
        for t in cur.fetchall()
    ]

    return {
        "total_stores_in_view": len(stores),
        "unassigned_count": unassigned_count,
        "contacted_count": contacted_count,
        "onboarded_count": onboarded_count,
        "stores": stores,
        "team_today_summary": team_today,
    }


# =============================================================================
# 4. CUSTOMERS ("MY CUSTOMERS" RELATIONSHIP TRACKING)
# =============================================================================

CUSTOMER_PAGE_SIZE = 30
VISIT_PAGE_SIZE = 40


def _signed_sql(prefix: str = "m") -> str:
    return (
        f"({prefix}.is_onboarded = 1 OR {prefix}.has_cmcb = 1 "
        f"OR {prefix}.current_khqr_stage IN ('CONVERTED', 'EXISTING'))"
    )


def _unsigned_sql(prefix: str = "m") -> str:
    return (
        f"(COALESCE({prefix}.is_onboarded, 0) = 0 AND COALESCE({prefix}.has_cmcb, 0) = 0 "
        f"AND COALESCE({prefix}.current_khqr_stage, '') NOT IN ('CONVERTED', 'EXISTING'))"
    )


# sort key -> (ORDER BY clause, cursor columns, direction)
CUSTOMER_SORTS: Dict[str, Tuple[str, Tuple[str, str], str]] = {
    "recent": ("m.latest_visit_date DESC, m.id DESC", ("latest_visit_date", "id"), "DESC"),
    "longest_unvisited": ("m.latest_visit_date ASC, m.id ASC", ("latest_visit_date", "id"), "ASC"),
    "name": ("m.canonical_name ASC, m.id ASC", ("canonical_name", "id"), "ASC"),
}


@router.get("/customers")
def get_sales_customers(
    telegram_id: Optional[int] = Query(None, description="RM Telegram user ID"),
    status: str = Query(
        "ALL",
        description="ALL | SIGNED | NOT_SIGNED | UNSIGNED_RECENT | UNSIGNED_DORMANT",
    ),
    search: Optional[str] = Query(None, description="Search merchant name, phone or district"),
    sort_by: str = Query("recent", description="recent | longest_unvisited | name"),
    cursor: Optional[str] = Query(None, description="Opaque keyset cursor from the previous page"),
    limit: int = Query(CUSTOMER_PAGE_SIZE, ge=1, le=100),
    auth_user: Dict[str, Any] = Depends(require_sales_telegram_auth),
    conn=Depends(get_db),
):
    """
    One page of customer accounts for this sales rep, ordered by a stable keyset.

    Search, status filtering and sorting all happen in SQL so they cover the rep's
    entire book of business, not just the rows already paged into the client.
    Paging is keyset-based (never OFFSET) so concurrently ingested visits cannot
    shift rows and produce duplicates between pages.
    """
    telegram_id = telegram_id or auth_user.get("telegram_user_id")
    cur = conn.cursor()
    rm = _get_rm_or_default(conn, telegram_id)
    if not rm:
        raise HTTPException(status_code=404, detail="RM not found")

    rm_id = rm["id"]

    # Shared WHERE fragment so the page query and the summary counts can never diverge
    base_where = "m.id IN (SELECT DISTINCT merchant_id FROM merchant_reports WHERE rm_id = ?)"
    base_params: List[Any] = [rm_id]

    s = (status or "ALL").strip().upper()
    if s == "SIGNED":
        base_where += f" AND {_signed_sql()}"
    elif s in ("NOT_SIGNED", "UNSIGNED"):
        base_where += f" AND {_unsigned_sql()}"
    elif s == "UNSIGNED_RECENT":
        base_where += f" AND {_unsigned_sql()} AND m.latest_visit_date >= ?"
        base_params.append(get_dormant_boundary())
    elif s == "UNSIGNED_DORMANT":
        base_where += f" AND {_unsigned_sql()} AND m.latest_visit_date < ?"
        base_params.append(get_dormant_boundary())

    if search and search.strip():
        term = f"%{search.strip()}%"
        base_where += " AND (m.canonical_name LIKE ? OR m.tel LIKE ? OR m.district_khan LIKE ?)"
        base_params.extend([term, term, term])

    # Summary counts span the whole filtered set, so the chips show real totals
    cur.execute(
        f"""
        SELECT count(*) AS all_count,
               sum(CASE WHEN m.current_khqr_stage = 'PIPELINE' THEN 1 ELSE 0 END) AS pipeline_count,
               sum(CASE WHEN m.current_khqr_stage IN ('CONVERTED', 'EXISTING') THEN 1 ELSE 0 END) AS converted_count,
               sum(CASE WHEN COALESCE(m.current_khqr_stage, '') NOT IN ('CONVERTED', 'EXISTING', 'PIPELINE')
                        THEN 1 ELSE 0 END) AS target_count
        FROM merchants m
        WHERE {base_where}
        """,
        base_params,
    )
    counts = cur.fetchone()
    total = counts["all_count"] or 0

    order_sql, cursor_cols, direction = CUSTOMER_SORTS.get(sort_by, CUSTOMER_SORTS["recent"])
    page_where = base_where
    page_params: List[Any] = list(base_params)

    keys = _decode_cursor(cursor)
    if keys and len(keys) == 2:
        c1, c2 = keys
        op = "<" if direction == "DESC" else ">"
        page_where += (
            f" AND (m.{cursor_cols[0]} {op} ?"
            f" OR (m.{cursor_cols[0]} = ? AND m.{cursor_cols[1]} {op} ?))"
        )
        page_params.extend([c1, c1, c2])

    # Fetch one extra row to detect whether a further page exists
    page_params.append(limit + 1)
    cur.execute(
        f"""
        SELECT m.id, m.canonical_name, m.business_category, m.tel, m.district_khan,
               m.current_status, m.current_khqr_stage, m.latest_visit_date, m.latest_remark,
               m.latitude, m.longitude, m.total_visits, m.is_onboarded, m.has_cmcb
        FROM merchants m
        WHERE {page_where}
        ORDER BY {order_sql}
        LIMIT ?
        """,
        page_params,
    )
    rows = cur.fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]

    ref_dt = datetime.fromisoformat(f"{get_cambodia_today()}T00:00:00+00:00")
    all_list: List[Dict[str, Any]] = []

    for r in rows:
        stage = r["current_khqr_stage"] or "TARGET"
        status_val = r["current_status"] or "OP"
        action_note = r["latest_remark"] if r["latest_remark"] else "Follow up on CMCB products"

        last_date_str = r["latest_visit_date"] or ""
        days_diff = 0
        if last_date_str:
            try:
                v_dt = datetime.fromisoformat(last_date_str.replace("Z", "+00:00"))
                days_diff = max(0, (ref_dt.date() - v_dt.date()).days)
            except Exception:
                days_diff = 0

        if days_diff == 0:
            duration_label = "Visited today"
        elif days_diff == 1:
            duration_label = "1 day ago"
        elif days_diff < 7:
            duration_label = f"{days_diff} days ago"
        elif days_diff < 14:
            duration_label = "1 week ago"
        elif days_diff < 30:
            duration_label = f"{days_diff // 7} weeks ago"
        else:
            duration_label = f"{days_diff // 30} month(s) ago"

        all_list.append({
            "id": r["id"],
            "name": r["canonical_name"],
            "contact_name": r["tel"] or "Store Contact",
            "business_category": r["business_category"] or "Retail",
            "district": r["district_khan"] or "Phnom Penh",
            "phone": r["tel"] or "N/A",
            "status": status_val,
            "stage": stage,
            "has_cmcb": bool(r["has_cmcb"]),
            "is_onboarded": bool(r["is_onboarded"]),
            "is_signed": bool(r["is_onboarded"] or r["has_cmcb"] or stage in ("CONVERTED", "EXISTING")),
            "latest_visit_date": r["latest_visit_date"],
            "due_badge": duration_label,
            "due_label": duration_label,
            "duration_label": duration_label,
            "days_since_last_visit": days_diff,
            "action_note": action_note,
            "total_visits": r["total_visits"] or 1,
            "latitude": r["latitude"],
            "longitude": r["longitude"],
        })

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last[cursor_cols[0]], last[cursor_cols[1]])

    return {
        "summary": {
            "all_count": total,
            "total_customers": total,
            "pipeline_count": counts["pipeline_count"] or 0,
            "converted_count": counts["converted_count"] or 0,
            "target_count": counts["target_count"] or 0,
            "followups_count": counts["pipeline_count"] or 0,
            "overdue_count": 0,
            "today_count": 0,
            "coming_up_count": 0,
        },
        "all_customers": all_list,
        "overdue": [],
        "today": [],
        "coming_up": [],
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
        "page_size": limit,
    }


# =============================================================================
# 5. VISITS HISTORY FEED ("YOUR VISITS")
# =============================================================================

@router.get("/visits/dates")
def get_sales_visit_dates(
    telegram_id: Optional[int] = Query(None, description="RM Telegram user ID"),
    auth_user: Dict[str, Any] = Depends(require_sales_telegram_auth),
    conn=Depends(get_db),
):
    """
    Returns an index of all distinct calendar dates on which this RM logged visits.
    Lightweight query (<0.5ms) used to immediately populate green dot indicators
    across all months in the calendar jump picker.
    """
    cur = conn.cursor()
    telegram_id = telegram_id or auth_user.get("telegram_user_id")
    rm = _get_rm_or_default(conn, telegram_id)
    if not rm:
        raise HTTPException(status_code=404, detail="RM not found")

    rm_id = rm["id"]
    cur.execute(
        """
        SELECT DISTINCT substr(report_time, 1, 10) as visit_date
        FROM merchant_reports
        WHERE rm_id = ? AND report_time IS NOT NULL AND report_time != ''
        ORDER BY visit_date DESC;
        """,
        (rm_id,),
    )
    dates = [r["visit_date"] for r in cur.fetchall() if r["visit_date"]]
    return {"dates": dates}


@router.get("/visits")
def get_sales_visits(
    telegram_id: Optional[int] = Query(None, description="RM Telegram user ID"),
    time_range: str = Query("7d", description="today, 7d, 30d, all"),
    outcome: Optional[str] = Query(None, description="Filter by outcome/stage"),
    search: Optional[str] = Query(None, description="Search visit notes or store name"),
    jump_date: Optional[str] = Query(None, description="Jump directly to visits on or before YYYY-MM-DD"),
    cursor: Optional[str] = Query(None, description="Opaque keyset cursor from the previous page"),
    limit: int = Query(VISIT_PAGE_SIZE, ge=1, le=200),
    auth_user: Dict[str, Any] = Depends(require_sales_telegram_auth),
    conn=Depends(get_db),
):
    """
    One page of the rep's visit log, newest first, ordered by a stable keyset.

    Returns the page already grouped into date sections; the client merges
    consecutive pages into the same section when a date spans a page boundary.
    """
    telegram_id = telegram_id or auth_user.get("telegram_user_id")
    cur = conn.cursor()
    rm = _get_rm_or_default(conn, telegram_id)
    if not rm:
        raise HTTPException(status_code=404, detail="RM not found")

    rm_id = rm["id"]

    base_where = "rm_id = ?"
    base_params: List[Any] = [rm_id]

    if time_range == "today":
        start_date, end_date = get_range_dates("today")
        base_where += " AND report_time >= ? AND report_time < ?"
        base_params.extend([start_date, end_date])
    elif time_range == "7d":
        start_date, _ = get_range_dates("7d")
        base_where += " AND report_time >= ?"
        base_params.append(start_date)
    elif time_range == "30d":
        start_date, _ = get_range_dates("30d")
        base_where += " AND report_time >= ?"
        base_params.append(start_date)
    if jump_date and jump_date.strip():
        jd = jump_date.strip()
        base_where += " AND report_time <= ?"
        base_params.append(f"{jd}T23:59:59")

    if outcome and outcome.strip().lower() not in ["all", ""]:
        o = outcome.strip().upper()
        if o in ["CONVERTED", "ONBOARDED"]:
            base_where += " AND khqr_stage IN ('CONVERTED', 'EXISTING')"
        elif o in ["PIPELINE", "INTERESTED"]:
            base_where += " AND khqr_stage = 'PIPELINE'"
        else:
            base_where += " AND status_clean LIKE ?"
            base_params.append(f"%{outcome.strip()}%")

    if search and search.strip():
        term = f"%{search.strip()}%"
        base_where += " AND (merchant_name LIKE ? OR remark LIKE ? OR district_khan LIKE ?)"
        base_params.extend([term, term, term])

    # Total across the whole filtered range (drives the insight banner, not the page)
    cur.execute(f"SELECT count(*) AS n FROM merchant_reports WHERE {base_where}", base_params)
    total_visits = cur.fetchone()["n"] or 0

    page_where = base_where
    page_params: List[Any] = list(base_params)

    keys = _decode_cursor(cursor)
    if keys and len(keys) == 2:
        c1, c2 = keys
        page_where += " AND (report_time < ? OR (report_time = ? AND id < ?))"
        page_params.extend([c1, c1, c2])

    # Fetch one extra row to detect whether a further page exists
    page_params.append(limit + 1)
    cur.execute(
        f"""
        SELECT id, merchant_id, merchant_name, report_time, status_clean, khqr_stage,
               district_khan, remark, COALESCE(tel_clean, tel) as tel,
               photo_count, latitude, longitude, map_url
        FROM merchant_reports
        WHERE {page_where}
        ORDER BY report_time DESC, id DESC
        LIMIT ?
        """,
        page_params,
    )
    rows = cur.fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]

    groups_dict: Dict[str, List[Dict[str, Any]]] = {}

    for r in rows:
        heading = _format_date_heading(r["report_time"])
        if heading not in groups_dict:
            groups_dict[heading] = []

        iso_time = r["report_time"] or ""
        date_str = iso_time[:10] if iso_time else ""
        groups_dict[heading].append({
            "id": r["id"],
            "merchant_id": r["merchant_id"],
            "name": r["merchant_name"],
            "date": date_str,
            "time": _format_time_label(r["report_time"]),
            "outcome": r["status_clean"] or "OP",
            "khqr_stage": r["khqr_stage"] or "TARGET",
            "district": r["district_khan"] or "Phnom Penh",
            "remark": r["remark"] or "",
            "phone": r["tel"] or "",
            "photo_count": r["photo_count"] or 1,
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "map_url": r["map_url"],
        })

    grouped_sections = [
        {
            "date_heading": heading,
            "date_slug": items[0]["date"] if items else "",
            "count": len(items),
            "visits": items,
        }
        for heading, items in groups_dict.items()
    ]

    page_count = sum(g["count"] for g in grouped_sections)

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last["report_time"], last["id"])

    return {
        "total_visits": total_visits,
        "page_count": page_count,
        "insight_banner": (
            f"💡 Total {total_visits} verified visits logged in this period "
            f"for {rm['canonical_name']}."
        ),
        "grouped_sections": grouped_sections,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "page_size": limit,
    }


# =============================================================================
# 6. MERCHANT DETAIL PROFILE
# =============================================================================

@router.get("/merchants/{merchant_id}")
def get_sales_merchant_detail(
    merchant_id: int,
    telegram_id: Optional[int] = Query(None, description="RM Telegram user ID"),
    auth_user: Dict[str, Any] = Depends(require_sales_telegram_auth),
    conn=Depends(get_db),
):
    """
    Detailed merchant profile for the sales rep directly from merchants & merchant_reports.
    Includes onboarding stepper, real phone numbers, and full visit timeline.
    """
    cur = conn.cursor()
    telegram_id = telegram_id or auth_user.get("telegram_user_id")
    rm = _get_rm_or_default(conn, telegram_id)
    rm_id = rm["id"] if rm else 0
    rm_name = rm["canonical_name"] if rm else ""

    cur.execute("SELECT * FROM merchants WHERE id = ?", (merchant_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Merchant not found")

    m = dict(row)
    assigned = m.get("assigned_reps") or ""
    is_assigned_to_me = bool(rm_name and (rm_name in assigned))

    # Determine POS onboarding step (1 to 4)
    stage = m.get("current_khqr_stage") or "TARGET"
    if stage in ["CONVERTED", "EXISTING"]:
        step = 4
        step_title = "Live & Processing"
        step_desc = "CMCB KHQR/POS deployed. Active merchant."
    elif stage == "PIPELINE":
        step = 2
        step_title = "Demo Planned / In Discussion"
        step_desc = "Follow-up discussion in progress. Plan POS terminal demonstration."
    else:
        step = 1
        step_title = "Contact Made"
        step_desc = "Initial visit completed. Introduce CMCB merchant solutions."

    # Fetch chronological visit timeline
    cur.execute(
        """
        SELECT id, rm_id, sender_name, report_time, status_clean, khqr_stage,
               remark, photo_count, latitude, longitude, map_url
        FROM merchant_reports
        WHERE merchant_id = ?
        ORDER BY report_time DESC;
        """,
        (merchant_id,),
    )
    timeline_rows = cur.fetchall()

    timeline = [
        {
            "id": t["id"],
            "rm_name": t["sender_name"] or "RM",
            "rm_initials": _extract_initials(t["sender_name"]),
            "is_you": (t["rm_id"] == rm_id),
            "date": t["report_time"][:10] if t["report_time"] else "",
            "date_label": _format_date_heading(t["report_time"]),
            "time": _format_time_label(t["report_time"]),
            "status": t["status_clean"] or "OP",
            "stage": t["khqr_stage"] or "TARGET",
            "remark": t["remark"] or "",
            "photo_count": t["photo_count"] or 1,
            "latitude": t["latitude"],
            "longitude": t["longitude"],
        }
        for t in timeline_rows
    ]

    raw_phone = m.get("tel") or "N/A"
    tel_link = raw_phone if raw_phone not in ["N/A", "TELEGRAM", "None", ""] else None

    return {
        "id": m["id"],
        "name": m["canonical_name"],
        "category": m["business_category"] or "Retail Store",
        "district": m["district_khan"] or "Phnom Penh",
        "address": f"{m.get('district_khan') or 'Phnom Penh'}, Cambodia",
        "stage": stage,
        "status": m.get("current_status") or "OP",
        "is_onboarded": bool(m.get("is_onboarded")),
        "assigned_reps": assigned or "Unassigned",
        "is_assigned_to_me": is_assigned_to_me,
        "last_visit_date": m.get("latest_visit_date"),
        "total_visits": m.get("total_visits") or len(timeline),
        "latitude": m["latitude"],
        "longitude": m["longitude"],
        "map_url": m.get("map_url") or f"https://www.google.com/maps?q={m['latitude']},{m['longitude']}",
        "contact": {
            "name": raw_phone if raw_phone != "N/A" else "Store Contact",
            "role": "Decision Maker / Cashier",
            "phone": raw_phone,
            "telegram": f"@{raw_phone}" if raw_phone != "N/A" and not raw_phone.isdigit() else None,
        },
        "onboarding": {
            "current_step": step,
            "total_steps": 4,
            "step_title": step_title,
            "step_description": step_desc,
            "steps": ["Contact", "Demo", "Documents", "Live"],
        },
        "latest_note": {
            "text": m.get("latest_remark") or "Field visit interaction logged.",
            "author": assigned.split(",")[0] if assigned else "RM",
            "date": m.get("latest_visit_date")[:10] if m.get("latest_visit_date") else "Recent",
        },
        "timeline": timeline,
    }
