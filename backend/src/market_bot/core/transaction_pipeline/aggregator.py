"""Step 4: Weekly Snapshot Aggregation
Aggregates clean transactions into the Periodic Snapshot table.
Grain: 1 row = 1 Merchant per Calendar Week.
"""

from typing import Dict, Any, Tuple
import collections
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

def is_in_phnom_penh(lat: float, lon: float) -> bool:
    """Evaluates whether coordinates fall inside the Phnom Penh urban envelope."""
    if pd.isna(lat) or pd.isna(lon):
        return False
    return (11.43 <= lat <= 11.72) and (104.75 <= lon <= 104.99)

def compute_store_centroid(coords_array: np.ndarray, eps_meters: float = 100.0, min_samples: int = 2) -> Tuple[float, float]:
    """
    Computes median centroid of dominant physical cluster using DBSCAN.
    Eliminates remote delivery scans and phone GPS outliers.
    """
    n_pts = len(coords_array)
    if n_pts == 0:
        return np.nan, np.nan
    if n_pts <= 2:
        return float(np.median(coords_array[:, 0])), float(np.median(coords_array[:, 1]))

    coords_rad = np.radians(coords_array)
    earth_radius_m = 6371000.0
    eps_rad = eps_meters / earth_radius_m

    db = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine")
    labels = db.fit_predict(coords_rad)

    valid_labels = labels[labels != -1]
    if len(valid_labels) == 0:
        return float(np.median(coords_array[:, 0])), float(np.median(coords_array[:, 1]))

    dominant_cluster = collections.Counter(valid_labels).most_common(1)[0][0]
    cluster_points = coords_array[labels == dominant_cluster]

    return float(np.median(cluster_points[:, 0])), float(np.median(cluster_points[:, 1]))

def aggregate_weekly_snapshot(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Aggregates cleaned transactions into weekly merchant snapshots.
    Derives ISO calendar week, start date, end date, and human label row-by-row.
    """
    df = df.copy()

    # Step A: Derive Calendar Weeks & Labels Row-by-Row
    iso_cal = df["TRANSACTION_DATETIME"].dt.isocalendar()
    df["ISO_WEEK"] = (
        iso_cal["year"].astype(str)
        + "-W"
        + iso_cal["week"].astype(str).str.zfill(2)
    )

    mondays = (
        df["TRANSACTION_DATETIME"]
        - pd.to_timedelta(df["TRANSACTION_DATETIME"].dt.weekday, unit="D")
    ).dt.date
    df["WEEK_START_DATE"] = mondays
    df["WEEK_END_DATE"] = (
        pd.to_datetime(mondays) + pd.Timedelta(days=6)
    ).dt.date

    start_fmt = pd.to_datetime(df["WEEK_START_DATE"]).dt.strftime("%d %b")
    end_fmt = pd.to_datetime(df["WEEK_END_DATE"]).dt.strftime("%d %b %Y")
    df["WEEK_LABEL"] = (
        "Week "
        + iso_cal["week"].astype(str).str.zfill(2)
        + " ("
        + start_fmt
        + " – "
        + end_fmt
        + ")"
    )

    # Step B: Base Aggregation per (BKG_MERCHN_ID, ISO_WEEK)
    def get_mode(series):
        m = series.mode()
        return m.iloc[0] if not m.empty else np.nan

    grouped = df.groupby(["BKG_MERCHN_ID", "ISO_WEEK"])
    agg_base = grouped.agg(
        BKG_MERCHN_NAME=("BKG_MERCHN_NAME", get_mode),
        BENEFICIARY_BANK_CODE=("BENEFICIARY_BANK_CODE", get_mode),
        TRANSACTION_COUNT=("TRANSACTION_ID", "count"),
        WEEK_START_DATE=("WEEK_START_DATE", "first"),
        WEEK_END_DATE=("WEEK_END_DATE", "first"),
        WEEK_LABEL=("WEEK_LABEL", "first"),
    ).reset_index()

    # Step C: Compute DBSCAN Centroids (Using only VALID_GPS == True rows)
    valid_gps_df = df[df["VALID_GPS"]][["BKG_MERCHN_ID", "ISO_WEEK", "LATITUDE", "LONGITUDE"]]
    coords_by_merchant_week = valid_gps_df.groupby(["BKG_MERCHN_ID", "ISO_WEEK"])

    centroids = []
    for (m_id, w_tag) in zip(agg_base["BKG_MERCHN_ID"], agg_base["ISO_WEEK"]):
        key = (m_id, w_tag)
        if key in coords_by_merchant_week.groups:
            coords_array = coords_by_merchant_week.get_group(key)[["LATITUDE", "LONGITUDE"]].values
            lat, lng = compute_store_centroid(coords_array, eps_meters=100.0, min_samples=2)
        else:
            lat, lng = np.nan, np.nan

        centroids.append({
            "BKG_MERCHN_ID": m_id,
            "ISO_WEEK": w_tag,
            "LATITUDE": lat,
            "LONGITUDE": lng,
        })

    if not centroids:
        centroid_df = pd.DataFrame(columns=["BKG_MERCHN_ID", "ISO_WEEK", "LATITUDE", "LONGITUDE"])
    else:
        centroid_df = pd.DataFrame(centroids)
    result = pd.merge(agg_base, centroid_df, on=["BKG_MERCHN_ID", "ISO_WEEK"], how="left")

    # Step D: Phnom Penh Boundary Check
    result["IS_IN_PP"] = result.apply(
        lambda r: is_in_phnom_penh(r["LATITUDE"], r["LONGITUDE"]), axis=1
    )

    final_columns = [
        "ISO_WEEK",
        "WEEK_START_DATE",
        "WEEK_END_DATE",
        "WEEK_LABEL",
        "BKG_MERCHN_ID",
        "BKG_MERCHN_NAME",
        "BENEFICIARY_BANK_CODE",
        "TRANSACTION_COUNT",
        "LATITUDE",
        "LONGITUDE",
        "IS_IN_PP"
    ]
    result = result[final_columns]

    metrics = {
        "snapshot_rows": len(result),
        "unique_merchants": int(result["BKG_MERCHN_ID"].nunique()),
        "distinct_weeks": sorted(result["ISO_WEEK"].unique().tolist()),
        "merchants_in_pp": int(result["IS_IN_PP"].sum()),
        "merchants_20plus": int(((result["IS_IN_PP"] == True) & (result["TRANSACTION_COUNT"] >= 20)).sum())
    }

    return result, metrics
