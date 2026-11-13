"""
Sessionization module for cleaned web access logs.

Groups user events into sessions using an inactivity-timeout threshold (default: 30 minutes)
between consecutive events, preserves valid mapped session IDs when present, generates
per-dataset session IDs for missing values, persists Session summary rows in SQLite,
and writes the ordered sessionized CSV to disk for downstream analytics and pattern mining.
"""
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd
from django.conf import settings
from django.db import transaction

from datasets.models import Dataset, Session

DEFAULT_TIMEOUT_MINUTES = 30
REQUIRED_CLEANED_COLUMNS: List[str] = [
    "user_id",
    "timestamp",
    "page_url",
    "action",
]
OPTIONAL_CLEANED_COLUMNS: List[str] = [
    "session_id",
    "device",
    "referrer",
]


def validate_timeout_minutes(timeout_minutes: Any) -> float:
    """
    Validate that timeout_minutes is a positive finite number (not bool).
    """
    if isinstance(timeout_minutes, bool) or not isinstance(timeout_minutes, (int, float)):
        raise ValueError("timeout_minutes must be a positive number.")
    timeout_val = float(timeout_minutes)
    if math.isnan(timeout_val) or math.isinf(timeout_val) or timeout_val <= 0:
        raise ValueError("timeout_minutes must be a positive number greater than 0.")
    return timeout_val


def _to_aware_datetime(ts: pd.Timestamp) -> datetime:
    """
    Convert a pandas Timestamp to a timezone-aware Python datetime (UTC if naive).
    """
    dt = ts.to_pydatetime()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def sessionize_dataset(
    dataset: Dataset, timeout_minutes: Any = DEFAULT_TIMEOUT_MINUTES
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Sessionizes a cleaned Dataset using consecutive-event inactivity timeout.

    Existing session_id policy:
    - If 'session_id' was mapped and an event has a non-empty value, preserve it.
    - If 'session_id' is missing/empty for an event, assign a generated session ID
      using the consecutive-event inactivity timeout algorithm.
    - If no 'session_id' column exists at all, generate all session IDs using the
      inactivity timeout algorithm.

    Generated session ID format:
        <job_id>-S0001, <job_id>-S0002, ... (unique within the dataset).

    Returns:
        (sessionized_df: pd.DataFrame, summary: Dict[str, Any])
    """
    timeout_val = validate_timeout_minutes(timeout_minutes)
    timeout_display: Any = int(timeout_val) if timeout_val.is_integer() else timeout_val

    cleaned_path = dataset.cleaned_file_path
    if not cleaned_path or not os.path.exists(cleaned_path):
        raise FileNotFoundError(
            f"Cleaned CSV file not found on disk at '{cleaned_path}'."
        )

    df = pd.read_csv(cleaned_path)

    missing_cols = [col for col in REQUIRED_CLEANED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Cleaned CSV is missing required column(s): {', '.join(missing_cols)}."
        )

    uploads_dir = os.path.join(settings.BASE_DIR, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    sessionized_file_path = os.path.join(uploads_dir, f"sessionized_{dataset.job_id}.csv")

    if df.empty:
        if "session_id" not in df.columns:
            df["session_id"] = pd.Series(dtype="object")
        ordered_cols = _order_sessionized_columns(df.columns.tolist())
        df = df[ordered_cols]
        df.to_csv(sessionized_file_path, index=False)

        with transaction.atomic():
            Session.objects.filter(dataset=dataset).delete()
            dataset.sessionized_file_path = sessionized_file_path
            dataset.status = Dataset.STATUS_COMPLETED
            dataset.save(update_fields=["sessionized_file_path", "status"])

        return df, {
            "job_id": str(dataset.job_id),
            "status": dataset.status,
            "timeout_minutes": timeout_display,
            "total_sessions": 0,
            "total_users": 0,
            "sessionized_file_available": os.path.exists(sessionized_file_path),
        }

    # Parse timestamps consistently
    parsed_ts = pd.to_datetime(df["timestamp"], errors="coerce")
    if parsed_ts.dtype == object:
        parsed_ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df["timestamp"] = parsed_ts
    df = df.dropna(subset=["timestamp"]).copy()

    # Clean user_id and sort deterministically by (user_id, timestamp)
    df["user_id"] = df["user_id"].astype(str).str.strip()
    df = df.sort_values(by=["user_id", "timestamp"], kind="mergesort").reset_index(drop=True)

    # Extract any existing non-empty session_ids
    has_session_col = "session_id" in df.columns
    existing_session_ids: List[Optional[str]] = []
    used_session_ids: Set[str] = set()

    if has_session_col:
        for val in df["session_id"]:
            if pd.isna(val):
                existing_session_ids.append(None)
            else:
                s = str(val).strip()
                if not s or s.lower() in {"nan", "none", "null"}:
                    existing_session_ids.append(None)
                else:
                    existing_session_ids.append(s)
                    used_session_ids.add(s)
    else:
        existing_session_ids = [None] * len(df)

    # Assign session IDs per user based on consecutive-event inactivity gap
    timeout_delta = pd.Timedelta(minutes=timeout_val)
    assigned_session_ids: List[str] = []
    session_counter = 0

    def _next_generated_id() -> str:
        nonlocal session_counter
        while True:
            session_counter += 1
            candidate = f"{dataset.job_id}-S{session_counter:04d}"
            if candidate not in used_session_ids:
                used_session_ids.add(candidate)
                return candidate

    current_user: Optional[str] = None
    prev_ts: Optional[pd.Timestamp] = None
    current_generated_sid: Optional[str] = None

    for idx, row in df.iterrows():
        uid = row["user_id"]
        ts = row["timestamp"]
        existing_sid = existing_session_ids[idx]

        if uid != current_user:
            current_user = uid
            prev_ts = None
            current_generated_sid = None

        if existing_sid is not None:
            assigned_session_ids.append(existing_sid)
            current_generated_sid = None
            prev_ts = ts
        else:
            if (
                current_generated_sid is None
                or prev_ts is None
                or (ts - prev_ts) > timeout_delta
            ):
                current_generated_sid = _next_generated_id()
            assigned_session_ids.append(current_generated_sid)
            prev_ts = ts

    df["session_id"] = assigned_session_ids

    # Build Session model objects grouped by session_id
    session_objects: List[Session] = []
    for sid, group in df.groupby("session_id", sort=False):
        start_ts = _to_aware_datetime(group["timestamp"].min())
        end_ts = _to_aware_datetime(group["timestamp"].max())
        session_objects.append(
            Session(
                dataset=dataset,
                session_id=str(sid),
                user_id=str(group["user_id"].iloc[0]),
                start_time=start_ts,
                end_time=end_ts,
                duration=end_ts - start_ts,
                event_count=int(len(group)),
            )
        )

    # Reorder columns cleanly and save sessionized CSV
    ordered_cols = _order_sessionized_columns(df.columns.tolist())
    df = df[ordered_cols]
    df.to_csv(sessionized_file_path, index=False)

    # Atomically replace previous sessions for this dataset
    with transaction.atomic():
        Session.objects.filter(dataset=dataset).delete()
        Session.objects.bulk_create(session_objects)
        dataset.sessionized_file_path = sessionized_file_path
        dataset.status = Dataset.STATUS_COMPLETED
        dataset.save(update_fields=["sessionized_file_path", "status"])

    summary = {
        "job_id": str(dataset.job_id),
        "status": dataset.status,
        "timeout_minutes": timeout_display,
        "total_sessions": len(session_objects),
        "total_users": int(df["user_id"].nunique()),
        "sessionized_file_available": os.path.exists(sessionized_file_path),
    }

    return df, summary


def _order_sessionized_columns(columns: List[str]) -> List[str]:
    """
    Ensure standard logical columns appear in canonical order in the sessionized CSV.
    """
    preferred = ["user_id", "timestamp", "page_url", "action", "session_id", "device", "referrer"]
    ordered = [c for c in preferred if c in columns]
    remaining = [c for c in columns if c not in ordered]
    return ordered + remaining
