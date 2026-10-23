"""Build and atomically publish a local query cache from retail_data."""
import asyncio
import hashlib
import json
import logging
import math
import re
import sqlite3
from collections import defaultdict
from dataclasses import asdict
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from ..clients.google_sheets import GoogleSheetsClient, GoogleSheetsError
from ..config import Settings
from ..db.models import MerchantRecord, MerchantReportRecord, RMRecord
from ..db.storage import (
    get_connection, init_connection, recalculate_rm_aggregates,
)
from .merchant_resolver import (
    distance_meters, evaluate_onboarding_status, is_valid_phone, normalize_merchant_name_root,
)
from .parser import (
    classify_khqr_stage, match_khan_boundary, normalize_business,
    normalize_phone, normalize_status, parse_competitor_banks, parse_merchant_form,
)
from .rm_resolver import clean_rm_name

logger = logging.getLogger(__name__)
ICT = timezone(timedelta(hours=7))
CACHE_TABLES = ("rms", "merchants", "merchant_reports", "dead_letter_queue", "sales_submissions")
CACHE_SCHEMA_VERSION = "sales-activity-v1"
REQUIRED_HEADERS = {"sender_id", "sender_name", "name", "message_date", "latitude", "longitude"}
HEADER_ALIASES = {
    "merchant_name": "name", "report_time": "message_date",
    "telegram_user_id": "sender_id", "sales_rep": "sender_name",
    "potential_h_m_l": "potential_level", "lat": "latitude", "lng": "longitude",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stable_id(value: str) -> int:
    # 52 bits: exact integers in both SQLite and JavaScript.
    return int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:7], "big") >> 4 or 1


def canonical_header(value: Any) -> str:
    name = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return HEADER_ALIASES.get(name, name)


def parse_timestamp(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        dt = None
        for date_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
            try:
                dt = datetime.strptime(value.strip(), date_format)
                break
            except (ValueError, AttributeError):
                continue
        if dt is None:
            raise ValueError("invalid_message_date")
    # The sheet's naive Message_Date values are local Cambodia time.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ICT)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BoundaryIndex:
    """Skip polygons whose bounding boxes cannot contain a visit coordinate."""
    def __init__(self, features: List[dict]):
        self.entries = []
        self.cache = {}
        for feature in features:
            geometry = feature.get("geometry", {})
            coordinates = geometry.get("coordinates", [])
            if geometry.get("type") == "Polygon":
                rings = [coordinates[0]] if coordinates else []
            elif geometry.get("type") == "MultiPolygon":
                rings = [polygon[0] for polygon in coordinates if polygon]
            else:
                continue
            points = [point for ring in rings for point in ring]
            if points:
                xs, ys = zip(*points)
                self.entries.append((min(xs), min(ys), max(xs), max(ys), feature))

    def match(self, lng: float, lat: float) -> str:
        key = (lng, lat)
        if key not in self.cache:
            candidates = [
                feature for minx, miny, maxx, maxy, feature in self.entries
                if minx <= lng <= maxx and miny <= lat <= maxy
            ]
            self.cache[key] = match_khan_boundary(lng, lat, candidates)
        return self.cache[key]


@lru_cache(maxsize=100000)
def name_parts(name: str):
    root = normalize_merchant_name_root(name)
    return root, frozenset(root.split())


def indexed_name_similarity(first: str, second: str) -> float:
    root1, tokens1 = name_parts(first)
    root2, tokens2 = name_parts(second)
    if not root1 or not root2:
        return 0.0
    if root1 == root2 or root1 in root2 or root2 in root1:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0
    return len(tokens1 & tokens2) / len(tokens1 | tokens2)


def parse_report(row: Dict[str, str], source_key: str, boundaries: BoundaryIndex) -> MerchantReportRecord:
    name = row.get("name", "").strip()
    if name.upper() in ("", "N/A", "NONE", "NULL"):
        parsed = parse_merchant_form(row.get("raw_text", ""))
        name = parsed.name.strip()
    if not name:
        raise ValueError("missing_merchant_name")
    try:
        sender_id = int(row.get("sender_id", ""))
    except ValueError:
        raise ValueError("invalid_sender_id")
    if sender_id <= 0:
        raise ValueError("invalid_sender_id")
    report_time = parse_timestamp(row.get("message_date", ""))
    try:
        lat = float(row.get("latitude", ""))
        lng = float(row.get("longitude", ""))
    except ValueError:
        raise ValueError("missing_or_invalid_gps")
    if (
        not math.isfinite(lat) or not math.isfinite(lng)
        or not -90 <= lat <= 90 or not -180 <= lng <= 180
        or (lat == 0 and lng == 0)
    ):
        raise ValueError("missing_or_invalid_gps")
    bank = row.get("bank", "")
    flags = parse_competitor_banks(bank)
    status = row.get("status") or "OP"
    status_clean = normalize_status(status)
    remark = row.get("remark", "")
    report_id = stable_id(source_key)
    return MerchantReportRecord(
        id=report_id, report_time=report_time, sender_id=sender_id,
        sender_name=clean_rm_name(row.get("sender_name") or f"User_{sender_id}"),
        merchant_name=name, tel=row.get("tel", ""),
        tel_clean=normalize_phone(row.get("tel", "")),
        business=row.get("business", ""), business_clean=normalize_business(row.get("business", "")),
        purpose=row.get("purpose") or "CMCB Products", bank=bank,
        has_aba=flags[0], has_acleda=flags[1], has_cmcb=flags[2], has_other_bank=flags[3],
        amount=row.get("amount") or "N/A", interest=row.get("interest") or "N/A",
        loan_type=row.get("loan_type") or "N/A", tenure=row.get("tenure") or "N/A",
        maturity=row.get("maturity") or "N/A", status=status, status_clean=status_clean,
        khqr_stage=classify_khqr_stage(status_clean, remark, bank),
        potential_level=row.get("potential_level") or "L",
        potential_product=row.get("potential_product") or "KHQR", remark=remark,
        latitude=lat, longitude=lng, district_khan=boundaries.match(lng, lat),
        map_url=f"https://www.google.com/maps?q={lat},{lng}", location_time=report_time,
        form_msg_id=None, location_msg_id=None,
        photo_count=int(row.get("has_image", "").strip().lower() in ("true", "1", "yes")),
        raw_text=row.get("raw_text", ""),
    )


def parse_submission(row: Dict[str, str], source_key: str):
    """A named merchant report counts as a drop even when its GPS is absent."""
    name = row.get("name", "").strip()
    if name.upper() in ("", "N/A", "NONE", "NULL"):
        name = parse_merchant_form(row.get("raw_text", "")).name.strip()
    if not name:
        raise ValueError("missing_merchant_name")
    try:
        sender_id = int(row.get("sender_id", ""))
    except ValueError:
        raise ValueError("invalid_sender_id")
    if sender_id <= 0:
        raise ValueError("invalid_sender_id")
    submitted_at = parse_timestamp(row.get("message_date", ""))
    lat = lng = None
    try:
        lat, lng = float(row.get("latitude", "")), float(row.get("longitude", ""))
        has_gps = (
            math.isfinite(lat) and math.isfinite(lng)
            and -90 <= lat <= 90 and -180 <= lng <= 180
            and (lat != 0 or lng != 0)
        )
    except ValueError:
        has_gps = False
    if not has_gps:
        lat = lng = None
    local_date = datetime.fromisoformat(submitted_at.replace("Z", "+00:00")).astimezone(ICT).date().isoformat()
    return {
        "id": stable_id(source_key), "sender_id": sender_id,
        "sender_name": clean_rm_name(row.get("sender_name") or f"User_{sender_id}"),
        "submitted_at": submitted_at, "local_date": local_date,
        "merchant_name": name, "business": row.get("business", ""),
        "remark": row.get("remark", ""), "source_channel": row.get("source_channel", ""),
        "has_gps": int(has_gps),
        "has_image": int(row.get("has_image", "").lower() in ("true", "1", "yes")),
        "latitude": lat, "longitude": lng,
    }


def insert_records(conn: sqlite3.Connection, table: str, records: List[Dict[str, Any]]) -> None:
    if not records:
        return
    columns = list(records[0])
    names = ", ".join('"' + c + '"' for c in columns)
    placeholders = ", ".join("?" for _ in columns)
    conn.executemany(
        f'INSERT INTO "{table}" ({names}) VALUES ({placeholders})',
        [tuple(row[c] for c in columns) for row in records],
    )


class MerchantIndex:
    """Spatial candidates avoid scanning all stores for each of 30,000+ visits."""
    def __init__(self):
        self.merchants: Dict[int, MerchantRecord] = {}
        self.cells = defaultdict(set)

    @staticmethod
    def cell(lat: float, lng: float):
        return (math.floor(lat * 110574 / 500), math.floor(lng * 108940 / 500))

    def resolve(self, report: MerchantReportRecord) -> int:
        cx, cy = self.cell(report.latitude, report.longitude)
        candidate_ids = set()
        # +/-2 cells also covers projection differences near the edge of Cambodia.
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                candidate_ids.update(self.cells.get((cx + dx, cy + dy), ()))
        ranked = []
        for merchant_id in sorted(candidate_ids):
            m = self.merchants[merchant_id]
            distance = distance_meters(report.latitude, report.longitude, m.latitude, m.longitude)
            if distance > 400:
                continue
            similarity = indexed_name_similarity(report.merchant_name, m.canonical_name)
            phone_match = is_valid_phone(report.tel_clean) and m.tel == report.tel_clean
            if phone_match and distance <= 350 and similarity >= 0.5:
                rank = 0
            elif distance <= 80 and similarity >= 0.65:
                rank = 1
            elif m.district_khan == report.district_khan and similarity == 1:
                rank = 2
            else:
                continue
            ranked.append((rank, distance, merchant_id))
        onboarded = evaluate_onboarding_status(report.remark, report.status_clean, report.khqr_stage)
        if ranked:
            merchant_id = min(ranked)[2]
            m = self.merchants[merchant_id]
            m.total_visits += 1
            m.latest_visit_date = report.report_time
            m.updated_at = report.report_time
            m.current_status = report.status_clean
            m.latest_remark = report.remark
            m.is_onboarded |= onboarded
            m.has_aba |= report.has_aba
            m.has_acleda |= report.has_acleda
            m.has_cmcb |= report.has_cmcb | onboarded
            m.has_other_bank |= report.has_other_bank
            m.current_khqr_stage = "CONVERTED" if m.is_onboarded else report.khqr_stage
            reps = set(m.assigned_reps.split(", "))
            reps.add(report.sender_name)
            m.assigned_reps = ", ".join(sorted(reps))
            if not is_valid_phone(m.tel) and is_valid_phone(report.tel_clean):
                m.tel = report.tel_clean
            return merchant_id
        merchant_id = stable_id("merchant:" + str(report.id))
        if merchant_id in self.merchants:
            raise GoogleSheetsError("Merchant identity collision; cache was not updated.")
        m = MerchantRecord(
            id=merchant_id, canonical_name=report.merchant_name,
            business_category=report.business_clean or "General", tel=report.tel_clean or "N/A",
            district_khan=report.district_khan, latitude=report.latitude, longitude=report.longitude,
            map_url=report.map_url, first_visit_date=report.report_time,
            latest_visit_date=report.report_time, current_status=report.status_clean,
            current_khqr_stage="CONVERTED" if onboarded else report.khqr_stage,
            is_onboarded=onboarded, competitor_banks=report.bank,
            has_aba=report.has_aba, has_acleda=report.has_acleda,
            has_cmcb=report.has_cmcb | onboarded, has_other_bank=report.has_other_bank,
            assigned_reps=report.sender_name, latest_remark=report.remark,
            created_at=report.report_time, updated_at=report.report_time,
        )
        self.merchants[merchant_id] = m
        self.cells[(cx, cy)].add(merchant_id)
        return merchant_id


def build_snapshot(values: List[List[str]], features: List[dict], namespace: str):
    if not values:
        raise GoogleSheetsError("Sheet is empty; keeping the previous cache.")
    headers = [canonical_header(h) for h in values[0]]
    missing = REQUIRED_HEADERS.difference(headers)
    if missing:
        raise GoogleSheetsError("Missing sheet columns: " + ", ".join(sorted(missing)))
    named_headers = [h for h in headers if h]
    if len(named_headers) != len(set(named_headers)):
        raise GoogleSheetsError("Duplicate sheet column names; keeping the previous cache.")
    boundaries = BoundaryIndex(features)
    submission_map = {}
    report_map = {}
    report_keys = {}
    quarantined = []
    seen = set()
    duplicate_count = 0
    for row_number, cells in enumerate(values[1:], start=2):
        if not any(str(cell).strip() for cell in cells):
            continue
        row = {
            header: str(cells[i]).strip() if i < len(cells) and cells[i] is not None else ""
            for i, header in enumerate(headers) if header
        }
        # retail_data has no row IDs: use message identity, independent of sheet ordering.
        identity = row.get("record_id") or row.get("message_id") or json.dumps(
            [row.get("source_channel"), row.get("sender_id"), row.get("message_date"), row.get("name")],
            ensure_ascii=False,
        )
        source_key = namespace + ":" + identity
        try:
            submission = parse_submission(row, source_key)
            submission_map[submission["id"]] = submission
        except ValueError:
            pass
        fingerprint = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if fingerprint in seen:
            duplicate_count += 1
            # A repeated original row can supersede an intervening corrected version.
            try:
                repeated = parse_report(row, source_key, boundaries)
                if repeated.id in report_map:
                    report_map[repeated.id] = repeated
            except ValueError:
                pass
            continue
        seen.add(fingerprint)
        try:
            report = parse_report(row, source_key, boundaries)
            if report.id in report_map:
                if report_keys[report.id] != source_key:
                    raise GoogleSheetsError("Visit identity collision; cache was not updated.")
                duplicate_count += 1
            # Later sheet rows win when the same message appears with corrected fields.
            report_map[report.id] = report
            report_keys[report.id] = source_key
        except ValueError as error:
            try:
                sender_id = int(row.get("sender_id", ""))
            except ValueError:
                sender_id = 0
            quarantined.append({
                "id": stable_id("dlq:" + namespace + ":" + fingerprint),
                "msg_id": None, "msg_date": row.get("message_date", ""),
                "sender_id": sender_id, "sender_name": row.get("sender_name", ""),
                "message_type": "google_sheet_row", "reason": str(error),
                "raw_content": json.dumps({"sheet_row": row_number, **row}, ensure_ascii=False),
            })
    reports = list(report_map.values())
    if not submission_map:
        raise GoogleSheetsError("No valid report submissions found; keeping the previous cache.")
    # Deterministic replay also handles sheet edits and deleted rows without stale aggregates.
    reports.sort(key=lambda r: (r.report_time, r.id))
    index = MerchantIndex()
    rms = {}
    for report in reports:
        rm_id = stable_id("rm:" + str(report.sender_id))
        report.rm_id = rm_id
        if rm_id not in rms:
            rms[rm_id] = RMRecord(
                id=rm_id, telegram_user_id=report.sender_id, canonical_name=report.sender_name,
                first_active_date=report.report_time, latest_active_date=report.report_time,
                created_at=report.report_time, updated_at=report.report_time,
            )
        else:
            rms[rm_id].canonical_name = report.sender_name
        report.merchant_id = index.resolve(report)
    staging = sqlite3.connect(":memory:")
    staging.row_factory = sqlite3.Row
    try:
        init_connection(staging)
        insert_records(staging, "rms", [asdict(r) for r in rms.values()])
        insert_records(staging, "merchants", [asdict(m) for m in index.merchants.values()])
        insert_records(staging, "merchant_reports", [asdict(r) for r in reports])
        insert_records(staging, "dead_letter_queue", quarantined)
        insert_records(staging, "sales_submissions", list(submission_map.values()))
        staging.commit()
        for rm_id in rms:
            recalculate_rm_aggregates(staging, rm_id)
        staging.commit()
        return staging, {
            "drops": len(submission_map), "visits": len(reports), "merchants": len(index.merchants),
            "sales_reps": len(rms), "quarantined": len(quarantined), "duplicates": duplicate_count,
        }
    except Exception:
        staging.close()
        raise


def publish_snapshot(conn: sqlite3.Connection, staging: sqlite3.Connection, digest: str, namespace: str):
    marker = conn.execute("SELECT value FROM sync_state WHERE key='visit_data_source'").fetchone()
    if marker and marker["value"] != namespace:
        raise GoogleSheetsError("This cache belongs to another sheet. Configure a separate DATABASE_PATH.")
    if not marker and conn.execute("SELECT COUNT(*) FROM merchant_reports").fetchone()[0]:
        raise GoogleSheetsError(
            "DATABASE_PATH contains existing visits. Use a separate Google Sheets cache database."
        )
    # One transaction: concurrent API readers see either the old or the complete new snapshot.
    conn.execute("BEGIN IMMEDIATE")
    try:
        for table in reversed(CACHE_TABLES):
            conn.execute(f'DELETE FROM "{table}"')
        for table in CACHE_TABLES:
            columns = [r["name"] for r in staging.execute(f'PRAGMA table_info("{table}")')]
            placeholders = ",".join("?" for _ in columns)
            names = ",".join('"' + c + '"' for c in columns)
            conn.executemany(
                f'INSERT INTO "{table}" ({names}) VALUES ({placeholders})',
                (tuple(row[c] for c in columns) for row in staging.execute(f'SELECT * FROM "{table}"')),
            )
        for key, value in (
            ("visit_data_source", namespace), ("google_sheets_digest", digest),
            ("google_sheets_last_success", utc_now()),
        ):
            conn.execute(
                "INSERT OR REPLACE INTO sync_state(key,value,updated_at) VALUES(?,?,?)",
                (key, value, utc_now()),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


class GoogleSheetsSync:
    def __init__(self, settings: Settings, features: List[dict], client=None):
        self.settings = settings
        self.features = features
        self.client = client or GoogleSheetsClient(settings)
        self.namespace = "google_sheets:" + settings.google_sheets_id + ":" + settings.google_sheets_tab
        self.status = {
            "source": "google_sheets", "sheet": settings.google_sheets_tab,
            "state": "starting", "last_attempt": None, "last_success": None, "last_checked": None,
            "refresh_seconds": settings.google_sheets_refresh_seconds, "error": None,
        }

    def refresh(self):
        self.status.update(state="refreshing", last_attempt=utc_now())
        conn = None
        staging = None
        try:
            conn = get_connection(self.settings.db_path)
            previous = dict(conn.execute("SELECT key,value FROM sync_state").fetchall())
            if previous.get("visit_data_source") == self.namespace:
                self.status["last_success"] = previous.get("google_sheets_last_success")
                for name, table in (
                    ("drops", "sales_submissions"),
                    ("visits", "merchant_reports"), ("merchants", "merchants"),
                    ("sales_reps", "rms"), ("quarantined", "dead_letter_queue"),
                ):
                    self.status[name] = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            values = self.client.fetch_values()
            digest = hashlib.sha256((CACHE_SCHEMA_VERSION + json.dumps(values, ensure_ascii=False)).encode("utf-8")).hexdigest()
            if (
                previous.get("google_sheets_digest") == digest
                and previous.get("visit_data_source") == self.namespace
                and conn.execute("SELECT COUNT(*) FROM sales_submissions").fetchone()[0] > 0
            ):
                self.status.update(
                    state="ready", error=None,
                    last_success=previous.get("google_sheets_last_success"), last_checked=utc_now(), changed=False,
                )
                return dict(self.status)
            staging, counts = build_snapshot(values, self.features, self.namespace)
            publish_snapshot(conn, staging, digest, self.namespace)
            self.status.update(state="ready", error=None, last_success=utc_now(), last_checked=utc_now(), changed=True, **counts)
            logger.info("Google Sheets cache refreshed: %s", counts)
            return dict(self.status)
        except Exception as error:
            self.status.update(
                state="error", error=str(error) if isinstance(error, GoogleSheetsError)
                else "Sheet refresh failed; keeping the previous cache.",
            )
            logger.warning("Google Sheets: %s", self.status["error"])
            return dict(self.status)
        finally:
            if staging is not None:
                staging.close()
            if conn is not None:
                conn.close()

    async def run(self):
        while True:
            await asyncio.to_thread(self.refresh)
            await asyncio.sleep(self.settings.google_sheets_refresh_seconds)

    def public_status(self, all_sources: bool):
        status = dict(self.status)
        if not all_sources:
            fields = {"source", "state", "last_attempt", "last_success", "last_checked", "refresh_seconds"}
            status = {key: value for key, value in status.items() if key in fields}
        return status
