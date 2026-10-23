"""Step 3: Transaction Cleaning & Filtering
Deduplicates transactions, drops invalid/blank merchant IDs, and flags Cambodia coordinates.
"""

from typing import Tuple, Dict, Any
import numpy as np
import pandas as pd

def clean_transactions(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Cleans raw transactions:
    1. Deduplicates on TRANSACTION_ID
    2. Drops missing or blank BKG_MERCHN_ID
    3. Flags valid Cambodia coordinates (Lat: 9.5-15.0, Lon: 102.0-108.0, non-zero)
    Returns: (cleaned_df, audit_metrics_dict)
    """
    df = df.copy()
    total_initial = len(df)

    # 1. Deduplication on TRANSACTION_ID
    df = df.drop_duplicates(subset=["TRANSACTION_ID"], keep="first")
    duplicates_removed = total_initial - len(df)

    # 2. Drop Missing or Blank Merchant Identifiers
    before_null_id = len(df)
    valid_merchant_mask = (
        df["BKG_MERCHN_ID"].notna()
        & (df["BKG_MERCHN_ID"].astype(str).str.strip() != "")
        & (~df["BKG_MERCHN_ID"].astype(str).str.lower().isin(["none", "nan", "null"]))
    )
    df = df[valid_merchant_mask]
    missing_ids_removed = before_null_id - len(df)

    # 3. GPS Coordinate Validation (Cambodia Bounding Envelope)
    # Latitude: 9.5 to 15.0, Longitude: 102.0 to 108.0
    valid_gps_mask = (
        df["LATITUDE"].notna()
        & df["LONGITUDE"].notna()
        & (df["LATITUDE"] >= 9.5)
        & (df["LATITUDE"] <= 15.0)
        & (df["LONGITUDE"] >= 102.0)
        & (df["LONGITUDE"] <= 108.0)
        & ~((df["LATITUDE"] == 0.0) & (df["LONGITUDE"] == 0.0))
    )
    df["VALID_GPS"] = valid_gps_mask

    valid_gps_count = int(df["VALID_GPS"].sum())
    invalid_gps_count = int(len(df) - valid_gps_count)

    audit_metrics = {
        "initial_rows": total_initial,
        "duplicates_removed": duplicates_removed,
        "missing_merchant_ids_removed": missing_ids_removed,
        "clean_transactions": len(df),
        "valid_gps_transactions": valid_gps_count,
        "missing_gps_transactions": invalid_gps_count,
        "unique_merchants": int(df["BKG_MERCHN_ID"].nunique())
    }

    return df, audit_metrics
