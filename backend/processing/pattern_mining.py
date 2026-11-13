from collections import defaultdict
import os
import pandas as pd

from processing.analytics import REQUIRED_ANALYTICS_COLUMNS, _parse_timestamps


def validate_mining_params(min_support=0.1, max_pattern_length=3):
    """
    Validate pattern mining hyperparameters.

    min_support must satisfy 0 < min_support <= 1.
    max_pattern_length must be an integer >= 2.
    """
    if isinstance(min_support, bool) or not isinstance(min_support, (int, float)):
        raise ValueError("min_support must be a number greater than 0 and at most 1.")
    min_support_val = float(min_support)
    if min_support_val <= 0 or min_support_val > 1:
        raise ValueError("min_support must be > 0 and <= 1.")

    if isinstance(max_pattern_length, bool) or not isinstance(max_pattern_length, int):
        raise ValueError("max_pattern_length must be an integer >= 2.")
    if max_pattern_length < 2:
        raise ValueError("max_pattern_length must be >= 2.")

    return min_support_val, max_pattern_length


def _collapse_consecutive_duplicates(items):
    """Collapse consecutive duplicate values while keeping non-consecutive repeats."""
    collapsed = []
    for item in items:
        if not collapsed or collapsed[-1] != item:
            collapsed.append(item)
    return collapsed


def _extract_frequent_patterns(sequences, total_sessions, min_support, max_pattern_length):
    """
    Count contiguous sub-sequences of length 2..max_pattern_length across sessions.

    Each pattern contributes at most 1 per session regardless of intra-session repeats.
    """
    if total_sessions == 0:
        return []

    pattern_session_counts = defaultdict(int)
    for seq in sequences:
        seq_len = len(seq)
        if seq_len < 2:
            continue

        seen_in_session = set()
        upper_length = min(max_pattern_length, seq_len)
        for length in range(2, upper_length + 1):
            for idx in range(seq_len - length + 1):
                subseq = tuple(seq[idx : idx + length])
                if subseq not in seen_in_session:
                    seen_in_session.add(subseq)
                    pattern_session_counts[subseq] += 1

    results = []
    for pattern_tuple, session_count in pattern_session_counts.items():
        raw_support = session_count / total_sessions
        if raw_support >= min_support:
            results.append(
                {
                    "pattern": list(pattern_tuple),
                    "length": len(pattern_tuple),
                    "session_count": int(session_count),
                    "support": round(float(raw_support), 4),
                    "_raw_support": raw_support,
                }
            )

    results.sort(
        key=lambda item: (
            -item["_raw_support"],
            -item["length"],
            tuple(item["pattern"]),
        )
    )
    for item in results:
        del item["_raw_support"]
    return results


def _calculate_transitions(page_sequences, total_sessions):
    """Calculate top 20 adjacent page transitions ranked by unique session count."""
    if total_sessions == 0:
        return []

    transition_counts = defaultdict(int)
    unique_session_counts = defaultdict(int)

    for seq in page_sequences:
        if len(seq) < 2:
            continue
        seen_in_session = set()
        for idx in range(len(seq) - 1):
            edge = (seq[idx], seq[idx + 1])
            transition_counts[edge] += 1
            if edge not in seen_in_session:
                seen_in_session.add(edge)
                unique_session_counts[edge] += 1

    transitions = [
        {
            "from": edge[0],
            "to": edge[1],
            "transition_count": int(transition_counts[edge]),
            "unique_sessions": int(unique_sessions),
            "support": round(float(unique_sessions / total_sessions), 4),
        }
        for edge, unique_sessions in unique_session_counts.items()
    ]

    transitions.sort(
        key=lambda item: (
            -item["unique_sessions"],
            -item["transition_count"],
            item["from"],
            item["to"],
        )
    )
    return transitions[:20]


def mine_patterns(dataset, min_support=0.1, max_pattern_length=3):
    """
    Discover frequent sequential page/action patterns and transitions from sessionized CSV.

    Raises FileNotFoundError if sessionized CSV does not exist, or ValueError on
    invalid parameters or missing required CSV columns.
    """
    min_support_val, max_len_val = validate_mining_params(
        min_support=min_support,
        max_pattern_length=max_pattern_length,
    )

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
        return {
            "page_patterns": [],
            "action_patterns": [],
            "transitions": [],
            "common_journeys": [],
        }

    df = df.copy()
    df["timestamp"] = _parse_timestamps(df["timestamp"])
    df = df.dropna(subset=["timestamp", "user_id", "session_id", "page_url", "action"])
    if df.empty:
        return {
            "page_patterns": [],
            "action_patterns": [],
            "transitions": [],
            "common_journeys": [],
        }

    df["session_id"] = df["session_id"].astype(str)
    df["page_url"] = df["page_url"].astype(str)
    df["action"] = df["action"].astype(str)

    ordered_df = df.sort_values(
        by=["session_id", "timestamp"], kind="mergesort"
    ).reset_index(drop=True)

    page_sequences = []
    action_sequences = []
    for _, session_group in ordered_df.groupby("session_id", sort=False):
        page_sequences.append(
            _collapse_consecutive_duplicates(session_group["page_url"].tolist())
        )
        action_sequences.append(
            _collapse_consecutive_duplicates(session_group["action"].tolist())
        )

    total_sessions = len(page_sequences)
    page_patterns = _extract_frequent_patterns(
        page_sequences, total_sessions, min_support_val, max_len_val
    )
    action_patterns = _extract_frequent_patterns(
        action_sequences, total_sessions, min_support_val, max_len_val
    )
    transitions = _calculate_transitions(page_sequences, total_sessions)
    common_journeys = list(page_patterns[:20])

    return {
        "page_patterns": page_patterns,
        "action_patterns": action_patterns,
        "transitions": transitions,
        "common_journeys": common_journeys,
    }
