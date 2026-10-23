import json
import math
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from .models import (
    MerchantRecord,
    MerchantReportRecord,
    ParsedForm,
    ParsedLocation,
    RMRecord,
    SenderInfo,
)


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        init_connection(conn)
    finally:
        conn.close()


def init_connection(conn: sqlite3.Connection) -> None:
    """Initialize schema on an existing disk or in-memory connection."""
    cur = conn.cursor()

    # 1. Dimension Table: Relationship Managers / Sales Reps
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER UNIQUE NOT NULL,
            canonical_name TEXT NOT NULL,
            username TEXT,
            first_active_date TEXT NOT NULL,
            latest_active_date TEXT NOT NULL,
            total_visits_logged INTEGER DEFAULT 1,
            unique_merchants_reached INTEGER DEFAULT 1,
            onboarded_count INTEGER DEFAULT 0,
            pipeline_count INTEGER DEFAULT 0,
            target_count INTEGER DEFAULT 0,
            conversion_rate REAL DEFAULT 0.0,
            active_working_days INTEGER DEFAULT 1,
            daily_visit_velocity REAL DEFAULT 1.0,
            top_districts TEXT,     -- JSON: {"Sen Sok": 18, ...}
            top_categories TEXT,    -- JSON: {"Coffee Shop / Cafe": 14, ...}
            compliance_errors INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

    # 2. Dimension Table: Unique Merchants / Stores
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS merchants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL,
            business_category TEXT NOT NULL,
            tel TEXT,
            district_khan TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            map_url TEXT,
            total_visits INTEGER DEFAULT 1,
            first_visit_date TEXT NOT NULL,
            latest_visit_date TEXT NOT NULL,
            current_status TEXT NOT NULL,
            current_khqr_stage TEXT NOT NULL,
            is_onboarded INTEGER DEFAULT 0,
            competitor_banks TEXT,
            has_aba INTEGER DEFAULT 0,
            has_acleda INTEGER DEFAULT 0,
            has_cmcb INTEGER DEFAULT 0,
            has_other_bank INTEGER DEFAULT 0,
            assigned_reps TEXT,
            latest_remark TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

    # 3. Fact Table: Individual Visits / Touchpoints
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS merchant_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER REFERENCES merchants(id),
            rm_id INTEGER REFERENCES rms(id),
            report_time TEXT NOT NULL,
            sender_id INTEGER NOT NULL,
            sender_name TEXT NOT NULL,
            merchant_name TEXT NOT NULL,
            tel TEXT,
            tel_clean TEXT,
            business TEXT,
            business_clean TEXT,
            purpose TEXT,
            bank TEXT,
            has_aba INTEGER DEFAULT 0,
            has_acleda INTEGER DEFAULT 0,
            has_cmcb INTEGER DEFAULT 0,
            has_other_bank INTEGER DEFAULT 0,
            amount TEXT,
            interest TEXT,
            loan_type TEXT,
            tenure TEXT,
            maturity TEXT,
            status TEXT,
            status_clean TEXT,
            khqr_stage TEXT NOT NULL,
            potential_level TEXT,
            potential_product TEXT,
            remark TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            district_khan TEXT,
            map_url TEXT,
            location_time TEXT NOT NULL,
            location_diff_seconds REAL,
            form_msg_id INTEGER UNIQUE,
            location_msg_id INTEGER UNIQUE,
            photo_count INTEGER DEFAULT 1,
            photo_msg_ids TEXT,
            raw_text TEXT
        );
        """
    )

    # Add columns if migrating from an older schema
    cur.execute("PRAGMA table_info(merchant_reports);")
    report_cols = [row["name"] for row in cur.fetchall()]
    if "merchant_id" not in report_cols:
        cur.execute("ALTER TABLE merchant_reports ADD COLUMN merchant_id INTEGER REFERENCES merchants(id);")
    if "rm_id" not in report_cols:
        cur.execute("ALTER TABLE merchant_reports ADD COLUMN rm_id INTEGER REFERENCES rms(id);")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dead_letter_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id INTEGER UNIQUE,
            msg_date TEXT NOT NULL,
            sender_id INTEGER,
            sender_name TEXT,
            message_type TEXT NOT NULL,
            reason TEXT NOT NULL,
            raw_content TEXT
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL UNIQUE,
            sender_id INTEGER NOT NULL,
            sender_name TEXT NOT NULL,
            msg_date INTEGER NOT NULL,
            iso_date TEXT NOT NULL,
            grouped_id INTEGER,
            payload_json TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        """
    )

    cur.execute("CREATE INDEX IF NOT EXISTS idx_rms_tg_id ON rms(telegram_user_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_merchants_name ON merchants(canonical_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_merchants_khan ON merchants(district_khan);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_merchants_stage ON merchants(current_khqr_stage);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_merchant_id ON merchant_reports(merchant_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_rm_id ON merchant_reports(rm_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_merchant ON merchant_reports(merchant_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_khan ON merchant_reports(district_khan);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_stage ON merchant_reports(khqr_stage);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_time ON merchant_reports(report_time DESC, id DESC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pending_sender ON pending_events(sender_id, event_type);")

    # Keyset-pagination support for the sales portal infinite lists.
    # These make "the next N rows after this cursor" an index seek instead of a full scan.
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_reports_rm_time "
        "ON merchant_reports(rm_id, report_time DESC, id DESC);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_merchants_visit_cursor "
        "ON merchants(latest_visit_date DESC, id DESC);"
    )

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sales_submissions (
        id INTEGER PRIMARY KEY,
        sender_id INTEGER NOT NULL,
        sender_name TEXT NOT NULL,
        submitted_at TEXT NOT NULL,
        local_date TEXT NOT NULL,
        merchant_name TEXT NOT NULL,
        business TEXT NOT NULL,
        remark TEXT NOT NULL,
        source_channel TEXT NOT NULL,
        has_gps INTEGER NOT NULL,
        has_image INTEGER NOT NULL,
        latitude REAL,
        longitude REAL
    );
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_submissions_sender_time "
        "ON sales_submissions(sender_id,submitted_at,id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_submissions_local_date ON sales_submissions(local_date)"
    )

    # 4. Periodic Snapshot Table: Weekly Aggregated Merchants (from Mobile Banking Transactions)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS merchants_weekly_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_week TEXT NOT NULL,
        week_start_date TEXT NOT NULL,
        week_end_date TEXT NOT NULL,
        week_label TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        merchant_name TEXT,
        bank_code TEXT,
        transaction_count INTEGER NOT NULL,
        prev_week_txns INTEGER DEFAULT 0,
        txn_delta INTEGER DEFAULT 0,
        growth_pct REAL DEFAULT 0.0,
        change_status TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        is_in_pp INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(snapshot_week, merchant_id)
    );
    """)

    # 5. Upload Logs: Audit Trail for Transaction Ingestions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS upload_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        file_size_bytes INTEGER NOT NULL,
        snapshot_weeks TEXT NOT NULL,
        raw_rows INTEGER NOT NULL,
        clean_rows INTEGER NOT NULL,
        status TEXT NOT NULL,
        error_message TEXT,
        metrics_json TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_week ON merchants_weekly_snapshot (snapshot_week);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_m_id ON merchants_weekly_snapshot (merchant_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_status ON merchants_weekly_snapshot (change_status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_pp ON merchants_weekly_snapshot (is_in_pp);")

    conn.commit()


def save_pending_event(
    conn: sqlite3.Connection,
    event_type: str,
    chat_id: int,
    message_id: int,
    sender_id: int,
    sender_name: str,
    msg_date: int,
    iso_date: str,
    grouped_id: Optional[int],
    payload: Dict[str, Any],
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO pending_events (
            event_type, chat_id, message_id, sender_id, sender_name,
            msg_date, iso_date, grouped_id, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%s', 'now'))
        """,
        (
            event_type,
            chat_id,
            message_id,
            sender_id,
            sender_name,
            msg_date,
            iso_date,
            grouped_id,
            json.dumps(payload),
        ),
    )
    conn.commit()


def find_matching_pending_event(
    conn: sqlite3.Connection,
    target_event_type: str,
    sender_id: int,
    current_date: int,
    window_seconds: int = 900,
) -> Optional[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM pending_events
        WHERE event_type = ?
          AND sender_id = ?
          AND abs(msg_date - ?) <= ?
        ORDER BY abs(msg_date - ?) ASC
        LIMIT 1
        """,
        (target_event_type, sender_id, current_date, window_seconds, current_date),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def delete_pending_event(conn: sqlite3.Connection, message_id: int) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM pending_events WHERE message_id = ?", (message_id,))
    conn.commit()


def _normalize_name_match(name1: Optional[str], name2: Optional[str]) -> bool:
    n1 = re.sub(r"[\s\-_.,/()]+", "", (name1 or "").lower())
    n2 = re.sub(r"[\s\-_.,/()]+", "", (name2 or "").lower())
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    min_len = min(len(n1), len(n2))
    max_len = max(len(n1), len(n2))
    if (n1 in n2 or n2 in n1) and (min_len / max_len >= 0.7):
        return True
    return False


def _haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def _to_epoch(t: Any) -> Optional[int]:
    if isinstance(t, (int, float)):
        return int(t)
    if isinstance(t, str):
        try:
            return int(datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp())
        except Exception:
            return None
    return None


def find_recent_duplicate_report(
    conn: sqlite3.Connection,
    sender_id: int,
    merchant_name: str,
    target_time: Any,
    window_seconds: int = 1800,
    tel: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Check if a report from the same RM was already logged within the last `window_seconds` (default 30 min)
    for the same merchant.
    """
    target_epoch = _to_epoch(target_time)
    if target_epoch is None:
        return None

    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM merchant_reports
        WHERE sender_id = ?
        ORDER BY id DESC
        LIMIT 15;
        """,
        (sender_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        rep_time_str = r.get("report_time")
        if not rep_time_str:
            continue
        rep_epoch = _to_epoch(rep_time_str)
        if rep_epoch is None:
            continue

        diff_sec = abs(target_epoch - rep_epoch)
        if diff_sec > window_seconds:
            continue

        n_match = _normalize_name_match(merchant_name, r.get("merchant_name"))
        t_clean_input = re.sub(r"\D", "", tel or "")
        t_clean_row = re.sub(r"\D", "", r.get("tel_clean") or r.get("tel") or "")
        tel_match = bool(t_clean_input and t_clean_row and len(t_clean_input) >= 8 and t_clean_input == t_clean_row)

        if not (n_match or tel_match):
            continue

        r_lat = r.get("latitude")
        r_lng = r.get("longitude")
        if lat is not None and lng is not None and r_lat is not None and r_lng is not None:
            dist = _haversine_distance_meters(lat, lng, r_lat, r_lng)
            if dist > 150.0:
                continue

        return r

    return None


def find_pending_duplicate_form(
    conn: sqlite3.Connection,
    sender_id: int,
    merchant_name: str,
    target_time: Any,
    window_seconds: int = 1800,
    tel: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Check if a pending form event already exists from the same sender within window_seconds
    for the same merchant.
    """
    target_epoch = _to_epoch(target_time)
    if target_epoch is None:
        return None

    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM pending_events
        WHERE event_type = 'form'
          AND sender_id = ?
          AND abs(msg_date - ?) <= ?
        ORDER BY abs(msg_date - ?) ASC;
        """,
        (sender_id, target_epoch, window_seconds, target_epoch),
    )
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        try:
            payload = json.loads(r.get("payload_json") or "{}")
            form_payload = payload.get("form", {})
            p_name = form_payload.get("name")
            p_tel = form_payload.get("tel")
            n_match = _normalize_name_match(merchant_name, p_name)
            t_clean_input = re.sub(r"\D", "", tel or "")
            t_clean_p = re.sub(r"\D", "", p_tel or "")
            tel_match = bool(t_clean_input and t_clean_p and len(t_clean_input) >= 8 and t_clean_input == t_clean_p)
            if n_match or tel_match:
                return r
        except Exception:
            continue
    return None

def upsert_merchant_report(conn: sqlite3.Connection, report: MerchantReportRecord) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO merchant_reports (
            merchant_id, rm_id, report_time, sender_id, sender_name, merchant_name,
            tel, tel_clean, business, business_clean, purpose,
            bank, has_aba, has_acleda, has_cmcb, has_other_bank,
            amount, interest, loan_type, tenure, maturity,
            status, status_clean, khqr_stage, potential_level,
            potential_product, remark, latitude, longitude,
            district_khan, map_url, location_time, location_diff_seconds,
            form_msg_id, location_msg_id, photo_count, photo_msg_ids, raw_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report.merchant_id,
            report.rm_id,
            report.report_time,
            report.sender_id,
            report.sender_name,
            report.merchant_name,
            report.tel,
            report.tel_clean,
            report.business,
            report.business_clean,
            report.purpose,
            report.bank,
            report.has_aba,
            report.has_acleda,
            report.has_cmcb,
            report.has_other_bank,
            report.amount,
            report.interest,
            report.loan_type,
            report.tenure,
            report.maturity,
            report.status,
            report.status_clean,
            report.khqr_stage,
            report.potential_level,
            report.potential_product,
            report.remark,
            report.latitude,
            report.longitude,
            report.district_khan,
            report.map_url,
            report.location_time,
            report.location_diff_seconds,
            report.form_msg_id,
            report.location_msg_id,
            report.photo_count,
            report.photo_msg_ids,
            report.raw_text,
        ),
    )
    conn.commit()
    return cur.lastrowid


def upsert_merchant(conn: sqlite3.Connection, m: MerchantRecord) -> int:
    cur = conn.cursor()
    now_iso = m.updated_at or m.latest_visit_date
    created_at = m.created_at or m.first_visit_date

    if m.id:
        cur.execute(
            """
            UPDATE merchants SET
                canonical_name = ?,
                business_category = ?,
                tel = ?,
                district_khan = ?,
                latitude = ?,
                longitude = ?,
                map_url = ?,
                total_visits = ?,
                first_visit_date = ?,
                latest_visit_date = ?,
                current_status = ?,
                current_khqr_stage = ?,
                is_onboarded = ?,
                competitor_banks = ?,
                has_aba = ?,
                has_acleda = ?,
                has_cmcb = ?,
                has_other_bank = ?,
                assigned_reps = ?,
                latest_remark = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                m.canonical_name,
                m.business_category,
                m.tel,
                m.district_khan,
                m.latitude,
                m.longitude,
                m.map_url,
                m.total_visits,
                m.first_visit_date,
                m.latest_visit_date,
                m.current_status,
                m.current_khqr_stage,
                m.is_onboarded,
                m.competitor_banks,
                m.has_aba,
                m.has_acleda,
                m.has_cmcb,
                m.has_other_bank,
                m.assigned_reps,
                m.latest_remark,
                now_iso,
                m.id,
            ),
        )
        conn.commit()
        return m.id

    cur.execute(
        """
        INSERT INTO merchants (
            canonical_name, business_category, tel, district_khan,
            latitude, longitude, map_url, total_visits, first_visit_date,
            latest_visit_date, current_status, current_khqr_stage,
            is_onboarded, competitor_banks, has_aba, has_acleda,
            has_cmcb, has_other_bank, assigned_reps, latest_remark,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            m.canonical_name,
            m.business_category,
            m.tel,
            m.district_khan,
            m.latitude,
            m.longitude,
            m.map_url,
            m.total_visits,
            m.first_visit_date,
            m.latest_visit_date,
            m.current_status,
            m.current_khqr_stage,
            m.is_onboarded,
            m.competitor_banks,
            m.has_aba,
            m.has_acleda,
            m.has_cmcb,
            m.has_other_bank,
            m.assigned_reps,
            m.latest_remark,
            created_at,
            now_iso,
        ),
    )
    conn.commit()
    return cur.lastrowid


def upsert_rm(conn: sqlite3.Connection, rm: RMRecord) -> int:
    cur = conn.cursor()
    now_iso = rm.updated_at or rm.latest_active_date
    created_at = rm.created_at or rm.first_active_date

    if rm.id:
        cur.execute(
            """
            UPDATE rms SET
                canonical_name = ?,
                username = ?,
                first_active_date = ?,
                latest_active_date = ?,
                total_visits_logged = ?,
                unique_merchants_reached = ?,
                onboarded_count = ?,
                pipeline_count = ?,
                target_count = ?,
                conversion_rate = ?,
                active_working_days = ?,
                daily_visit_velocity = ?,
                top_districts = ?,
                top_categories = ?,
                compliance_errors = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                rm.canonical_name,
                rm.username,
                rm.first_active_date,
                rm.latest_active_date,
                rm.total_visits_logged,
                rm.unique_merchants_reached,
                rm.onboarded_count,
                rm.pipeline_count,
                rm.target_count,
                rm.conversion_rate,
                rm.active_working_days,
                rm.daily_visit_velocity,
                rm.top_districts,
                rm.top_categories,
                rm.compliance_errors,
                now_iso,
                rm.id,
            ),
        )
        conn.commit()
        return rm.id

    cur.execute(
        """
        INSERT OR REPLACE INTO rms (
            telegram_user_id, canonical_name, username, first_active_date,
            latest_active_date, total_visits_logged, unique_merchants_reached,
            onboarded_count, pipeline_count, target_count, conversion_rate,
            active_working_days, daily_visit_velocity, top_districts,
            top_categories, compliance_errors, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rm.telegram_user_id,
            rm.canonical_name,
            rm.username,
            rm.first_active_date,
            rm.latest_active_date,
            rm.total_visits_logged,
            rm.unique_merchants_reached,
            rm.onboarded_count,
            rm.pipeline_count,
            rm.target_count,
            rm.conversion_rate,
            rm.active_working_days,
            rm.daily_visit_velocity,
            rm.top_districts,
            rm.top_categories,
            rm.compliance_errors,
            created_at,
            now_iso,
        ),
    )
    conn.commit()
    return cur.lastrowid


def link_visit_to_entities(
    conn: sqlite3.Connection,
    visit_id: int,
    merchant_id: Optional[int] = None,
    rm_id: Optional[int] = None,
) -> None:
    cur = conn.cursor()
    updates = []
    params = []
    if merchant_id is not None:
        updates.append("merchant_id = ?")
        params.append(merchant_id)
    if rm_id is not None:
        updates.append("rm_id = ?")
        params.append(rm_id)
    if updates:
        params.append(visit_id)
        cur.execute(f"UPDATE merchant_reports SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()


def recalculate_rm_aggregates(conn: sqlite3.Connection, rm_id: int) -> None:
    """Recalculates performance and habits metrics for an RM based on their logged visits."""
    cur = conn.cursor()

    cur.execute("SELECT * FROM rms WHERE id = ?", (rm_id,))
    rm_row = cur.fetchone()
    if not rm_row:
        return

    tg_id = rm_row["telegram_user_id"]

    # Query all visits for this RM
    cur.execute(
        """
        SELECT 
            report_time,
            merchant_id,
            district_khan,
            business_clean,
            khqr_stage
        FROM merchant_reports
        WHERE rm_id = ? OR sender_id = ?
        ORDER BY report_time ASC, id ASC;
        """,
        (rm_id, tg_id),
    )
    visits = cur.fetchall()

    if not visits:
        return

    total_visits = len(visits)
    unique_merchants = len(set(v["merchant_id"] for v in visits if v["merchant_id"])) or total_visits

    first_date = visits[0]["report_time"]
    latest_date = visits[-1]["report_time"]

    active_days_set = set(v["report_time"][:10] for v in visits if v["report_time"])
    active_days_cnt = max(1, len(active_days_set))
    daily_velocity = round(total_visits / active_days_cnt, 1)

    onboarded = sum(1 for v in visits if v["khqr_stage"] in ["CONVERTED", "EXISTING"])
    pipeline = sum(1 for v in visits if v["khqr_stage"] == "PIPELINE")
    target = sum(1 for v in visits if v["khqr_stage"] == "TARGET")

    conv_rate = round((onboarded / max(1, unique_merchants)) * 100, 1)

    # Habits: Top Districts & Categories
    districts_counter = Counter(v["district_khan"] for v in visits if v["district_khan"] and v["district_khan"] != "Other / Outside PP")
    categories_counter = Counter(v["business_clean"] for v in visits if v["business_clean"])

    # Compliance errors in DLQ
    cur.execute("SELECT count(*) as dlq_cnt FROM dead_letter_queue WHERE sender_id = ?;", (tg_id,))
    dlq_cnt = cur.fetchone()["dlq_cnt"]

    cur.execute(
        """
        UPDATE rms SET
            first_active_date = ?,
            latest_active_date = ?,
            total_visits_logged = ?,
            unique_merchants_reached = ?,
            onboarded_count = ?,
            pipeline_count = ?,
            target_count = ?,
            conversion_rate = ?,
            active_working_days = ?,
            daily_visit_velocity = ?,
            top_districts = ?,
            top_categories = ?,
            compliance_errors = ?,
            updated_at = ?
        WHERE id = ?;
        """,
        (
            first_date,
            latest_date,
            total_visits,
            unique_merchants,
            onboarded,
            pipeline,
            target,
            conv_rate,
            active_days_cnt,
            daily_velocity,
            json.dumps(dict(districts_counter.most_common(5))),
            json.dumps(dict(categories_counter.most_common(5))),
            dlq_cnt,
            latest_date,
            rm_id,
        ),
    )
    conn.commit()


def save_dlq_item(
    conn: sqlite3.Connection,
    msg_id: int,
    msg_date: str,
    sender_id: int,
    sender_name: str,
    message_type: str,
    reason: str,
    raw_content: str,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO dead_letter_queue (
            msg_id, msg_date, sender_id, sender_name,
            message_type, reason, raw_content
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (msg_id, msg_date, sender_id, sender_name, message_type, reason, raw_content),
    )
    conn.commit()


def sweep_expired_events(conn: sqlite3.Connection, window_seconds: int = 900) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM pending_events
        WHERE (strftime('%s', 'now') - msg_date) > ?
        """,
        (window_seconds,),
    )
    expired = cur.fetchall()

    for item in expired:
        event_type = item["event_type"]
        payload = json.loads(item["payload_json"])

        if event_type == "form":
            raw_text = ""
            if isinstance(payload.get("form"), dict):
                raw_text = payload["form"].get("raw_text", "")
            if not raw_text:
                raw_text = payload.get("raw_text", "")

            save_dlq_item(
                conn=conn,
                msg_id=item["message_id"],
                msg_date=item["iso_date"],
                sender_id=item["sender_id"],
                sender_name=item["sender_name"],
                message_type="unmatched_report",
                reason=f"Merchant form timed out without matching GPS pin after {window_seconds}s",
                raw_content=raw_text,
            )
        elif event_type == "location":
            save_dlq_item(
                conn=conn,
                msg_id=item["message_id"],
                msg_date=item["iso_date"],
                sender_id=item["sender_id"],
                sender_name=item["sender_name"],
                message_type="orphaned_location",
                reason=f"GPS pin timed out without matching visit report after {window_seconds}s",
                raw_content=f"lat: {payload.get('latitude')}, lon: {payload.get('longitude')}",
            )

        cur.execute("DELETE FROM pending_events WHERE id = ?", (item["id"],))

    conn.commit()
    return len(expired)


# --- Query functions for FastAPI REST Endpoints ---

def get_all_reports(
    conn: sqlite3.Connection,
    khan: Optional[str] = None,
    stage: Optional[str] = None,
    sender: Optional[str] = None,
    rm_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    query = "SELECT * FROM merchant_reports WHERE 1=1"
    params: List[Any] = []

    if khan:
        query += " AND district_khan = ?"
        params.append(khan)
    if stage:
        query += " AND khqr_stage = ?"
        params.append(stage)
    if sender:
        query += " AND sender_name LIKE ?"
        params.append(f"%{sender}%")
    if rm_id:
        query += " AND rm_id = ?"
        params.append(rm_id)

    query += " ORDER BY report_time DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cur.execute(query, params)
    return [dict(r) for r in cur.fetchall()]


def get_report_by_id(conn: sqlite3.Connection, report_id: int) -> Optional[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM merchant_reports WHERE id = ?", (report_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def get_all_merchants(
    conn: sqlite3.Connection,
    khan: Optional[str] = None,
    stage: Optional[str] = None,
    min_visits: int = 1,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    query = "SELECT * FROM merchants WHERE total_visits >= ?"
    params: List[Any] = [min_visits]

    if khan:
        query += " AND district_khan = ?"
        params.append(khan)
    if stage:
        query += " AND current_khqr_stage = ?"
        params.append(stage)
    if search:
        query += " AND (canonical_name LIKE ? OR tel LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY total_visits DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cur.execute(query, params)
    return [dict(r) for r in cur.fetchall()]


def get_merchant_by_id(conn: sqlite3.Connection, merchant_id: int) -> Optional[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM merchants WHERE id = ?", (merchant_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def get_merchant_visits(conn: sqlite3.Connection, merchant_id: int) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 
            id as visit_id,
            merchant_id,
            rm_id,
            report_time,
            sender_name as sales_rep,
            status_clean as status,
            khqr_stage,
            bank,
            remark,
            photo_count,
            latitude,
            longitude,
            map_url
        FROM merchant_reports
        WHERE merchant_id = ?
        ORDER BY report_time ASC, id ASC;
        """,
        (merchant_id,),
    )
    rows = cur.fetchall()
    visits = []
    for idx, r in enumerate(rows, start=1):
        v = dict(r)
        v["visit_no"] = idx
        visits.append(v)
    return visits


def get_all_rms(
    conn: sqlite3.Connection,
    sort_by: str = "visits",
    limit: int = 100,
    offset: int = 0,
    include_visits: bool = True,
) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    order_map = {
        "visits": "total_visits_logged DESC",
        "onboarded": "onboarded_count DESC",
        "conversion_rate": "conversion_rate DESC",
        "velocity": "daily_visit_velocity DESC",
        "merchants": "unique_merchants_reached DESC",
    }
    order_clause = order_map.get(sort_by, "total_visits_logged DESC")

    cur.execute(f"SELECT * FROM rms ORDER BY {order_clause}, id ASC LIMIT ? OFFSET ?", (limit, offset))
    rows = cur.fetchall()

    results = []
    for r in rows:
        rm_dict = dict(r)
        rm_id = rm_dict["id"]
        rm_dict["rm_id"] = rm_id
        rm_dict["name"] = rm_dict.get("canonical_name", "")

        # Deserialize JSON fields
        if isinstance(rm_dict.get("top_districts"), str):
            try:
                rm_dict["top_districts"] = json.loads(rm_dict["top_districts"]) if rm_dict["top_districts"] else {}
            except Exception:
                rm_dict["top_districts"] = {}
        elif not rm_dict.get("top_districts"):
            rm_dict["top_districts"] = {}

        if isinstance(rm_dict.get("top_categories"), str):
            try:
                rm_dict["top_categories"] = json.loads(rm_dict["top_categories"]) if rm_dict["top_categories"] else {}
            except Exception:
                rm_dict["top_categories"] = {}
        elif not rm_dict.get("top_categories"):
            rm_dict["top_categories"] = {}

        if include_visits:
            cur.execute(
                """
                SELECT 
                    id as visit_id,
                    merchant_id,
                    rm_id,
                    report_time,
                    merchant_name,
                    business_clean as business,
                    district_khan,
                    status_clean as status,
                    khqr_stage,
                    bank,
                    remark,
                    latitude,
                    longitude,
                    map_url
                FROM merchant_reports
                WHERE rm_id = ?
                ORDER BY report_time ASC, id ASC;
                """,
                (rm_id,),
            )
            rm_visits = []
            for seq_idx, v in enumerate(cur.fetchall(), start=1):
                vd = dict(v)
                vd["sequence_no"] = seq_idx
                rm_visits.append(vd)
            rm_dict["visits"] = rm_visits
        else:
            rm_dict["visits"] = []

        results.append(rm_dict)

    return results

def get_rm_by_id(conn: sqlite3.Connection, rm_id: int) -> Optional[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM rms WHERE id = ?", (rm_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def get_rm_by_telegram_id(conn: sqlite3.Connection, telegram_user_id: int) -> Optional[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM rms WHERE telegram_user_id = ?", (telegram_user_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def get_rm_visits(conn: sqlite3.Connection, rm_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 
            id as visit_id,
            merchant_id,
            rm_id,
            report_time,
            sender_name as sales_rep,
            merchant_name,
            COALESCE(business_clean, business) as business,
            district_khan,
            status_clean as status,
            khqr_stage,
            bank,
            remark,
            photo_count,
            latitude,
            longitude,
            map_url
        FROM merchant_reports
        WHERE rm_id = ?
        ORDER BY report_time ASC, id ASC
        LIMIT ?;
        """,
        (rm_id, limit),
    )
    rows = cur.fetchall()
    visits = []
    for idx, r in enumerate(rows, start=1):
        v = dict(r)
        v["visit_no"] = idx
        visits.append(v)
    return visits


def get_rm_habits(conn: sqlite3.Connection, rm_id: int) -> Optional[Dict[str, Any]]:
    rm = get_rm_by_id(conn, rm_id)
    if not rm:
        return None

    top_d = json.loads(rm["top_districts"]) if rm["top_districts"] else {}
    top_c = json.loads(rm["top_categories"]) if rm["top_categories"] else {}

    return {
        "rm_id": rm["id"],
        "rm_name": rm["canonical_name"],
        "top_districts": top_d,
        "top_categories": top_c,
        "daily_visit_velocity": rm["daily_visit_velocity"],
        "active_working_days": rm["active_working_days"],
    }


def get_stats_summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    cur = conn.cursor()

    cur.execute("SELECT count(*) as total FROM merchant_reports;")
    total_visits = cur.fetchone()["total"]

    cur.execute("SELECT count(*) as total_m FROM merchants;")
    total_merchants = cur.fetchone()["total_m"]

    cur.execute("SELECT count(*) as total_r FROM rms;")
    total_rms = cur.fetchone()["total_r"]

    cur.execute("SELECT count(*) as cnt FROM merchant_reports WHERE khqr_stage IN ('CONVERTED', 'EXISTING');")
    converted = cur.fetchone()["cnt"]

    cur.execute("SELECT count(*) as cnt FROM merchant_reports WHERE khqr_stage = 'PIPELINE';")
    pipeline = cur.fetchone()["cnt"]

    cur.execute("SELECT count(*) as cnt FROM merchant_reports WHERE khqr_stage = 'TARGET';")
    target = cur.fetchone()["cnt"]

    cur.execute("SELECT count(DISTINCT district_khan) as active_khans FROM merchant_reports WHERE district_khan != 'Other / Outside PP';")
    active_khans = cur.fetchone()["active_khans"]
    cold_khans = max(0, 14 - active_khans)

    cur.execute("SELECT sum(photo_count) as total_photos FROM merchant_reports;")
    photos_row = cur.fetchone()
    total_photos = photos_row["total_photos"] or total_visits

    cur.execute("SELECT count(*) as total_dlq FROM dead_letter_queue;")
    total_dlq = cur.fetchone()["total_dlq"]

    return {
        "total_visits": total_visits,
        "total_merchants": total_merchants,
        "total_rms": total_rms,
        "cmcb_deployed": converted,
        "in_pipeline": pipeline,
        "competitor_only": target,
        "active_districts": active_khans,
        "cold_districts": cold_khans,
        "total_photos_linked": total_photos,
        "total_dlq_items": total_dlq,
    }


def get_dlq_items(conn: sqlite3.Connection, limit: int = 50) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM dead_letter_queue ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in cur.fetchall()]


# --- Transaction Weekly Snapshot & Upload Storage Helpers ---

def save_merchant_snapshots(conn: sqlite3.Connection, df_final) -> int:
    """
    Upserts weekly snapshot DataFrame rows into `merchants_weekly_snapshot`.
    Idempotent: Re-uploading the same week cleanly overwrites without duplicates.
    """
    import pandas as pd
    cursor = conn.cursor()
    insert_sql = """
    INSERT OR REPLACE INTO merchants_weekly_snapshot (
        snapshot_week, week_start_date, week_end_date, week_label,
        merchant_id, merchant_name, bank_code, transaction_count,
        prev_week_txns, txn_delta, growth_pct, change_status,
        latitude, longitude, is_in_pp
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    rows = []
    for _, r in df_final.iterrows():
        rows.append((
            str(r["ISO_WEEK"]),
            str(r["WEEK_START_DATE"]),
            str(r["WEEK_END_DATE"]),
            str(r["WEEK_LABEL"]),
            str(r["BKG_MERCHN_ID"]),
            str(r["BKG_MERCHN_NAME"]) if pd.notna(r["BKG_MERCHN_NAME"]) else "",
            str(r["BENEFICIARY_BANK_CODE"]) if pd.notna(r["BENEFICIARY_BANK_CODE"]) else "",
            int(r["TRANSACTION_COUNT"]),
            int(r["PREV_WEEK_TXNS"]) if pd.notna(r["PREV_WEEK_TXNS"]) else 0,
            int(r["TXN_DELTA"]) if pd.notna(r["TXN_DELTA"]) else 0,
            float(r["GROWTH_PCT"]) if pd.notna(r["GROWTH_PCT"]) else 0.0,
            str(r["CHANGE_STATUS"]),
            float(r["LATITUDE"]) if pd.notna(r["LATITUDE"]) else None,
            float(r["LONGITUDE"]) if pd.notna(r["LONGITUDE"]) else None,
            1 if bool(r["IS_IN_PP"]) else 0
        ))

    cursor.executemany(insert_sql, rows)
    conn.commit()
    return len(rows)


def log_transaction_upload(
    conn: sqlite3.Connection,
    filename: str,
    file_size_bytes: int,
    weeks: list,
    raw_rows: int,
    clean_rows: int,
    status: str,
    metrics: dict,
    error_message: str = None
) -> None:
    """Logs an ETL transaction ingestion job into `upload_logs`."""
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO upload_logs (
        filename, file_size_bytes, snapshot_weeks, raw_rows, clean_rows, status, error_message, metrics_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        filename,
        file_size_bytes,
        json.dumps(weeks),
        raw_rows,
        clean_rows,
        status,
        error_message,
        json.dumps(metrics)
    ))
    conn.commit()


def get_available_snapshot_weeks(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Returns all available weekly snapshots and aggregated volume totals."""
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
        snapshot_week AS iso_week,
        week_start_date,
        week_end_date,
        week_label,
        COUNT(*) AS merchant_count,
        SUM(transaction_count) AS total_volume,
        SUM(CASE WHEN is_in_pp = 1 THEN 1 ELSE 0 END) AS merchants_in_pp,
        SUM(CASE WHEN is_in_pp = 1 AND transaction_count >= 20 THEN 1 ELSE 0 END) AS merchants_20plus
    FROM merchants_weekly_snapshot
    GROUP BY snapshot_week, week_start_date, week_end_date, week_label
    ORDER BY snapshot_week DESC;
    """)
    return [dict(r) for r in cursor.fetchall()]


def get_weekly_merchant_snapshots(
    conn: sqlite3.Connection,
    week: str = "latest",
    min_txns: int = 0,
    is_in_pp: Optional[bool] = None,
    change_status: Optional[str] = None,
    bank_code: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 5000
) -> List[Dict[str, Any]]:
    """Queries weekly snapshot records with optional filtering."""
    cursor = conn.cursor()

    target_week = week
    if target_week == "latest":
        cursor.execute("SELECT MAX(snapshot_week) FROM merchants_weekly_snapshot;")
        row = cursor.fetchone()
        if not row or not row[0]:
            return []
        target_week = row[0]

    conditions = ["snapshot_week = ?"]
    params = [target_week]

    if min_txns > 0:
        conditions.append("transaction_count >= ?")
        params.append(min_txns)

    if is_in_pp is not None:
        conditions.append("is_in_pp = ?")
        params.append(1 if is_in_pp else 0)

    if change_status:
        conditions.append("change_status = ?")
        params.append(change_status.upper())

    if bank_code:
        conditions.append("bank_code = ?")
        params.append(bank_code.strip())

    if search:
        search_pattern = f"%{search.strip().lower()}%"
        conditions.append("(LOWER(merchant_name) LIKE ? OR LOWER(merchant_id) LIKE ?)")
        params.extend([search_pattern, search_pattern])

    where_clause = " AND ".join(conditions)
    sql = f"""
    SELECT 
        id, snapshot_week, week_start_date, week_end_date, week_label,
        merchant_id, merchant_name, bank_code, transaction_count,
        prev_week_txns, txn_delta, growth_pct, change_status,
        latitude, longitude, is_in_pp
    FROM merchants_weekly_snapshot
    WHERE {where_clause}
    ORDER BY transaction_count DESC
    LIMIT ?;
    """
    params.append(limit)

    cursor.execute(sql, params)
    return [dict(r) for r in cursor.fetchall()]
