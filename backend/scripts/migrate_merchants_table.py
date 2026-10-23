import sys
import sqlite3
import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.market_bot.core.merchant_resolver import resolve_or_create_merchant
from src.market_bot.db.models import MerchantReportRecord
from src.market_bot.db.storage import init_db, link_visit_to_merchant

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "data" / "market_reports.db"
BACKUP_DIR = BASE_DIR / "data" / "backups"


def migrate_merchants(db_path: Path):
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_file = BACKUP_DIR / f"{db_path.stem}_pre_merchant_migration.db"
    shutil.copy2(db_path, backup_file)
    print(f"[+] Safety backup created: {backup_file.name}")

    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Clear merchants table to rebuild cleanly
    cur.execute("DELETE FROM merchants;")
    cur.execute("UPDATE merchant_reports SET merchant_id = NULL;")
    conn.commit()

    visits = cur.execute("SELECT * FROM merchant_reports ORDER BY id ASC;").fetchall()
    print(f"[*] Processing {len(visits)} historical visits into unique merchants...")

    revisit_count = 0
    for row in visits:
        record = MerchantReportRecord(
            id=row["id"],
            merchant_id=None,
            report_time=row["report_time"],
            sender_id=row["sender_id"],
            sender_name=row["sender_name"],
            merchant_name=row["merchant_name"],
            tel=row["tel"],
            tel_clean=row["tel_clean"],
            business=row["business"],
            business_clean=row["business_clean"],
            purpose=row["purpose"],
            bank=row["bank"],
            has_aba=row["has_aba"],
            has_acleda=row["has_acleda"],
            has_cmcb=row["has_cmcb"],
            has_other_bank=row["has_other_bank"],
            amount=row["amount"],
            interest=row["interest"],
            loan_type=row["loan_type"],
            tenure=row["tenure"],
            maturity=row["maturity"],
            status=row["status"],
            status_clean=row["status_clean"],
            khqr_stage=row["khqr_stage"],
            potential_level=row["potential_level"],
            potential_product=row["potential_product"],
            remark=row["remark"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            district_khan=row["district_khan"],
            map_url=row["map_url"],
            location_time=row["location_time"],
            location_diff_seconds=row["location_diff_seconds"],
            form_msg_id=row["form_msg_id"],
            location_msg_id=row["location_msg_id"],
            photo_count=row["photo_count"] or 1,
            photo_msg_ids=row["photo_msg_ids"] or "[]",
            raw_text=row["raw_text"],
        )

        merchant_id = resolve_or_create_merchant(conn, record)
        link_visit_to_merchant(conn, row["id"], merchant_id)

    cur.execute("SELECT count(*) FROM merchants;")
    total_merchants = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM merchants WHERE total_visits > 1;")
    multi_visits = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM merchants WHERE is_onboarded = 1;")
    onboarded = cur.fetchone()[0]

    print("\n" + "=" * 60)
    print(" MERCHANT ENTITY AGGREGATION COMPLETE")
    print("=" * 60)
    print(f"Total Raw Visits Processed : {len(visits)}")
    print(f"Unique Merchant Entities   : {total_merchants}")
    print(f"Stores with Multiple Visits: {multi_visits} (Re-visits / Follow-ups)")
    print(f"CMCB Onboarded Merchants   : {onboarded}")
    print("=" * 60)

    print("\n--- Sample Multi-Visit Merchants ---")
    cur.execute(
        """
        SELECT id, canonical_name, district_khan, total_visits, is_onboarded, current_khqr_stage, assigned_reps
        FROM merchants
        WHERE total_visits > 1
        ORDER BY total_visits DESC
        LIMIT 6;
        """
    )
    for m in cur.fetchall():
        onboarded_str = "🟢 Onboarded" if m["is_onboarded"] else "⚪ Prospect"
        print(f"Merchant #{m['id']:03d}: {m['canonical_name']:<25} | Khan {m['district_khan']:<12} | {m['total_visits']} Visits | {onboarded_str} | Reps: {m['assigned_reps']}")

    conn.close()


if __name__ == "__main__":
    migrate_merchants(DEFAULT_DB)
