#!/usr/bin/env python3
"""
Deduplication Utility for Historical Merchant Visit Reports

Detects and cleans up accidental duplicate submissions in the database:
- Criteria: Same RM (sender_id), same merchant (name/tel), and timestamp delta <= 30 minutes (1800s).
- Action: Keeps the primary visit (earlier or more complete with location/photos),
          moves phantom duplicates to the Dead-Letter Queue (DLQ) for auditability,
          and recalculates RM lifetime performance metrics.

Usage:
    # Inspect duplicates without making changes (Dry Run):
    python scripts/deduplicate_past_reports.py --dry-run

    # Execute and permanently remove duplicates:
    python scripts/deduplicate_past_reports.py --execute

    # Target specific database:
    python scripts/deduplicate_past_reports.py --db /path/to/market_reports.db --execute
"""

import argparse
import json
import math
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure market_bot package is importable
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR / "src") not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR / "src"))

from market_bot.config import Settings
from market_bot.db.storage import (
    _haversine_distance_meters,
    _normalize_name_match,
    _to_epoch,
    recalculate_rm_aggregates,
    save_dlq_item,
)


def find_duplicate_clusters(
    conn: sqlite3.Connection,
    window_seconds: int = 1800,
) -> List[List[Dict[str, Any]]]:
    """
    Find clusters of duplicate reports in merchant_reports.
    Returns a list of clusters, where each cluster is a list of report dicts
    belonging to the same RM and merchant within <= window_seconds of each other.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM merchant_reports
        ORDER BY sender_id ASC, report_time ASC, id ASC;
        """
    )
    all_reports = [dict(r) for r in cur.fetchall()]

    # Group by sender_id
    by_sender: Dict[int, List[Dict[str, Any]]] = {}
    for r in all_reports:
        s_id = r.get("sender_id") or 0
        by_sender.setdefault(s_id, []).append(r)

    duplicate_clusters: List[List[Dict[str, Any]]] = []

    for s_id, sender_reports in by_sender.items():
        n = len(sender_reports)
        visited = set()

        for i in range(n):
            if i in visited:
                continue

            r_base = sender_reports[i]
            base_epoch = _to_epoch(r_base.get("report_time"))
            if base_epoch is None:
                continue

            cluster = [r_base]

            for j in range(i + 1, n):
                if j in visited:
                    continue

                r_cand = sender_reports[j]
                cand_epoch = _to_epoch(r_cand.get("report_time"))
                if cand_epoch is None:
                    continue

                # Reports are ordered by time, so if difference exceeds window, stop checking this base
                diff_sec = cand_epoch - base_epoch
                if diff_sec > window_seconds:
                    break

                # Match merchant
                n_match = _normalize_name_match(r_base.get("merchant_name"), r_cand.get("merchant_name"))
                t_base = re.sub(r"\D", "", r_base.get("tel_clean") or r_base.get("tel") or "")
                t_cand = re.sub(r"\D", "", r_cand.get("tel_clean") or r_cand.get("tel") or "")
                tel_match = bool(t_base and t_cand and len(t_base) >= 8 and t_base == t_cand)

                if not (n_match or tel_match):
                    continue

                # Check GPS distance if both present
                lat1, lng1 = r_base.get("latitude"), r_base.get("longitude")
                lat2, lng2 = r_cand.get("latitude"), r_cand.get("longitude")
                if lat1 is not None and lng1 is not None and lat2 is not None and lng2 is not None:
                    dist = _haversine_distance_meters(lat1, lng1, lat2, lng2)
                    if dist > 150.0:
                        continue

                cluster.append(r_cand)
                visited.add(j)

            if len(cluster) > 1:
                duplicate_clusters.append(cluster)
                visited.add(i)

    return duplicate_clusters


def pick_keeper(cluster: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Given a cluster of duplicates, choose the best record to keep:
    Priority:
    1. Has valid coordinates (latitude/longitude not None)
    2. Higher photo count
    3. Has longer remark
    4. Earlier ID (original post)
    """
    def score(r: Dict[str, Any]) -> Tuple[int, int, int, int]:
        has_coords = 1 if (r.get("latitude") and r.get("longitude")) else 0
        photos = r.get("photo_count") or 0
        remark_len = len(r.get("remark") or "")
        earlier_id = -r.get("id", 0)
        return (has_coords, photos, remark_len, earlier_id)

    sorted_cluster = sorted(cluster, key=score, reverse=True)
    keeper = sorted_cluster[0]
    purged = sorted_cluster[1:]
    return keeper, purged


def deduplicate(db_path: Path, execute: bool = False):
    if not db_path.exists():
        print(f"[!] Database file does not exist: {db_path}")
        sys.exit(1)

    print("=" * 70)
    print(f" MERCHANT REPORTS DEDUPLICATION TOOL")
    print(f" Database: {db_path}")
    print(f" Mode    : {'[EXECUTE] (Applying changes)' if execute else '[DRY-RUN] (Inspection only)'}")
    print("=" * 70)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    clusters = find_duplicate_clusters(conn, window_seconds=1800)
    print(f"\n[*] Found {len(clusters)} duplicate clusters across all visit reports.\n")

    total_purged = 0
    affected_rm_ids = set()

    for idx, cluster in enumerate(clusters, start=1):
        keeper, to_purge = pick_keeper(cluster)
        total_purged += len(to_purge)

        k_epoch = _to_epoch(keeper.get("report_time"))
        print(f"--- Cluster #{idx} (RM: {keeper.get('sender_name')} - ID #{keeper.get('sender_id')}) ---")
        print(f"  [KEEP]  Report #{keeper['id']} | Merchant: '{keeper['merchant_name']}' | Time: {keeper['report_time']} | Coords: {keeper['latitude']},{keeper['longitude']}")

        for p in to_purge:
            p_epoch = _to_epoch(p.get("report_time"))
            diff_sec = abs(k_epoch - p_epoch) if (k_epoch and p_epoch) else 0
            print(f"  [PURGE] Report #{p['id']} | Merchant: '{p['merchant_name']}' | Time: {p['report_time']} (diff: {diff_sec}s)")
            if p.get("rm_id"):
                affected_rm_ids.add(p["rm_id"])

            if execute:
                # 1. Audit trail in dead_letter_queue
                save_dlq_item(
                    conn=conn,
                    msg_id=p.get("form_msg_id") or p["id"],
                    msg_date=p.get("report_time") or "",
                    sender_id=p.get("sender_id") or 0,
                    sender_name=p.get("sender_name") or "",
                    message_type="duplicate_visit",
                    reason=f"HISTORICAL_DUPLICATE_PURGED (matches Report #{keeper['id']} '{keeper['merchant_name']}' within {diff_sec}s)",
                    raw_content=p.get("raw_text") or f"Duplicate of Report #{keeper['id']}",
                )

                # 2. Delete duplicate row from merchant_reports
                cur.execute("DELETE FROM merchant_reports WHERE id = ?;", (p["id"],))

    if execute:
        # Recalculate statistics for affected RMs
        for rm_id in affected_rm_ids:
            recalculate_rm_aggregates(conn, rm_id)

        conn.commit()
        print("\n" + "=" * 70)
        print(f"[v] DEDUPLICATION COMPLETE!")
        print(f"  - Duplicate Records Purged : {total_purged}")
        print(f"  - Audit Trail Logged in DLQ: {total_purged}")
        print(f"  - RM Lifetime Stats Healed : {len(affected_rm_ids)}")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print(f"[!] DRY-RUN SUMMARY:")
        print(f"  - Total Duplicate Clusters : {len(clusters)}")
        print(f"  - Total Reports to Purge   : {total_purged}")
        print(f"  - Affected Sales Reps (RMs): {len(affected_rm_ids)}")
        print(f"\nRun with `--execute` to apply these changes to the database.")
        print("=" * 70)

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Deduplicate historical merchant visit reports.")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Custom path to SQLite database. Defaults to Settings.load().db_path",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute deletion of duplicates. If omitted, runs in safe dry-run mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicitly run in dry-run mode (default).",
    )

    args = parser.parse_args()

    if args.db:
        target_db = args.db
    else:
        settings = Settings.load()
        target_db = settings.db_path

    deduplicate(target_db, execute=args.execute)


if __name__ == "__main__":
    main()
