"""ETL Pipeline Runner
Executes the full pipeline end-to-end:
Gate 1 (Validation) -> Gate 2 (Types) -> Step 3 (Cleaning) -> Step 4 (Aggregation) -> Step 5 (Deltas).
"""

from typing import Dict, Any, Tuple, Union
import io
import os
from pathlib import Path
import sqlite3
import pandas as pd

from .validator import check_essential_columns
from .typing import enforce_datatypes
from .cleaner import clean_transactions
from .aggregator import aggregate_weekly_snapshot
from .delta import enrich_with_deltas

def run_pipeline(
    source: Union[str, bytes, io.BytesIO, pd.DataFrame],
    filename: str = "upload.csv",
    db_conn: sqlite3.Connection = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Executes the entire ETL pipeline on raw transaction input.
    Supports file paths, raw bytes, file streams, or pre-loaded DataFrames.
    """
    # 1. Ingest Raw Input into DataFrame
    if isinstance(source, pd.DataFrame):
        df_raw = source.copy()
    elif isinstance(source, (str, Path)):
        src_str = str(source)
        if src_str.endswith(".xlsx") or src_str.endswith(".xls"):
            df_raw = pd.read_excel(source)
        else:
            df_raw = pd.read_csv(source)
    elif isinstance(source, (bytes, io.BytesIO)):
        bio = io.BytesIO(source) if isinstance(source, bytes) else source
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            df_raw = pd.read_excel(bio)
        else:
            df_raw = pd.read_csv(bio)
    else:
        raise ValueError("Unsupported input format for pipeline.")

    # 2. Gate 1: Essential Schema Validation
    is_valid, missing_cols = check_essential_columns(df_raw, raise_error=True)

    # 3. Gate 2: Strict Data Type Enforcement
    df_typed = enforce_datatypes(df_raw)

    # 4. Step 3: Cleaning & Filtering
    df_clean, clean_metrics = clean_transactions(df_typed)

    # 5. Step 4: Weekly Snapshot Aggregation
    df_snapshot, agg_metrics = aggregate_weekly_snapshot(df_clean)

    # 6. Step 5: Week-over-Week Delta Intelligence
    df_final, delta_metrics = enrich_with_deltas(df_snapshot, db_conn=db_conn)

    combined_metrics = {
        "filename": filename,
        "raw_rows": clean_metrics["initial_rows"],
        "duplicates_removed": clean_metrics["duplicates_removed"],
        "missing_ids_removed": clean_metrics["missing_merchant_ids_removed"],
        "clean_transactions": clean_metrics["clean_transactions"],
        "valid_gps_count": clean_metrics["valid_gps_transactions"],
        "snapshot_records": agg_metrics["snapshot_rows"],
        "unique_merchants": agg_metrics["unique_merchants"],
        "weeks_processed": agg_metrics["distinct_weeks"],
        "merchants_in_pp": agg_metrics["merchants_in_pp"],
        "target_20plus_stores": agg_metrics["merchants_20plus"],
        "change_distribution": delta_metrics
    }

    return df_final, combined_metrics
