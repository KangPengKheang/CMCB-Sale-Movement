"""Step 5: Change Intelligence Engine (Delta Tracking)
Calculates week-over-week transaction volume deltas and classifies merchants:
- NEW_POPUP: Brand new business (0 txns last week, active this week)
- SURGING: High-velocity growth (+50% or more volume)
- COOLING: Activity drop (-50% or more volume)
- STABLE: Normal steady business flow
- BASELINE: Initial week benchmark
"""

from typing import Dict, Any, Optional
import sqlite3
import numpy as np
import pandas as pd

def classify_change_status(prev: int, curr: int) -> tuple[str, float]:
    """Classifies change category and calculates growth percentage."""
    if prev == 0:
        return "NEW_POPUP", 100.0

    growth = ((curr - prev) / prev) * 100.0

    if growth >= 50.0:
        return "SURGING", round(growth, 1)
    elif growth <= -50.0:
        return "COOLING", round(growth, 1)
    return "STABLE", round(growth, 1)

def enrich_with_deltas(
    df_snapshot: pd.DataFrame,
    db_conn: Optional[sqlite3.Connection] = None
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Enriches weekly snapshot DataFrame with delta columns:
    PREV_WEEK_TXNS, TXN_DELTA, GROWTH_PCT, CHANGE_STATUS.
    If db_conn is provided, looks up previous week from `merchants_weekly_snapshot`.
    If multi-week DataFrame is passed, computes deltas across all weeks chronologically.
    """
    df = df_snapshot.copy()

    # Case 1: Multi-week DataFrame in single batch
    if df["ISO_WEEK"].nunique() > 1:
        df = df.sort_values(by=["BKG_MERCHN_ID", "ISO_WEEK"]).reset_index(drop=True)
        df["PREV_WEEK_TXNS"] = df.groupby("BKG_MERCHN_ID")["TRANSACTION_COUNT"].shift(1)
        df["TXN_DELTA"] = (df["TRANSACTION_COUNT"] - df["PREV_WEEK_TXNS"].fillna(0)).astype(int)

        first_week = df["ISO_WEEK"].min()

        def classify_multi(row):
            p, c, w = row["PREV_WEEK_TXNS"], row["TRANSACTION_COUNT"], row["ISO_WEEK"]
            if w == first_week and pd.isna(p):
                return "BASELINE", 0.0
            if pd.isna(p) or p == 0:
                return "NEW_POPUP", 100.0
            return classify_change_status(int(p), int(c))

        results = df.apply(classify_multi, axis=1)
        df["CHANGE_STATUS"] = [r[0] for r in results]
        df["GROWTH_PCT"] = [r[1] for r in results]
        df["PREV_WEEK_TXNS"] = df["PREV_WEEK_TXNS"].fillna(0).astype(int)

        status_counts = df["CHANGE_STATUS"].value_counts().to_dict()
        return df, status_counts

    # Case 2: Single-week DataFrame
    current_week = df["ISO_WEEK"].iloc[0]
    prev_week = None
    df_prev = None

    if db_conn is not None:
        try:
            cursor = db_conn.cursor()
            cursor.execute(
                "SELECT MAX(snapshot_week) FROM merchants_weekly_snapshot WHERE snapshot_week < ?",
                (current_week,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                prev_week = row[0]
                df_prev = pd.read_sql_query(
                    "SELECT merchant_id AS BKG_MERCHN_ID, transaction_count AS PREV_WEEK_TXNS "
                    "FROM merchants_weekly_snapshot WHERE snapshot_week = ?",
                    db_conn,
                    params=(prev_week,)
                )
        except Exception:
            df_prev = None

    if df_prev is not None and len(df_prev) > 0:
        merged = pd.merge(df, df_prev, on="BKG_MERCHN_ID", how="left")
        merged["PREV_WEEK_TXNS"] = merged["PREV_WEEK_TXNS"].fillna(0).astype(int)
        merged["TXN_DELTA"] = (merged["TRANSACTION_COUNT"] - merged["PREV_WEEK_TXNS"]).astype(int)

        results = merged.apply(
            lambda r: classify_change_status(int(r["PREV_WEEK_TXNS"]), int(r["TRANSACTION_COUNT"])),
            axis=1
        )
        merged["CHANGE_STATUS"] = [r[0] for r in results]
        merged["GROWTH_PCT"] = [r[1] for r in results]

        status_counts = merged["CHANGE_STATUS"].value_counts().to_dict()
        return merged, status_counts

    # Case 3: Initial Baseline run
    df["PREV_WEEK_TXNS"] = 0
    df["TXN_DELTA"] = 0
    df["GROWTH_PCT"] = 0.0
    df["CHANGE_STATUS"] = "BASELINE"

    status_counts = {"BASELINE": len(df)}
    return df, status_counts

# Alias matching notebook
compute_weekly_deltas = enrich_with_deltas
