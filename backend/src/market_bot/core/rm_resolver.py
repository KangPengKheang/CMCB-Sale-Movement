import re
import sqlite3
from typing import Optional
from ..db.models import RMRecord, SenderInfo
from ..db.storage import (
    get_rm_by_id,
    get_rm_by_telegram_id,
    recalculate_rm_aggregates,
    upsert_rm,
)


def clean_rm_name(raw_name: str) -> str:
    """
    Cleans and canonicalizes RM sales rep names:
    - Strips noisy bank suffixes like '(CMCB BANK)', 'CHIPMONG COMMERCIAL BANK', etc.
    - Strips inline username handles like '(@username)'
    - Normalizes case and spacing
    """
    n = str(raw_name or "").strip()
    # Remove zero-width characters
    n = re.sub(r"[\u200B-\u200D\uFEFF]", "", n)
    # Remove usernames like (@username) or @username
    n = re.sub(r"\(@[A-Za-z0-9_]+\)", "", n)
    n = re.sub(r"@[A-Za-z0-9_]+", "", n)
    # Remove bank suffixes
    n = re.sub(r"\b(CHIPMONG COMMERCIAL BANK|CHIP MONG BANK|CMCB BANK|CMCB|Chip Mong Bank)\b", "", n, flags=re.IGNORECASE)
    # Remove empty parentheses
    n = re.sub(r"\(\s*\)", "", n)
    n = re.sub(r"\s+", " ", n).strip()

    # Title case for all-caps names, while preserving specific casing conventions
    if n.isupper() and len(n) > 3:
        n = n.title()
    elif "Liza soy" in n:
        n = "Liza Soy"
    elif "Bunkhloem PEL" in n:
        n = "Bunkhloem Pel"
    elif "Sodirafi SEANG" in n:
        n = "Sodirafi Seang"
    elif "SAM OL" in n:
        n = "Sam Ol"
    elif "Pen​​​​(​ទី)" in raw_name or "Pen(ទី)" in n or "Pen (ទី)" in n:
        n = "Raty Pen (ទី)"

    return n if n else "Unknown RM"
def resolve_or_create_rm(
    conn: sqlite3.Connection,
    sender: SenderInfo,
    report_time: str,
) -> int:
    """
    Resolves an RM entity by telegram_user_id, creating or updating their profile.
    Returns the stable internal rm_id (PK).
    """
    user_id = sender.sender_id
    existing_rm = get_rm_by_telegram_id(conn, user_id)

    if existing_rm:
        rm_id = existing_rm["id"]
        latest_date = max(existing_rm["latest_active_date"] or report_time, report_time)
        first_date = min(existing_rm["first_active_date"] or report_time, report_time)

        # Update name/username if changed or improved
        raw_sender_name = sender.sender_name if sender.sender_name and sender.sender_name != "Unknown" else existing_rm["canonical_name"]
        name = clean_rm_name(raw_sender_name)
        username = sender.username or existing_rm["username"]
        if not username:
            u_match = re.search(r"@([A-Za-z0-9_]+)", sender.sender_name or "")
            if u_match:
                username = u_match.group(1)
        updated_rm = RMRecord(
            id=rm_id,
            telegram_user_id=user_id,
            canonical_name=name,
            username=username,
            first_active_date=first_date,
            latest_active_date=latest_date,
            total_visits_logged=existing_rm["total_visits_logged"],
            unique_merchants_reached=existing_rm["unique_merchants_reached"],
            onboarded_count=existing_rm["onboarded_count"],
            pipeline_count=existing_rm["pipeline_count"],
            target_count=existing_rm["target_count"],
            conversion_rate=existing_rm["conversion_rate"],
            active_working_days=existing_rm["active_working_days"],
            daily_visit_velocity=existing_rm["daily_visit_velocity"],
            top_districts=existing_rm["top_districts"],
            top_categories=existing_rm["top_categories"],
            compliance_errors=existing_rm["compliance_errors"],
            created_at=existing_rm["created_at"] or first_date,
            updated_at=latest_date,
        )

        upsert_rm(conn, updated_rm)
        return rm_id

    # Create new RM entity
    raw_name = sender.sender_name or f"User_{user_id}"
    clean_name = clean_rm_name(raw_name)
    username = sender.username
    if not username:
        u_match = re.search(r"@([A-Za-z0-9_]+)", raw_name)
        if u_match:
            username = u_match.group(1)

    new_rm = RMRecord(
        telegram_user_id=user_id,
        canonical_name=clean_name,
        username=username,
        first_active_date=report_time,
        latest_active_date=report_time,
        total_visits_logged=1,
        unique_merchants_reached=1,
        onboarded_count=0,
        pipeline_count=0,
        target_count=0,
        conversion_rate=0.0,
        active_working_days=1,
        daily_visit_velocity=1.0,
        top_districts="{}",
        top_categories="{}",
        compliance_errors=0,
        created_at=report_time,
        updated_at=report_time,
    )

    new_id = upsert_rm(conn, new_rm)
    return new_id
