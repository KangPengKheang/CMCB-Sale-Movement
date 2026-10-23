import json
import math
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from ..db.models import MerchantRecord, MerchantReportRecord
from ..db.storage import get_connection, upsert_merchant

ONBOARDING_KEYWORDS = [
    "signed", "sign", "sign doc", "sign form", "sign khqr", "deployed", "deploy",
    "open account", "open khqr", "opening account", "opening acount",
    "replace new khqr", "replace khqr", "add more khqr"
]


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates approximate distance between two coordinates in meters."""
    y = (lat2 - lat1) * 111000
    x = (lon2 - lon1) * 111000 * math.cos((lat1 * math.pi) / 180)
    return math.sqrt(x * x + y * y)

def normalize_merchant_name_root(name: str) -> str:
    """
    Strips branch annotations, special characters, and lowercase for comparison.
    Example: 'Express 41 (271)' -> 'express 41'
    Example: 'Lacoste Sensok' -> 'lacoste'
    """
    n = str(name or "").strip().lower()
    # Remove branch/store notations in parentheses
    n = re.sub(r"\([^)]*\)", "", n)
    # Remove common district/location suffixes
    n = re.sub(r"\b(sensok|sen sok|ssk|wat phnom|monivong|271|cm271|fl|toul kork|tk|pct|ss)\b", "", n)
    # Remove punctuation
    n = re.sub(r"[^\w\s\u1780-\u17FF]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n if n else name.strip().lower()


def name_similarity(n1: str, n2: str) -> float:
    """Calculates Jaccard similarity over word tokens and substring check."""
    r1 = normalize_merchant_name_root(n1)
    r2 = normalize_merchant_name_root(n2)

    if not r1 or not r2:
        return 0.0
    if r1 == r2 or r1 in r2 or r2 in r1:
        return 1.0

    tokens1 = set(r1.split())
    tokens2 = set(r2.split())
    if not tokens1 or not tokens2:
        return 0.0

    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union)


def is_valid_phone(tel_clean: Optional[str]) -> bool:
    t = str(tel_clean or "").strip().upper()
    return bool(t and t not in ["N/A", "NA", "NONE", "TELEGRAM", "TG"] and len(re.sub(r"\D", "", t)) >= 8)


def evaluate_onboarding_status(remark: Optional[str], status_clean: Optional[str], khqr_stage: str) -> int:
    """Checks if RM remarks or stage indicates an onboarded/active CMCB merchant."""
    r = str(remark or "").lower()
    s = str(status_clean or "").lower()

    if khqr_stage in ["CONVERTED", "EXISTING"]:
        return 1
    if bool(re.search(r"\b(sign|signed|signing)\b", r)):
        return 1
    if any(kw in r for kw in ONBOARDING_KEYWORDS):
        return 1
    if "existing" in s:
        return 1
    return 0


def resolve_or_create_merchant(
    conn: sqlite3.Connection,
    visit: MerchantReportRecord,
) -> int:
    """
    Strict 3-tier merchant identity resolution engine:
    1. Phone match + Name compatibility.
    2. Proximity (<= 80m) + Name similarity (STRICTLY rejects different store names at same GPS).
    3. Exact root name + Same District Khan (<= 400m).
    4. Else: Creates a new merchant record.
    """
    cur = conn.cursor()

    cur.execute("SELECT * FROM merchants;")
    existing_merchants = [dict(r) for r in cur.fetchall()]

    matched_merchant: Optional[Dict[str, Any]] = None
    is_existing_link = False
    visit_phone = visit.tel_clean or visit.tel
    has_real_phone = is_valid_phone(visit_phone)
    visit_lat = visit.latitude
    visit_lng = visit.longitude
    visit_name = visit.merchant_name

    # =========================================================================
    # TIER 0: Direct Foreign Key Match (In-place edit on existing visit)
    # =========================================================================
    if visit.merchant_id is not None:
        cur.execute("SELECT * FROM merchants WHERE id = ?;", (visit.merchant_id,))
        row = cur.fetchone()
        if row:
            matched_merchant = dict(row)
            is_existing_link = True
    # =========================================================================
    # TIER 1: Phone Match + Compatible Name
    # =========================================================================
    if has_real_phone:
        for m in existing_merchants:
            if is_valid_phone(m["tel"]) and m["tel"] == visit_phone:
                dist = distance_meters(visit_lat, visit_lng, m["latitude"], m["longitude"])
                sim = name_similarity(visit_name, m["canonical_name"])
                # Require both physical proximity (<= 350m) and name compatibility
                # Distinct branches kilometers apart will remain separate merchant stores
                if dist <= 350 and sim >= 0.5:
                    matched_merchant = m
                    break

    # =========================================================================
    # TIER 2: Proximity (<= 80m) + Name Similarity (MALL RULE)
    # =========================================================================
    if not matched_merchant:
        for m in existing_merchants:
            dist = distance_meters(visit_lat, visit_lng, m["latitude"], m["longitude"])
            if dist <= 80:
                sim = name_similarity(visit_name, m["canonical_name"])
                # STRICT MALL RULE: Only merge if name similarity >= 0.65 or root names match!
                # Different store names in the same building/mall are NEVER merged.
                if sim >= 0.65:
                    matched_merchant = m
                    break

    # =========================================================================
    # TIER 3: Exact Root Name + Same District Khan (<= 400m)
    # =========================================================================
    if not matched_merchant:
        visit_root = normalize_merchant_name_root(visit_name)
        if len(visit_root) >= 3:
            for m in existing_merchants:
                if m["district_khan"] == visit.district_khan:
                    m_root = normalize_merchant_name_root(m["canonical_name"])
                    if visit_root == m_root:
                        dist = distance_meters(visit_lat, visit_lng, m["latitude"], m["longitude"])
                        if dist <= 400:
                            matched_merchant = m
                            break

    # =========================================================================
    # UPDATE OR INSERT
    # =========================================================================
    is_onboarded_visit = evaluate_onboarding_status(visit.remark, visit.status_clean, visit.khqr_stage)

    if matched_merchant:
        m_id = matched_merchant["id"]
        total_visits = matched_merchant["total_visits"] if is_existing_link else (matched_merchant["total_visits"] + 1)

        first_date = min(matched_merchant["first_visit_date"] or visit.report_time, visit.report_time)
        latest_date = max(matched_merchant["latest_visit_date"] or visit.report_time, visit.report_time)

        # Merge sales reps
        reps_set = set(r.strip() for r in matched_merchant["assigned_reps"].split(",") if r.strip())
        if visit.sender_name:
            reps_set.add(visit.sender_name.strip())
        merged_reps = ", ".join(sorted(reps_set))

        # Merge bank competitor flags (bitwise OR)
        has_aba = matched_merchant["has_aba"] | visit.has_aba
        has_acleda = matched_merchant["has_acleda"] | visit.has_acleda
        has_cmcb = matched_merchant["has_cmcb"] | visit.has_cmcb | is_onboarded_visit
        has_other = matched_merchant["has_other_bank"] | visit.has_other_bank

        is_onboarded = matched_merchant["is_onboarded"] | is_onboarded_visit

        # Lifecycle stage progression (CONVERTED takes precedence over PIPELINE)
        current_stage = matched_merchant["current_khqr_stage"]
        if is_onboarded or visit.khqr_stage in ["CONVERTED", "EXISTING"]:
            current_stage = "CONVERTED"
        elif current_stage != "CONVERTED":
            current_stage = visit.khqr_stage

        # Prefer real telephone over 'TELEGRAM' / 'N/A'
        primary_tel = matched_merchant["tel"]
        if not is_valid_phone(primary_tel) and is_valid_phone(visit_phone):
            primary_tel = visit_phone

        updated_record = MerchantRecord(
            id=m_id,
            canonical_name=visit.merchant_name if is_existing_link else matched_merchant["canonical_name"],
            business_category=matched_merchant["business_category"] or visit.business_clean,
            tel=primary_tel,
            district_khan=matched_merchant["district_khan"] or visit.district_khan,
            latitude=matched_merchant["latitude"] or visit.latitude,
            longitude=matched_merchant["longitude"] or visit.longitude,
            map_url=matched_merchant["map_url"] or visit.map_url,
            total_visits=total_visits,
            first_visit_date=first_date,
            latest_visit_date=latest_date,
            current_status=visit.status_clean or matched_merchant["current_status"],
            current_khqr_stage=current_stage,
            is_onboarded=is_onboarded,
            competitor_banks=matched_merchant["competitor_banks"] or visit.bank,
            has_aba=has_aba,
            has_acleda=has_acleda,
            has_cmcb=has_cmcb,
            has_other_bank=has_other,
            assigned_reps=merged_reps,
            latest_remark=visit.remark or matched_merchant["latest_remark"],
            created_at=matched_merchant["created_at"] or first_date,
            updated_at=latest_date,
        )

        upsert_merchant(conn, updated_record)
        return m_id

    # Create brand new merchant
    new_record = MerchantRecord(
        canonical_name=visit.merchant_name,
        business_category=visit.business_clean or "General",
        tel=visit_phone or "N/A",
        district_khan=visit.district_khan or "Other / Outside PP",
        latitude=visit.latitude,
        longitude=visit.longitude,
        map_url=visit.map_url,
        total_visits=1,
        first_visit_date=visit.report_time,
        latest_visit_date=visit.report_time,
        current_status=visit.status_clean or "OP",
        current_khqr_stage="CONVERTED" if is_onboarded_visit else visit.khqr_stage,
        is_onboarded=is_onboarded_visit,
        competitor_banks=visit.bank or "",
        has_aba=visit.has_aba,
        has_acleda=visit.has_acleda,
        has_cmcb=visit.has_cmcb | is_onboarded_visit,
        has_other_bank=visit.has_other_bank,
        assigned_reps=visit.sender_name or "",
        latest_remark=visit.remark or "",
        created_at=visit.report_time,
        updated_at=visit.report_time,
    )

    new_id = upsert_merchant(conn, new_record)
    return new_id
