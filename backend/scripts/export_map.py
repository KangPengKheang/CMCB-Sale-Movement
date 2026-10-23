import sqlite3
import json
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
DEFAULT_PROD_DB = BASE_DIR / "data" / "market_reports.db"
DEFAULT_TEST_DB = BASE_DIR / "data" / "market_reports_test.db"

OUTPUT_RMS = ROOT_DIR / "khqr-map" / "src" / "data" / "rms.json"
OUTPUT_MERCHANTS = ROOT_DIR / "khqr-map" / "src" / "data" / "merchants.json"
OUTPUT_REPORTS = ROOT_DIR / "khqr-map" / "src" / "data" / "reports.json"
OUTPUT_STATS_SUMMARY = ROOT_DIR / "khqr-map" / "src" / "data" / "stats_summary.json"
OUTPUT_KHAN_STATS = ROOT_DIR / "khqr-map" / "src" / "data" / "khan_stats.json"
OUTPUT_PP_KHANS = ROOT_DIR / "khqr-map" / "src" / "data" / "boundaries" / "phnom_penh_khans.json"
KHANS_GEOJSON = BASE_DIR / "data" / "boundaries" / "phnom_penh_khans.json"


def export_data(db_path: Path):
    if not db_path.exists():
        print(f"Error: Database file does not exist: {db_path}")
        return

    OUTPUT_REPORTS.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PP_KHANS.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load PP boundaries
    pp_features = []
    if KHANS_GEOJSON.exists():
        with open(KHANS_GEOJSON, "r", encoding="utf-8") as f:
            khans_raw = json.load(f)
        pp_features = [
            f for f in khans_raw.get("features", [])
            if f["properties"].get("hrparent") == "KH12"
        ]
        pp_geojson = {"type": "FeatureCollection", "features": pp_features}
        with open(OUTPUT_PP_KHANS, "w", encoding="utf-8") as f:
            json.dump(pp_geojson, f, ensure_ascii=False)
        print(f"[+] Exported PP Khans GeoJSON: {OUTPUT_PP_KHANS.name}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 2. Query unique merchants
    cur.execute("SELECT * FROM merchants ORDER BY total_visits DESC, id ASC;")
    merchants_rows = cur.fetchall()
    merchants = []
    for m in merchants_rows:
        cur.execute(
            """
            SELECT 
                id as visit_id,
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
            ORDER BY id ASC;
            """,
            (m["id"],),
        )
        v_rows = cur.fetchall()
        visits_list = []
        for idx, vr in enumerate(v_rows, start=1):
            v_item = dict(vr)
            v_item["visit_no"] = idx
            visits_list.append(v_item)

        merchants.append({
            "id": m["id"],
            "merchant_id": m["id"],
            "canonical_name": m["canonical_name"],
            "merchant_name": m["canonical_name"],
            "business_category": m["business_category"],
            "business": m["business_category"],
            "tel": m["tel"],
            "district_khan": m["district_khan"],
            "khan_name": m["district_khan"],
            "latitude": m["latitude"],
            "longitude": m["longitude"],
            "map_url": m["map_url"],
            "total_visits": m["total_visits"] or len(visits_list) or 1,
            "first_visit_date": m["first_visit_date"],
            "latest_visit_date": m["latest_visit_date"],
            "current_status": m["current_status"],
            "status": m["current_status"],
            "current_khqr_stage": m["current_khqr_stage"],
            "khqr_stage": m["current_khqr_stage"],
            "is_onboarded": m["is_onboarded"],
            "competitor_banks": m["competitor_banks"],
            "bank": m["competitor_banks"],
            "has_aba": m["has_aba"],
            "has_acleda": m["has_acleda"],
            "has_cmcb": m["has_cmcb"],
            "has_other_bank": m["has_other_bank"],
            "assigned_reps": m["assigned_reps"],
            "sender_name": m["assigned_reps"],
            "latest_remark": m["latest_remark"],
            "remark": m["latest_remark"],
            "visits": visits_list,
        })

    with open(OUTPUT_MERCHANTS, "w", encoding="utf-8") as f:
        json.dump(merchants, f, indent=2, ensure_ascii=False)
    print(f"[+] Exported {len(merchants)} unique merchants to {OUTPUT_MERCHANTS.name}")

    # 3. Query RMs with habits and sequential visit feeds
    cur.execute("SELECT * FROM rms ORDER BY total_visits_logged DESC, id ASC;")
    rms_rows = cur.fetchall()
    rms = []
    for r in rms_rows:
        rm_id = r["id"]
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
            ORDER BY id ASC;
            """,
            (rm_id,),
        )
        rm_visits = []
        for seq_idx, v in enumerate(cur.fetchall(), start=1):
            vd = dict(v)
            vd["sequence_no"] = seq_idx
            rm_visits.append(vd)

        top_d = json.loads(r["top_districts"]) if r["top_districts"] else {}
        top_c = json.loads(r["top_categories"]) if r["top_categories"] else {}

        rms.append({
            "id": rm_id,
            "rm_id": rm_id,
            "telegram_user_id": r["telegram_user_id"],
            "canonical_name": r["canonical_name"],
            "name": r["canonical_name"],
            "username": r["username"],
            "first_active_date": r["first_active_date"],
            "latest_active_date": r["latest_active_date"],
            "total_visits_logged": r["total_visits_logged"] or len(rm_visits),
            "unique_merchants_reached": r["unique_merchants_reached"],
            "onboarded_count": r["onboarded_count"],
            "pipeline_count": r["pipeline_count"],
            "target_count": r["target_count"],
            "conversion_rate": r["conversion_rate"],
            "active_working_days": r["active_working_days"],
            "daily_visit_velocity": r["daily_visit_velocity"],
            "compliance_errors": r["compliance_errors"],
            "top_districts": top_d,
            "top_categories": top_c,
            "visits": rm_visits,
        })

    with open(OUTPUT_RMS, "w", encoding="utf-8") as f:
        json.dump(rms, f, indent=2, ensure_ascii=False)
    print(f"[+] Exported {len(rms)} RM profiles with visit trails to {OUTPUT_RMS.name}")

    # 4. Query all individual visit reports
    rows = cur.execute("SELECT * FROM merchant_reports ORDER BY report_time ASC;").fetchall()
    reports = []
    khan_counts = {f["properties"]["hrname"]: 0 for f in pp_features}

    for r in rows:
        khan_name = r["district_khan"] or "Other / Outside PP"
        if khan_name in khan_counts:
            khan_counts[khan_name] += 1

        stage = r["khqr_stage"]
        stage_labels = {
            "CONVERTED": "Signed / Deployed CMCB",
            "PIPELINE": "In Discussion / Follow-up",
            "EXISTING": "Active CMCB Merchant",
            "TARGET": "Competitor Only (Target)",
        }
        stage_label = stage_labels.get(stage, "Target")

        reports.append({
            "id": r["id"],
            "merchant_id": r["merchant_id"],
            "rm_id": r["rm_id"],
            "report_time": r["report_time"],
            "sender_id": r["sender_id"],
            "sender_name": r["sender_name"],
            "merchant_name": r["merchant_name"],
            "canonical_name": r["merchant_name"],
            "tel": r["tel_clean"] or r["tel"],
            "business": r["business_clean"] or r["business"],
            "business_category": r["business_clean"] or r["business"],
            "purpose": r["purpose"],
            "bank": r["bank"],
            "has_aba": r["has_aba"],
            "has_acleda": r["has_acleda"],
            "has_cmcb": r["has_cmcb"],
            "has_other_bank": r["has_other_bank"],
            "status": r["status_clean"] or r["status"],
            "potential_level": r["potential_level"],
            "potential_product": r["potential_product"],
            "remark": r["remark"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "map_url": r["map_url"],
            "khan_name": khan_name,
            "district_khan": khan_name,
            "photo_count": r["photo_count"],
            "khqr_stage": stage,
            "khqr_stage_label": stage_label,
            "is_onboarded": 1 if stage in ["CONVERTED", "EXISTING"] else 0,
        })

    with open(OUTPUT_REPORTS, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2, ensure_ascii=False)
    print(f"[+] Exported {len(reports)} raw visit reports to {OUTPUT_REPORTS.name}")

    # 5. Export Overall Stats Summary
    cur.execute("SELECT count(*) as total FROM merchant_reports;")
    total_visits = cur.fetchone()["total"]

    cur.execute("SELECT count(*) as total_m FROM merchants;")
    total_m = cur.fetchone()["total_m"]

    cur.execute("SELECT count(*) as total_r FROM rms;")
    total_r = cur.fetchone()["total_r"]

    cur.execute("SELECT count(*) as cnt FROM merchants WHERE is_onboarded = 1 OR current_khqr_stage IN ('CONVERTED', 'EXISTING');")
    deployed = cur.fetchone()["cnt"]

    in_progress = total_m - deployed

    active_khans = len([k for k, v in khan_counts.items() if v > 0])
    cold_khans = max(0, 14 - active_khans)

    stats_summary = {
        "total_merchants": total_m,
        "total_visits": total_visits,
        "total_rms": total_r,
        "cmcb_deployed": deployed,
        "in_pipeline": in_progress,
        "competitor_only": 0,
        "active_districts": active_khans,
        "cold_districts": cold_khans,
    }

    with open(OUTPUT_STATS_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(stats_summary, f, indent=2)
    print(f"[+] Exported stats summary to {OUTPUT_STATS_SUMMARY.name}")

    # 6. Export Khan Stats
    khan_stats_list = []
    for f in pp_features:
        name = f["properties"]["hrname"]
        code = f["properties"]["hrpcode"]
        visits = khan_counts.get(name, 0)
        khan_stats_list.append({
            "khan_name": name,
            "khan_code": code,
            "visit_count": visits,
            "is_cold_zone": (visits == 0),
        })

    khan_stats_list.sort(key=lambda x: -x["visit_count"])

    with open(OUTPUT_KHAN_STATS, "w", encoding="utf-8") as f:
        json.dump(khan_stats_list, f, indent=2, ensure_ascii=False)
    print(f"[+] Exported Khan statistics to {OUTPUT_KHAN_STATS.name}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Export SQLite reports to map JSON format.")
    parser.add_argument("--test", action="store_true", help="Export from test database (data/market_reports_test.db)")
    parser.add_argument("--prod", action="store_true", help="Export from production database (data/market_reports.db)")
    parser.add_argument("--db", type=str, default=None, help="Custom database path")
    args = parser.parse_args()

    if args.db:
        target_path = Path(args.db)
    elif args.test:
        target_path = DEFAULT_TEST_DB
    else:
        target_path = DEFAULT_PROD_DB

    export_data(target_path)


if __name__ == "__main__":
    main()
