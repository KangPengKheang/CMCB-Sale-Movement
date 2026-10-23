"""Gate 1: Schema & Essential Column Validator
Verifies raw transaction file integrity before any processing.
"""

from typing import List, Tuple
import pandas as pd

ESSENTIAL_COLUMNS = [
    "CURRENT_SYS_TIME",
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
    "TRANSACTION_AMT",
    "TRANSACTION_CURRENCY_CODE",
    "TRANSACTION_DATE",
    "NARRATIVE",
    "TRANSACTION_TIME",
    "LATITUDE",
    "LONGITUDE"
]

def check_essential_columns(df: pd.DataFrame, raise_error: bool = True) -> Tuple[bool, List[str]]:
    """
    Validates that all essential columns exist in the DataFrame.
    Normalizes column headers (strips spaces, forces uppercase) to prevent false rejections.
    """
    if df is None or len(df) == 0:
        msg = "Uploaded dataset is completely empty (0 rows)."
        if raise_error:
            raise ValueError(msg)
        return False, ["EMPTY_DATASET"]

    df_cols = {col.strip().upper() for col in df.columns}
    req_cols = {col.strip().upper() for col in ESSENTIAL_COLUMNS}
    missing = sorted(list(req_cols - df_cols))

    if missing:
        msg = f"Dataset is missing essential columns ({len(missing)}): {missing}"
        if raise_error:
            raise ValueError(msg)
        return False, missing

    return True, []

# Alias matching notebook
check_essential_column = check_essential_columns
