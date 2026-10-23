"""Gate 2: Strict Data Type Enforcement
Casts raw transaction columns to strictly enforced banking data types.
Handles Oracle timestamps, 2-digit years, and leading zeros on IDs.
"""

import numpy as np
import pandas as pd

def enforce_datatypes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assumes check_essential_columns(df) has already verified column presence.
    Directly casts all columns to target types without redundant checks.
    """
    df = df.copy()

    # 1. Text & Identifiers (Preserve leading zeros, strip whitespace)
    text_cols = [
        "TRANSACTION_ID",
        "USER_ID",
        "BS_NAME",
        "ACCOUNT_NO",
        "ACCOUNT_NAME",
        "BENEFICIARY_ACCOUNT",
        "BENEFICIARY_NAME1",
        "BENEFICIARY_BANK_CODE",
        "BKG_MERCHN_ID",
        "BKG_MERCHN_NAME",
        "TRANSACTION_CURRENCY_CODE",
        "NARRATIVE"
    ]
    for col in text_cols:
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .replace(["nan", "None", "NULL", "<NA>", ""], np.nan)
        )

    # 2. Coordinates & Amounts (Force float, invalid strings become NaN)
    num_cols = ["TRANSACTION_AMT", "LATITUDE", "LONGITUDE"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 3. Oracle System Timestamp (e.g. '16-SEP-26 10.39.27.000000 AM')
    df["CURRENT_SYS_TIME"] = pd.to_datetime(
        df["CURRENT_SYS_TIME"].astype(str).str.strip(),
        format="%d-%b-%y %I.%M.%S.%f %p",
        errors="coerce"
    )

    # 4. Clean Date & Time Strings (Handles both 20260916 & 2026-09-16 formats)
    clean_date = df["TRANSACTION_DATE"].astype(str).str.split(".").str[0].str.strip().str.replace("-", "").str.replace("/", "")
    clean_time = df["TRANSACTION_TIME"].astype(str).str.split(".").str[0].str.strip().str.replace(":", "").str.zfill(6)

    # 5. Combined Datetime (e.g. '20260916' + '093927' -> 2026-09-16 09:39:27)
    df["TRANSACTION_DATETIME"] = pd.to_datetime(
        clean_date + clean_time,
        format="%Y%m%d%H%M%S",
        errors="coerce"
    )
    if df["TRANSACTION_DATETIME"].isna().any():
        fallback_dt = pd.to_datetime(df["CURRENT_SYS_TIME"], errors="coerce")
        df["TRANSACTION_DATETIME"] = df["TRANSACTION_DATETIME"].fillna(fallback_dt)
    # 6. Extract clean Date and Time components
    df["TRANSACTION_DATE"] = df["TRANSACTION_DATETIME"].dt.date
    df["TRANSACTION_TIME"] = df["TRANSACTION_DATETIME"].dt.time

    return df
