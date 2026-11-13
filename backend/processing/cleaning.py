"""
Data validation, cleaning, and standardization module for web access logs.
Standardizes schema, normalizes datetimes, handles missing values, removes duplicates,
and produces a quality report.
"""
import os
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from django.conf import settings

REQUIRED_FIELDS: List[str] = [
    "user_id",
    "timestamp",
    "page_url",
    "action",
]

OPTIONAL_FIELDS: List[str] = [
    "session_id",
    "device",
    "referrer",
]

ALL_LOGICAL_FIELDS: List[str] = REQUIRED_FIELDS + OPTIONAL_FIELDS


def clean_dataset(dataset) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Validates, cleans, and standardizes data for a given Dataset instance.

    Performs:
    1. Verification of column_mapping (all required fields must be mapped).
    2. Verification of value_mapping (must exist).
    3. Loading CSV and renaming columns to standard internal schema.
    4. Mapping action column using dataset.value_mapping.
    5. Normalizing timestamps to datetime.
    6. Detecting and removing rows with missing required fields or invalid timestamps.
    7. Removing exact duplicate rows.
    8. Generating a quality report.
    9. Persisting the cleaned dataframe to a temporary CSV (cleaned_file_path).

    Returns:
        (cleaned_df: pd.DataFrame, quality_report: Dict[str, Any])
    """
    # 1. Verify column mapping contains all required fields
    if not dataset.column_mapping or not isinstance(dataset.column_mapping, dict):
        raise ValueError("Column mapping has not been configured for this dataset.")

    missing_required = [f for f in REQUIRED_FIELDS if f not in dataset.column_mapping]
    if missing_required:
        raise ValueError(
            f"Missing required column mapping(s): {', '.join(missing_required)}."
        )

    # 2. Verify value mapping exists
    if not dataset.value_mapping or not isinstance(dataset.value_mapping, dict):
        raise ValueError("Value mapping has not been configured for this dataset.")

    # 3. Verify file exists on disk
    file_path = dataset.file_path
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Uploaded CSV file not found on disk at '{file_path}'."
        )

    # 4. Invert column mapping to map original CSV columns to logical fields
    # dataset.column_mapping is {logical_field: original_csv_col}
    col_rename = {
        orig_col: logical_field
        for logical_field, orig_col in dataset.column_mapping.items()
        if logical_field in ALL_LOGICAL_FIELDS
    }

    # Load only mapped columns
    df = pd.read_csv(file_path, usecols=list(col_rename.keys()))
    df = df.rename(columns=col_rename)

    # Keep only the logical columns in standard order
    active_columns = [
        col for col in ALL_LOGICAL_FIELDS if col in df.columns
    ]
    df = df[active_columns]

    rows_before = len(df)

    # 5. Apply value mapping to the action column
    # Convert non-null to stripped string before mapping
    df['action'] = (
        df['action']
        .astype(str)
        .str.strip()
        .map(dataset.value_mapping)
    )

    # 6. Parse and normalize timestamps
    parsed_timestamps = pd.to_datetime(df['timestamp'], errors='coerce')

    # 7. Identify invalid/missing fields
    def _is_missing_str(series: pd.Series) -> pd.Series:
        return (
            series.isna()
            | (series.astype(str).str.strip() == '')
            | series.astype(str).str.strip().str.lower().isin(['nan', 'none', 'null', 'nat'])
        )

    mask_missing_user_id = _is_missing_str(df['user_id'])
    mask_invalid_timestamp = parsed_timestamps.isna()
    mask_missing_page_url = _is_missing_str(df['page_url'])
    mask_missing_action = _is_missing_str(df['action'])

    # Count individual issue occurrences
    count_missing_user_id = int(mask_missing_user_id.sum())
    count_invalid_timestamp = int(mask_invalid_timestamp.sum())
    count_missing_page_url = int(mask_missing_page_url.sum())
    count_missing_action = int(mask_missing_action.sum())

    # Filter out rows with any missing required field or invalid timestamp
    invalid_rows_mask = (
        mask_missing_user_id
        | mask_invalid_timestamp
        | mask_missing_page_url
        | mask_missing_action
    )
    df_valid = df[~invalid_rows_mask].copy()

    # Assign parsed timestamps
    df_valid['timestamp'] = parsed_timestamps[~invalid_rows_mask]

    # Clean string fields
    df_valid['user_id'] = df_valid['user_id'].astype(str).str.strip()
    df_valid['page_url'] = df_valid['page_url'].astype(str).str.strip()
    df_valid['action'] = df_valid['action'].astype(str).str.strip()

    # Clean optional fields if present
    for opt in OPTIONAL_FIELDS:
        if opt in df_valid.columns:
            df_valid[opt] = df_valid[opt].astype(str).str.strip().replace(
                {'nan': None, 'none': None, 'null': None, '': None}
            )

    # 8. Remove exact duplicate rows
    duplicate_rows_count = int(df_valid.duplicated().sum())
    df_clean = df_valid.drop_duplicates().copy()

    rows_after = len(df_clean)
    rows_removed = rows_before - rows_after

    # 9. Quality report
    quality_report = {
        "rows_before": int(rows_before),
        "rows_after": int(rows_after),
        "rows_removed": int(rows_removed),
        "missing_user_id": count_missing_user_id,
        "invalid_timestamp": count_invalid_timestamp,
        "missing_page_url": count_missing_page_url,
        "missing_action": count_missing_action,
        "duplicate_rows": duplicate_rows_count,
    }

    # 10. Persist cleaned dataframe to disk for downstream sessionization & analytics
    uploads_dir = os.path.join(settings.BASE_DIR, 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    cleaned_file_path = os.path.join(uploads_dir, f"cleaned_{dataset.job_id}.csv")
    df_clean.to_csv(cleaned_file_path, index=False)

    return df_clean, quality_report
