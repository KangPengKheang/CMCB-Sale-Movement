"""Per-request source isolation for every visit-backed API, including derived dimensions."""
import json
from collections import defaultdict
from dataclasses import asdict

from ..config import Settings
from ..db.models import MerchantRecord, RMRecord
from ..db.storage import get_connection, recalculate_rm_aggregates
from .users_auth import normalize_identity


def _insert(conn, table, values):
    if not values:
        return
    columns = list(values[0])
    names = ",".join('"' + name + '"' for name in columns)
    conn.executemany(
        f'INSERT INTO temp."{table}" ({names}) VALUES ({",".join("?" for _ in columns)})',
        [tuple(record[column] for column in columns) for record in values],
    )


def restrict_connection(conn, allowed_sources, activity_only=False):
    """Shadow main tables on this connection only. Never copy global aggregates into a restricted response."""
    allowed = {normalize_identity(value) for value in allowed_sources}
    conn.execute("PRAGMA temp_store=MEMORY")
    if not conn.in_transaction:
        conn.execute("BEGIN")
    # Normalize distinct channel names once. Python SQLite callbacks on every row
    # contend for the GIL when several dashboard polls run concurrently.
    channels_sql = "SELECT DISTINCT source_channel FROM main.sales_submissions"
    if not activity_only:
        channels_sql += """
            UNION SELECT DISTINCT CASE WHEN json_valid(raw_content)
                THEN json_extract(raw_content,'$.source_channel') END
            FROM main.dead_letter_queue
        """
    candidates = conn.execute(channels_sql).fetchall()
    conn.execute("CREATE TEMP TABLE allowed_source_names (name PRIMARY KEY)")
    conn.executemany("INSERT OR IGNORE INTO temp.allowed_source_names VALUES (?)",
                     [(row[0],) for row in candidates
                      if normalize_identity(row[0] or "") in allowed])
    conn.execute("""CREATE TEMP TABLE sales_submissions AS SELECT * FROM main.sales_submissions
                    WHERE source_channel IN (SELECT name FROM temp.allowed_source_names)""")
    conn.execute("CREATE INDEX temp.idx_scoped_submissions ON sales_submissions(sender_id,submitted_at,id)")
    conn.execute("CREATE INDEX temp.idx_scoped_submission_date ON sales_submissions(local_date)")
    if activity_only:
        # Activity APIs need submissions only. Shadow the other visit tables as empty
        # rather than rebuilding merchant/RM aggregates on every map/feed poll.
        for table in ("merchant_reports", "dead_letter_queue", "merchants", "rms"):
            conn.execute(f"CREATE TEMP TABLE {table} AS SELECT * FROM main.{table} WHERE 0")
        conn.commit()
        conn.execute("PRAGMA query_only=ON")
        return conn
    conn.execute("CREATE TEMP TABLE merchant_reports AS SELECT * FROM main.merchant_reports WHERE id IN (SELECT id FROM temp.sales_submissions)")
    conn.execute("""CREATE TEMP TABLE dead_letter_queue AS SELECT * FROM main.dead_letter_queue
                    WHERE CASE WHEN json_valid(raw_content)
                    THEN json_extract(raw_content,'$.source_channel') IN (SELECT name FROM temp.allowed_source_names) ELSE 0 END""")
    conn.execute("CREATE INDEX temp.idx_scoped_reports_merchant ON merchant_reports(merchant_id,report_time,id)")
    conn.execute("CREATE INDEX temp.idx_scoped_reports_rm ON merchant_reports(rm_id,sender_id)")
    for table in ("merchants", "rms"):
        conn.execute(f"CREATE TEMP TABLE {table} AS SELECT * FROM main.{table} WHERE 0")
    reports = [dict(row) for row in conn.execute("SELECT * FROM merchant_reports ORDER BY report_time,id")]
    by_merchant, by_rm = defaultdict(list), defaultdict(list)
    for report in reports:
        if report["merchant_id"] is not None:
            by_merchant[report["merchant_id"]].append(report)
        if report["rm_id"] is not None:
            by_rm[report["rm_id"]].append(report)
    merchants = []
    for identity, own in by_merchant.items():
        first, last = own[0], own[-1]
        onboarded = int(any(report["khqr_stage"] in ("CONVERTED", "EXISTING") for report in own))
        merchants.append(asdict(MerchantRecord(
            id=identity, canonical_name=last["merchant_name"], business_category=last["business_clean"] or "General",
            tel=last["tel_clean"] or last["tel"] or "N/A", district_khan=last["district_khan"],
            latitude=last["latitude"], longitude=last["longitude"], map_url=last["map_url"],
            total_visits=len(own), first_visit_date=first["report_time"], latest_visit_date=last["report_time"],
            current_status=last["status_clean"] or last["status"], current_khqr_stage="CONVERTED" if onboarded else last["khqr_stage"],
            is_onboarded=onboarded, competitor_banks=", ".join(sorted({report["bank"] for report in own if report["bank"]})),
            has_aba=max(report["has_aba"] or 0 for report in own),
            has_acleda=max(report["has_acleda"] or 0 for report in own),
            has_cmcb=max(onboarded, max(report["has_cmcb"] or 0 for report in own)),
            has_other_bank=max(report["has_other_bank"] or 0 for report in own),
            assigned_reps=", ".join(sorted({report["sender_name"] for report in own})),
            latest_remark=last["remark"] or "", created_at=first["report_time"], updated_at=last["report_time"],
        )))
    _insert(conn, "merchants", merchants)
    _insert(conn, "rms", [asdict(RMRecord(
        id=identity, telegram_user_id=own[-1]["sender_id"], canonical_name=own[-1]["sender_name"],
        first_active_date=own[0]["report_time"], latest_active_date=own[-1]["report_time"],
        created_at=own[0]["report_time"], updated_at=own[-1]["report_time"],
    )) for identity, own in by_rm.items()])
    conn.commit()
    for identity in by_rm:
        recalculate_rm_aggregates(conn, identity)
    conn.execute("PRAGMA query_only=ON")
    return conn


def get_request_connection(request, activity_only=False):
    from .auth import require_admin
    settings = Settings.load()
    principal = getattr(request.state, "principal", None)
    if settings.auth_source == "users" and principal is None:
        principal = require_admin(request)
    conn = get_connection(settings.db_path)
    try:
        if principal and principal.get("allowed_sources") is not None:
            restrict_connection(conn, principal["allowed_sources"], activity_only=activity_only)
        return conn
    except Exception:
        conn.close()
        raise
