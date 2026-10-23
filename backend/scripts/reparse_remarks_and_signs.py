#!/usr/bin/env python3
"""
One-time database maintenance script to:
1. Re-extract 'Remark' from raw_text for records where RM typed 'Remarks:' (plural)
   instead of 'Remark:'.
2. Re-classify 'khqr_stage' and 'is_onboarded' for all past visits where remark
   contains 'sign', 'sign khqr', 'partnership', etc.
3. Synchronize the 'merchants' table current_status and is_onboarded flags.

Usage:
    python scripts/reparse_remarks_and_signs.py
    python scripts/reparse_remarks_and_signs.py --db /path/to/market_reports.db
"""

import sys
import re
import sqlite3
import argparse
from pathlib import Path

# Ensure market_bot package is importable
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR / "src") not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR / "src"))

from market_bot.config import Settings
from market_bot.core.parser import parse_merchant_form, classify_khqr_stage
from market_bot.core.merchant_resolver import evaluate_onboarding_status


def reparse(db_path: Path):
    if not db_path.exists():
        print(f"[!] Error: Database file not found at: {db_path}")
        sys.exit(1)

    print(f"[*] Opening database: {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id, merchant_name, raw_text, remark, status, status_clean, bank, khqr_stage FROM merchant_reports;")
    reports = cur.fetchall()
    print(f"[*] Found {len(reports)} total visit report(s) to inspect.")

    remarks_fixed = 0
    stages_fixed = 0

    for r in reports:
        rep_id = r["id"]
        raw_text = r["raw_text"] or ""
        current_remark = r["remark"] or ""
        current_stage = r["khqr_stage"] or "TARGET"
        bank = r["bank"] or ""
        status_clean = r["status_clean"] or r["status"] or ""

        new_remark = current_remark

        # 1. Re-extract remark, purpose, and loan fields using resilient parser
        if raw_text:
            parsed = parse_merchant_form(raw_text)
            if parsed.is_valid:
                if parsed.remark and (not current_remark or current_remark != parsed.remark):
                    new_remark = parsed.remark
                    remarks_fixed += 1
                    cur.execute("UPDATE merchant_reports SET remark = ? WHERE id = ?;", (new_remark, rep_id))
                    print(f"  [Remark Fixed] Report #{rep_id} '{r['merchant_name']}': '{new_remark}'")

                # Also populate purpose if empty in database
                if parsed.purpose:
                    cur.execute("UPDATE merchant_reports SET purpose = ? WHERE id = ? AND (purpose IS NULL OR purpose = '');", (parsed.purpose, rep_id))

                # Also populate amount if empty in database
                if parsed.amount and parsed.amount != "N/A":
                    cur.execute("UPDATE merchant_reports SET amount = ? WHERE id = ? AND (amount IS NULL OR amount = '' OR amount = 'N/A');", (parsed.amount, rep_id))
        # 2. Re-evaluate khqr_stage with the updated rule
        new_stage = classify_khqr_stage(status_clean, new_remark, bank)
        if new_stage != current_stage:
            stages_fixed += 1
            cur.execute("UPDATE merchant_reports SET khqr_stage = ? WHERE id = ?;", (new_stage, rep_id))
            print(f"  [Stage Fixed]  Report #{rep_id} '{r['merchant_name']}': {current_stage} ==> {new_stage} (Remark: '{new_remark}')")

    # 3. Synchronize merchants table
    merchants_fixed = 0
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='merchants';")
    if cur.fetchone():
        cur.execute("SELECT id, canonical_name, latest_remark, current_status, current_khqr_stage, is_onboarded FROM merchants;")
        merchants = cur.fetchall()
        for m in merchants:
            m_id = m["id"]
            # Get latest report for this merchant
            cur.execute("SELECT khqr_stage, remark, status_clean FROM merchant_reports WHERE merchant_id = ? ORDER BY report_time DESC, id DESC LIMIT 1;", (m_id,))
            latest_rep = cur.fetchone()

            if latest_rep:
                rep_stage = latest_rep["khqr_stage"]
                rep_remark = latest_rep["remark"]
                rep_status = latest_rep["status_clean"]

                onboarded = evaluate_onboarding_status(rep_remark, rep_status, rep_stage)
                if onboarded != m["is_onboarded"] or rep_stage != m["current_khqr_stage"]:
                    cur.execute(
                        "UPDATE merchants SET is_onboarded = ?, current_khqr_stage = ?, latest_remark = ? WHERE id = ?;",
                        (onboarded, rep_stage, rep_remark, m_id)
                    )
                    merchants_fixed += 1
                    print(f"  [Merchant Fixed] Merchant #{m_id} '{m['canonical_name']}': Onboarded={onboarded}, Stage={rep_stage}")

    # 4. Recalculate RM aggregates (onboarded_count, conversion_rate)
    rms_updated = 0
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rms';")
    if cur.fetchone():
        cur.execute("SELECT id, canonical_name FROM rms;")
        rms = cur.fetchall()
        for rm in rms:
            rm_id = rm["id"]
            cur.execute("SELECT count(*) as total FROM merchant_reports WHERE rm_id = ?;", (rm_id,))
            total_v = cur.fetchone()["total"]
            cur.execute("SELECT count(*) as onb FROM merchant_reports WHERE rm_id = ? AND khqr_stage IN ('CONVERTED', 'EXISTING');", (rm_id,))
            onboarded_v = cur.fetchone()["onb"]
            rate = round((onboarded_v / total_v) * 100, 1) if total_v > 0 else 0.0

            cur.execute(
                "UPDATE rms SET total_visits_logged = ?, onboarded_count = ?, conversion_rate = ? WHERE id = ?;",
                (total_v, onboarded_v, rate, rm_id)
            )
            rms_updated += 1
    # 5. Check Dead-Letter Queue for forms that can now be parsed with the resilient parser
    dlq_recoverable = 0
    cur.execute("SELECT * FROM dead_letter_queue WHERE message_type = 'form';")
    dlq_items = cur.fetchall()
    if dlq_items:
        print(f"\n[*] Inspecting {len(dlq_items)} Dead-Letter Queue form(s) for recovery...")
        for item in dlq_items:
            raw = item["raw_content"] or ""
            parsed = parse_merchant_form(raw)
            if parsed.is_valid:
                dlq_recoverable += 1
                print(f"  [DLQ Recovered] ID #{item['id']} '{parsed.name}' (RM: {item['sender_name']}) now parses cleanly!")

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print(f"[✓] REPARSING & SYNC COMPLETE!")
    print(f"    - Missing Remarks Restored   : {remarks_fixed}")
    print(f"    - Stages Upgraded (Signed)   : {stages_fixed}")
    print(f"    - Merchants Synchronized     : {merchants_fixed}")
    print(f"    - Sales Rep Stats Recalculated: {rms_updated}")
    print(f"    - DLQ Forms Recoverable      : {dlq_recoverable}")
    print("=" * 60)
    print("[*] All past remarks and sign/partnership statuses are now healed.")


def main():
    parser = argparse.ArgumentParser(description="Reparse remarks and upgrade sign stages for past visits.")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Custom path to SQLite database. Defaults to Settings.load().db_path",
    )
    args = parser.parse_args()

    if args.db:
        target_db = args.db
    else:
        settings = Settings.load()
        target_db = settings.db_path

    reparse(target_db)


if __name__ == "__main__":
    main()
