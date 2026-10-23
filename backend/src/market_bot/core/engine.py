import json
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional
from ..db.models import MerchantReportRecord, ParsedForm, ParsedLocation, SenderInfo
from ..db.storage import (
    delete_pending_event,
    find_matching_pending_event,
    find_pending_duplicate_form,
    find_recent_duplicate_report,
    recalculate_rm_aggregates,
    save_dlq_item,
    save_pending_event,
    upsert_merchant_report,
)
from .merchant_resolver import resolve_or_create_merchant
from .parser import (
    extract_sender_info,
    match_khan_boundary,
    parse_location,
    parse_merchant_form,
)
from .rm_resolver import resolve_or_create_rm

logger = logging.getLogger("market_bot.core.engine")


def process_update(
    conn: sqlite3.Connection,
    update: Dict[str, Any],
    pp_features: List[Dict[str, Any]],
    correlation_window_seconds: int = 900,
) -> Optional[MerchantReportRecord]:
    """
    Core state machine: processes a single Telegram update dict.
    Correlates photo/caption forms with GPS location pins asynchronously,
    handles in-place edits, and updates merchant & RM entity tables.
    """
    is_edit = "edited_message" in update
    msg = update.get("edited_message") if is_edit else update.get("message")

    if not msg or not isinstance(msg, dict):
        return None

    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id:
        return None

    message_id = msg.get("message_id")
    msg_date = msg.get("date", int(time.time()))
    iso_date = msg.get("date_iso") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(msg_date))
    grouped_id = msg.get("media_group_id")

    sender = extract_sender_info(msg)

    # 1. Check for location pin
    parsed_loc = parse_location(msg)
    if parsed_loc:
        return _handle_location_event(
            conn=conn,
            chat_id=chat_id,
            sender=sender,
            loc=parsed_loc,
            pp_features=pp_features,
            is_edit=is_edit,
            window_seconds=correlation_window_seconds,
        )

    # 2. Check for merchant visit form (caption or text)
    caption_text = msg.get("caption") or msg.get("text") or ""
    parsed_form = parse_merchant_form(caption_text)

    if parsed_form.is_valid:
        return _handle_form_event(
            conn=conn,
            chat_id=chat_id,
            message_id=message_id,
            msg_date=msg_date,
            iso_date=iso_date,
            grouped_id=grouped_id,
            sender=sender,
            form=parsed_form,
            pp_features=pp_features,
            is_edit=is_edit,
            window_seconds=correlation_window_seconds,
        )

    # 3. Check for supporting album photos or non-form media
    has_photo = bool(msg.get("photo") or msg.get("document"))
    if has_photo:
        save_pending_event(
            conn=conn,
            event_type="photo",
            chat_id=chat_id,
            message_id=message_id,
            sender_id=sender.sender_id,
            sender_name=sender.sender_name,
            msg_date=msg_date,
            iso_date=iso_date,
            grouped_id=grouped_id,
            payload={"caption": caption_text},
        )
        return None

    # 4. Otherwise: chatter or service event
    if caption_text.strip():
        save_dlq_item(
            conn=conn,
            msg_id=message_id,
            msg_date=iso_date,
            sender_id=sender.sender_id,
            sender_name=sender.sender_name,
            message_type="chatter",
            reason="Text message does not match 14-field merchant form template",
            raw_content=caption_text,
        )

    return None


def _handle_form_event(
    conn: sqlite3.Connection,
    chat_id: int,
    message_id: int,
    msg_date: int,
    iso_date: str,
    grouped_id: Optional[int],
    sender: SenderInfo,
    form: ParsedForm,
    pp_features: List[Dict[str, Any]],
    is_edit: bool = False,
    window_seconds: int = 900,
) -> Optional[MerchantReportRecord]:
    cur = conn.cursor()

    # =========================================================================
    # IN-PLACE EDIT: Check if this form_msg_id already exists in merchant_reports
    # =========================================================================
    cur.execute("SELECT * FROM merchant_reports WHERE form_msg_id = ?", (message_id,))
    existing_row = cur.fetchone()

    if existing_row:
        lat = existing_row["latitude"]
        lng = existing_row["longitude"]
        khan = match_khan_boundary(lng, lat, pp_features)

        # Resolve RM entity
        rm_id = resolve_or_create_rm(conn, sender, existing_row["report_time"])

        report = MerchantReportRecord(
            id=existing_row["id"],
            merchant_id=existing_row["merchant_id"],
            rm_id=rm_id,
            report_time=existing_row["report_time"],
            sender_id=sender.sender_id,
            sender_name=sender.sender_name,
            merchant_name=form.name,
            tel=form.tel,
            tel_clean=form.tel_clean,
            business=form.business,
            business_clean=form.business_clean,
            purpose=form.purpose,
            bank=form.bank,
            has_aba=form.has_aba,
            has_acleda=form.has_acleda,
            has_cmcb=form.has_cmcb,
            has_other_bank=form.has_other_bank,
            amount=form.amount,
            interest=form.interest,
            loan_type=form.loan_type,
            tenure=form.tenure,
            maturity=form.maturity,
            status=form.status,
            status_clean=form.status_clean,
            khqr_stage=form.khqr_stage,
            potential_level=form.potential_level,
            potential_product=form.potential_product,
            remark=form.remark,
            latitude=lat,
            longitude=lng,
            district_khan=khan,
            map_url=existing_row["map_url"],
            location_time=existing_row["location_time"],
            location_diff_seconds=existing_row["location_diff_seconds"],
            form_msg_id=message_id,
            location_msg_id=existing_row["location_msg_id"],
            photo_count=existing_row["photo_count"] or 1,
            photo_msg_ids=existing_row["photo_msg_ids"] or json.dumps([message_id]),
            raw_text=form.raw_text,
        )

        merchant_id = resolve_or_create_merchant(conn, report)
        report.merchant_id = merchant_id
        upsert_merchant_report(conn, report)
        recalculate_rm_aggregates(conn, rm_id)

        logger.info(f"In-Place Edit Applied: Form #{message_id} updated to '{form.name}' (Merchant #{merchant_id}, RM #{rm_id})")
        return report

    # =========================================================================
    # DUPLICATE PREVENTION: Check if this RM already submitted this visit (<= 30 min)
    # =========================================================================
    dup_report = find_recent_duplicate_report(
        conn=conn,
        sender_id=sender.sender_id,
        merchant_name=form.name,
        target_time=msg_date,
        window_seconds=1800,
        tel=form.tel,
    )
    if dup_report:
        logger.warning(
            f"Duplicate Form rejected: RM #{sender.sender_id} ({sender.sender_name}) already logged Visit #{dup_report['id']} for '{dup_report['merchant_name']}' within 30 min"
        )
        # Clean up any pending location from this sender that might have paired with this duplicate
        pending_loc = find_matching_pending_event(
            conn=conn,
            target_event_type="location",
            sender_id=sender.sender_id,
            current_date=msg_date,
            window_seconds=window_seconds,
        )
        if pending_loc:
            delete_pending_event(conn, pending_loc["message_id"])

        save_dlq_item(
            conn=conn,
            msg_id=message_id,
            msg_date=iso_date,
            sender_id=sender.sender_id,
            sender_name=sender.sender_name,
            message_type="form",
            reason=f"DUPLICATE_SUBMISSION (matches Visit #{dup_report['id']} '{dup_report['merchant_name']}' within 30 min)",
            raw_content=form.raw_text,
        )
        return None

    dup_pending = find_pending_duplicate_form(
        conn=conn,
        sender_id=sender.sender_id,
        merchant_name=form.name,
        target_time=msg_date,
        window_seconds=1800,
        tel=form.tel,
    )
    if dup_pending:
        logger.warning(
            f"Duplicate Form rejected: RM #{sender.sender_id} already has Pending Form #{dup_pending['message_id']} for '{form.name}' within 30 min"
        )
        save_dlq_item(
            conn=conn,
            msg_id=message_id,
            msg_date=iso_date,
            sender_id=sender.sender_id,
            sender_name=sender.sender_name,
            message_type="form",
            reason=f"DUPLICATE_SUBMISSION (matches Pending Form #{dup_pending['message_id']} within 30 min)",
            raw_content=form.raw_text,
        )
        return None

    # =========================================================================
    # NEW PAIRING: Look for matching pending location from the same sender
    # =========================================================================
    pending_loc = find_matching_pending_event(
        conn=conn,
        target_event_type="location",
        sender_id=sender.sender_id,
        current_date=msg_date,
        window_seconds=window_seconds,
    )

    if pending_loc:
        loc_payload = json.loads(pending_loc["payload_json"])
        lat = loc_payload["latitude"]
        lng = loc_payload["longitude"]
        loc_time = loc_payload["iso_date"]
        diff_sec = abs(msg_date - pending_loc["msg_date"])

        khan = match_khan_boundary(lng, lat, pp_features)
        map_url = f"https://www.google.com/maps?q={lat},{lng}"

        # Resolve RM entity
        rm_id = resolve_or_create_rm(conn, sender, iso_date)

        report = MerchantReportRecord(
            report_time=iso_date,
            sender_id=sender.sender_id,
            sender_name=sender.sender_name,
            rm_id=rm_id,
            merchant_name=form.name,
            tel=form.tel,
            tel_clean=form.tel_clean,
            business=form.business,
            business_clean=form.business_clean,
            purpose=form.purpose,
            bank=form.bank,
            has_aba=form.has_aba,
            has_acleda=form.has_acleda,
            has_cmcb=form.has_cmcb,
            has_other_bank=form.has_other_bank,
            amount=form.amount,
            interest=form.interest,
            loan_type=form.loan_type,
            tenure=form.tenure,
            maturity=form.maturity,
            status=form.status,
            status_clean=form.status_clean,
            khqr_stage=form.khqr_stage,
            potential_level=form.potential_level,
            potential_product=form.potential_product,
            remark=form.remark,
            latitude=lat,
            longitude=lng,
            district_khan=khan,
            map_url=map_url,
            location_time=loc_time,
            location_diff_seconds=diff_sec,
            form_msg_id=message_id,
            location_msg_id=pending_loc["message_id"],
            photo_count=1,
            photo_msg_ids=json.dumps([message_id]),
            raw_text=form.raw_text,
        )

        merchant_id = resolve_or_create_merchant(conn, report)
        report.merchant_id = merchant_id

        upsert_merchant_report(conn, report)
        recalculate_rm_aggregates(conn, rm_id)
        delete_pending_event(conn, pending_loc["message_id"])

        logger.info(f"Correlated Form #{message_id} with Location #{pending_loc['message_id']} -> Merchant #{merchant_id} ({form.name}), RM #{rm_id}")
        return report

    save_pending_event(
        conn=conn,
        event_type="form",
        chat_id=chat_id,
        message_id=message_id,
        sender_id=sender.sender_id,
        sender_name=sender.sender_name,
        msg_date=msg_date,
        iso_date=iso_date,
        grouped_id=grouped_id,
        payload={
            "form": {
                "name": form.name,
                "tel": form.tel,
                "tel_clean": form.tel_clean,
                "business": form.business,
                "business_clean": form.business_clean,
                "purpose": form.purpose,
                "bank": form.bank,
                "has_aba": form.has_aba,
                "has_acleda": form.has_acleda,
                "has_cmcb": form.has_cmcb,
                "has_other_bank": form.has_other_bank,
                "amount": form.amount,
                "interest": form.interest,
                "loan_type": form.loan_type,
                "tenure": form.tenure,
                "maturity": form.maturity,
                "status": form.status,
                "status_clean": form.status_clean,
                "khqr_stage": form.khqr_stage,
                "potential_level": form.potential_level,
                "potential_product": form.potential_product,
                "remark": form.remark,
                "raw_text": form.raw_text,
            }
        },
    )
    logger.info(f"Buffered Form #{message_id} ({form.name}). Waiting for GPS location pin...")
    return None


def _handle_location_event(
    conn: sqlite3.Connection,
    chat_id: int,
    sender: SenderInfo,
    loc: ParsedLocation,
    pp_features: List[Dict[str, Any]],
    is_edit: bool = False,
    window_seconds: int = 900,
) -> Optional[MerchantReportRecord]:
    cur = conn.cursor()

    # =========================================================================
    # IN-PLACE EDIT: Check if this location_msg_id already exists in merchant_reports
    # =========================================================================
    cur.execute("SELECT * FROM merchant_reports WHERE location_msg_id = ?", (loc.msg_id,))
    existing_loc_row = cur.fetchone()

    if existing_loc_row:
        lat = loc.latitude
        lng = loc.longitude
        khan = match_khan_boundary(lng, lat, pp_features)
        map_url = f"https://www.google.com/maps?q={lat},{lng}"

        cur.execute(
            """
            UPDATE merchant_reports SET
                latitude = ?,
                longitude = ?,
                district_khan = ?,
                map_url = ?,
                location_time = ?
            WHERE id = ?
            """,
            (lat, lng, khan, map_url, loc.iso_date, existing_loc_row["id"]),
        )
        conn.commit()
        logger.info(f"In-Place Edit Applied: Location #{loc.msg_id} coordinates updated for Visit #{existing_loc_row['id']}")
        return None

    # =========================================================================
    # NEW PAIRING: Look for matching pending form from the same sender
    # =========================================================================
    pending_form = find_matching_pending_event(
        conn=conn,
        target_event_type="form",
        sender_id=sender.sender_id,
        current_date=loc.msg_date,
        window_seconds=window_seconds,
    )

    if pending_form:
        form_payload = json.loads(pending_form["payload_json"])["form"]
        # Guard: Check if a report for this merchant from this RM was already finalized within 30 min
        dup_report = find_recent_duplicate_report(
            conn=conn,
            sender_id=sender.sender_id,
            merchant_name=form_payload.get("name"),
            target_time=loc.msg_date,
            window_seconds=1800,
            tel=form_payload.get("tel"),
            lat=loc.latitude,
            lng=loc.longitude,
        )
        if dup_report:
            logger.warning(
                f"Duplicate Location pairing rejected: RM #{sender.sender_id} already logged Visit #{dup_report['id']} for '{dup_report['merchant_name']}' within 30 min"
            )
            delete_pending_event(conn, pending_form["message_id"])
            save_dlq_item(
                conn=conn,
                msg_id=loc.msg_id,
                msg_date=loc.iso_date,
                sender_id=sender.sender_id,
                sender_name=sender.sender_name,
                message_type="location",
                reason=f"DUPLICATE_SUBMISSION (matches Visit #{dup_report['id']} '{dup_report['merchant_name']}' within 30 min)",
                raw_content=f"Location: {loc.latitude}, {loc.longitude}",
            )
            return None

        lat = loc.latitude
        lng = loc.longitude
        diff_sec = abs(loc.msg_date - pending_form["msg_date"])

        khan = match_khan_boundary(lng, lat, pp_features)
        map_url = f"https://www.google.com/maps?q={lat},{lng}"

        # Resolve RM entity
        rm_id = resolve_or_create_rm(conn, sender, pending_form["iso_date"])

        report = MerchantReportRecord(
            report_time=pending_form["iso_date"],
            sender_id=sender.sender_id,
            sender_name=sender.sender_name,
            rm_id=rm_id,
            merchant_name=form_payload["name"],
            tel=form_payload["tel"],
            tel_clean=form_payload["tel_clean"],
            business=form_payload["business"],
            business_clean=form_payload["business_clean"],
            purpose=form_payload["purpose"],
            bank=form_payload["bank"],
            has_aba=form_payload["has_aba"],
            has_acleda=form_payload["has_acleda"],
            has_cmcb=form_payload["has_cmcb"],
            has_other_bank=form_payload["has_other_bank"],
            amount=form_payload["amount"],
            interest=form_payload["interest"],
            loan_type=form_payload["loan_type"],
            tenure=form_payload["tenure"],
            maturity=form_payload["maturity"],
            status=form_payload["status"],
            status_clean=form_payload["status_clean"],
            khqr_stage=form_payload["khqr_stage"],
            potential_level=form_payload["potential_level"],
            potential_product=form_payload["potential_product"],
            remark=form_payload["remark"],
            latitude=lat,
            longitude=lng,
            district_khan=khan,
            map_url=map_url,
            location_time=loc.iso_date,
            location_diff_seconds=diff_sec,
            form_msg_id=pending_form["message_id"],
            location_msg_id=loc.msg_id,
            photo_count=1,
            photo_msg_ids=json.dumps([pending_form["message_id"]]),
            raw_text=form_payload["raw_text"],
        )

        merchant_id = resolve_or_create_merchant(conn, report)
        report.merchant_id = merchant_id

        upsert_merchant_report(conn, report)
        recalculate_rm_aggregates(conn, rm_id)
        delete_pending_event(conn, pending_form["message_id"])

        logger.info(f"Correlated Location #{loc.msg_id} with Form #{pending_form['message_id']} -> Merchant #{merchant_id} ({form_payload['name']}), RM #{rm_id}")
        return report

    save_pending_event(
        conn=conn,
        event_type="location",
        chat_id=chat_id,
        message_id=loc.msg_id,
        sender_id=sender.sender_id,
        sender_name=sender.sender_name,
        msg_date=loc.msg_date,
        iso_date=loc.iso_date,
        grouped_id=None,
        payload={
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "iso_date": loc.iso_date,
        },
    )
    logger.info(f"Buffered Location #{loc.msg_id} ({loc.latitude:.5f}, {loc.longitude:.5f}). Waiting for form...")
    return None
