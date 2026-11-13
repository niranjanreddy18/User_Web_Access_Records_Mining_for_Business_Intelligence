import os
import pandas as pd

REQUIRED_ANALYTICS_COLUMNS = (
    "user_id",
    "timestamp",
    "page_url",
    "action",
    "session_id",
)


def _empty_traffic_by_hour():
    """Return a 24-hour list (0..23) initialized with zero event counts."""
    return [{"hour": hour, "events": 0} for hour in range(24)]


def _empty_analytics():
    """Return default empty analytics payload when no valid events exist."""
    return {
        "total_users": 0,
        "total_sessions": 0,
        "total_events": 0,
        "average_session_duration": 0.0,
        "average_events_per_session": 0.0,
        "average_pages_per_session": 0.0,
        "most_visited_pages": [],
        "least_visited_pages": [],
        "action_counts": {},
        "traffic_by_hour": _empty_traffic_by_hour(),
        "peak_traffic_hour": None,
        "traffic_by_day": [],
        "device_counts": {},
        "entry_pages": {},
        "exit_pages": {},
    }


def _parse_timestamps(series):
    """Parse timestamps to datetime, falling back to UTC for mixed timezone formats."""
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.dtype == object or not pd.api.types.is_datetime64_any_dtype(parsed):
        parsed = pd.to_datetime(series, errors="coerce", utc=True)
    return parsed


def _build_page_rankings(page_view_df):
    """Compute most and least visited page lists (up to 10 each) from page_view rows."""
    if page_view_df.empty:
        return [], []

    counts = page_view_df["page_url"].dropna().astype(str).value_counts()
    if counts.empty:
        return [], []

    most_visited = [
        {"page_url": str(page), "visits": int(count)}
        for page, count in counts.head(10).items()
    ]
    least_series = counts.sort_values(ascending=True, kind="mergesort")
    least_visited = [
        {"page_url": str(page), "visits": int(count)}
        for page, count in least_series.head(10).items()
    ]
    return most_visited, least_visited


def _build_temporal_metrics(valid_ts_df):
    """Compute hourly distribution (0..23), peak hour, and daily event counts."""
    if valid_ts_df.empty:
        return _empty_traffic_by_hour(), None, []

    hour_series = valid_ts_df["timestamp"].dt.hour.value_counts()
    traffic_by_hour = [
        {"hour": hour, "events": int(hour_series.get(hour, 0))}
        for hour in range(24)
    ]
    peak_traffic_hour = max(
        traffic_by_hour, key=lambda item: (item["events"], -item["hour"])
    )["hour"]

    day_series = (
        valid_ts_df["timestamp"].dt.strftime("%Y-%m-%d").value_counts().sort_index()
    )
    traffic_by_day = [
        {"date": str(day), "events": int(count)}
        for day, count in day_series.items()
    ]
    return traffic_by_hour, int(peak_traffic_hour), traffic_by_day


def _build_session_metrics(ordered_df, total_sessions):
    """Compute average duration and entry/exit page counts from ordered session events."""
    if ordered_df.empty or total_sessions == 0:
        return 0.0, {}, {}

    grouped = ordered_df.groupby("session_id", sort=False)
    durations = (grouped["timestamp"].max() - grouped["timestamp"].min()).dt.total_seconds()
    avg_duration = round(float(durations.mean()), 2) if not durations.empty else 0.0

    entry_counts = grouped["page_url"].first().dropna().astype(str).value_counts()
    exit_counts = grouped["page_url"].last().dropna().astype(str).value_counts()

    entry_pages = {str(page): int(count) for page, count in entry_counts.items()}
    exit_pages = {str(page): int(count) for page, count in exit_counts.items()}
    return avg_duration, entry_pages, exit_pages


def _value_count_dict(series):
    """Convert non-null series value counts into a plain dict with Python ints."""
    cleaned = series.dropna().astype(str)
    if cleaned.empty:
        return {}
    return {str(key): int(val) for key, val in cleaned.value_counts().items()}


def calculate_analytics(dataset):
    """
    Calculate comprehensive web access analytics from a sessionized dataset CSV.

    Raises FileNotFoundError if the sessionized CSV does not exist, or ValueError
    if required schema columns are missing.
    """
    file_path = getattr(dataset, "sessionized_file_path", None)
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError("Sessionized CSV file not found for this dataset.")

    df = pd.read_csv(file_path)
    missing_cols = [col for col in REQUIRED_ANALYTICS_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Missing required columns in sessionized CSV: {', '.join(missing_cols)}"
        )

    if df.empty:
        return _empty_analytics()

    df = df.copy()
    df["timestamp"] = _parse_timestamps(df["timestamp"])
    df = df.dropna(subset=["timestamp", "user_id", "session_id", "page_url", "action"])
    if df.empty:
        return _empty_analytics()

    df["user_id"] = df["user_id"].astype(str)
    df["session_id"] = df["session_id"].astype(str)
    df["page_url"] = df["page_url"].astype(str)
    df["action"] = df["action"].astype(str)

    ordered_df = df.sort_values(
        by=["session_id", "timestamp"], kind="mergesort"
    ).reset_index(drop=True)

    total_users = int(ordered_df["user_id"].nunique())
    total_sessions = int(ordered_df["session_id"].nunique())
    total_events = int(len(ordered_df))

    page_view_df = ordered_df[ordered_df["action"] == "page_view"]
    total_page_views = int(len(page_view_df))

    avg_duration, entry_pages, exit_pages = _build_session_metrics(
        ordered_df, total_sessions
    )
    avg_events_per_session = (
        round(float(total_events / total_sessions), 2) if total_sessions > 0 else 0.0
    )
    avg_pages_per_session = (
        round(float(total_page_views / total_sessions), 2) if total_sessions > 0 else 0.0
    )

    most_visited_pages, least_visited_pages = _build_page_rankings(page_view_df)
    action_counts = _value_count_dict(ordered_df["action"])
    traffic_by_hour, peak_traffic_hour, traffic_by_day = _build_temporal_metrics(
        ordered_df
    )
    device_counts = (
        _value_count_dict(ordered_df["device"])
        if "device" in ordered_df.columns
        else {}
    )

    return {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "total_events": total_events,
        "average_session_duration": avg_duration,
        "average_events_per_session": avg_events_per_session,
        "average_pages_per_session": avg_pages_per_session,
        "most_visited_pages": most_visited_pages,
        "least_visited_pages": least_visited_pages,
        "action_counts": action_counts,
        "traffic_by_hour": traffic_by_hour,
        "peak_traffic_hour": peak_traffic_hour,
        "traffic_by_day": traffic_by_day,
        "device_counts": device_counts,
        "entry_pages": entry_pages,
        "exit_pages": exit_pages,
    }
