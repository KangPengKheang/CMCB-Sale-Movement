import sys
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.market_bot.core.parser import SenderInfo
from src.market_bot.core.rm_resolver import resolve_or_create_rm
from src.market_bot.db.storage import (
    get_all_rms,
    init_db,
    link_visit_to_entities,
    recalculate_rm_aggregates,
)

DEFAULT_DB = BASE_DIR / "data" / "market_reports.db"


def migrate_rms(db_path: Path):
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return

    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Clear rms table to rebuild cleanly
    cur.execute("DELETE FROM rms;")
    cur.execute("UPDATE merchant_reports SET rm_id = NULL;")
    conn.commit()

    # Find all unique senders
    cur.execute(
        """
        SELECT 
            sender_id,
            min(sender_name) as sample_name,
            min(report_time) as first_time,
            count(*) as visit_cnt
        FROM merchant_reports
        GROUP BY sender_id
        ORDER BY visit_cnt DESC;
        """
    )
    unique_senders = cur.fetchall()
    print(f"[*] Found {len(unique_senders)} unique sales reps across historical visits.")

    for s in unique_senders:
        uid = s["sender_id"]
        name = s["sample_name"]
        first_time = s["first_time"]

        sender_info = SenderInfo(sender_id=uid, sender_name=name)
        rm_id = resolve_or_create_rm(conn, sender_info, first_time)

        # Link all visits from this sender
        cur.execute("UPDATE merchant_reports SET rm_id = ? WHERE sender_id = ?;", (rm_id, uid))
        conn.commit()

        # Recalculate full lifetime aggregates & habits
        recalculate_rm_aggregates(conn, rm_id)

    # Output Performance Leaderboard
    rms = get_all_rms(conn, sort_by="visits")

    print("\n" + "=" * 95)
    print(" RELATIONSHIP MANAGER (RM) PERFORMANCE LEADERBOARD")
    print("=" * 95)
    print(f"{'#':<3} | {'Sales Rep Name':<28} | {'Visits':<6} | {'Stores':<6} | {'Onboarded':<9} | {'Conv. Rate':<10} | {'Velocity'}")
    print("-" * 95)

    for idx, rm in enumerate(rms, start=1):
        conv_str = f"{rm['conversion_rate']:.1f}%"
        velo_str = f"{rm['daily_visit_velocity']:.1f} / day"
        print(f"{idx:02d}  | {rm['canonical_name'][:26]:<28} | {rm['total_visits_logged']:<6} | {rm['unique_merchants_reached']:<6} | {rm['onboarded_count']:<9} | {conv_str:<10} | {velo_str}")

    conn.close()


if __name__ == "__main__":
    migrate_rms(DEFAULT_DB)
