import sqlite3
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROD_DB = BASE_DIR / "data" / "market_reports.db"
DEFAULT_TEST_DB = BASE_DIR / "data" / "market_reports_test.db"


def inspect(db_path: Path, show_dlq: bool = False, limit: int = 10):
    if not db_path.exists():
        print(f"Error: Database file does not exist: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT count(*) as cnt FROM merchant_reports;")
    rep_count = cur.fetchone()["cnt"]

    cur.execute("SELECT count(*) as cnt FROM dead_letter_queue;")
    dlq_count = cur.fetchone()["cnt"]

    cur.execute("SELECT sum(photo_count) as total_photos, avg(photo_count) as avg_photos FROM merchant_reports;")
    photo_row = cur.fetchone()
    total_photos = photo_row["total_photos"] or 0
    avg_photos = photo_row["avg_photos"] or 1.0

    print("=" * 70)
    print(f" MARKET IMPROVEMENT DATABASE: {db_path.name}")
    print("=" * 70)
    print(f"Full Path                         : {db_path}")
    print(f"Valid Merchant Reports (with GPS) : {rep_count}")
    print(f"Total Photos Linked               : {total_photos} (avg {avg_photos:.1f} per visit)")
    print(f"Dead-Letter Queue (Real Errors)   : {dlq_count}")
    print("=" * 70)

    if rep_count > 0:
        # Top Business Types
        print("\n--- Top Merchant Business Types ---")
        cur.execute(
            """
            SELECT business_clean, count(*) as cnt 
            FROM merchant_reports 
            GROUP BY business_clean 
            ORDER BY cnt DESC 
            LIMIT 8;
            """
        )
        for r in cur.fetchall():
            print(f"  {r['business_clean']:<25} : {r['cnt']} visits")

        # KHQR Stage Breakdown
        print("\n--- KHQR Acquisition Stage Breakdown ---")
        cur.execute(
            """
            SELECT khqr_stage, count(*) as cnt 
            FROM merchant_reports 
            GROUP BY khqr_stage 
            ORDER BY cnt DESC;
            """
        )
        for r in cur.fetchall():
            print(f"  {r['khqr_stage']:<25} : {r['cnt']}")

        # Sample Reports
        print("\n" + "=" * 95)
        print(f" RECENT VALID MERCHANT REPORTS (Showing first {limit})")
        print("=" * 95)
        cur.execute(
            f"""
            SELECT id, report_time, sender_name, merchant_name, business_clean, tel_clean,
                   khqr_stage, district_khan, photo_count, latitude, longitude, map_url
            FROM merchant_reports
            ORDER BY id DESC
            LIMIT {limit};
            """
        )
        for r in cur.fetchall():
            khan = r['district_khan'] or 'Unknown'
            print(f"[{r['id']:02d}] {r['report_time'][11:19]} | {r['sender_name'][:18]:<18} | {r['merchant_name']:<25} | Khan {khan:<12} | Photos: {r['photo_count']}")
            print(f"     Stage: {r['khqr_stage']:<10} | Category: {r['business_clean']:<16} | Tel: {r['tel_clean']}")
            print(f"     Map: {r['map_url']}")

    if dlq_count > 0:
        print("\n--- Dead-Letter Queue (Real Errors / Anomalies) ---")
        cur.execute(
            """
            SELECT message_type, count(*) as cnt, reason
            FROM dead_letter_queue 
            GROUP BY message_type 
            ORDER BY cnt DESC;
            """
        )
        for r in cur.fetchall():
            print(f"  {r['message_type']:<25} : {r['cnt']} | Reason: {r['reason']}")

        if show_dlq:
            print("\n" + "=" * 95)
            print(" DEAD-LETTER QUEUE ENTRIES (All Items)")
            print("=" * 95)
            cur.execute("SELECT * FROM dead_letter_queue ORDER BY id ASC;")
            for r in cur.fetchall():
                print(f"DLQ #{r['id']} | MsgID: {r['msg_id']} | Type: {r['message_type']} | Sender: {r['sender_name']}")
                print(f"  Reason : {r['reason']}")
                print(f"  Snippet: {(r['raw_content'] or '')[:75]}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Inspect market_reports SQLite databases.")
    parser.add_argument("--test", action="store_true", help="Inspect test database (data/market_reports_test.db)")
    parser.add_argument("--prod", action="store_true", help="Inspect production database (data/market_reports.db)")
    parser.add_argument("--db", type=str, default=None, help="Custom database path")
    parser.add_argument("--dlq", action="store_true", help="Print all DLQ entries")
    parser.add_argument("--limit", type=int, default=10, help="Number of reports to display (default: 10)")
    args = parser.parse_args()

    if args.db:
        target_path = Path(args.db)
    elif args.test:
        target_path = DEFAULT_TEST_DB
    else:
        target_path = DEFAULT_PROD_DB

    inspect(target_path, show_dlq=args.dlq, limit=args.limit)


if __name__ == "__main__":
    main()
