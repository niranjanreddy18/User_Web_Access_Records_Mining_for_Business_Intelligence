from datasets.models import AnalysisResult, PatternMiningResult


def _format_percentage(ratio):
    """Format a 0..1 ratio as a clean percentage string (e.g., 34% or 34.5%)."""
    pct = round(float(ratio) * 100, 1)
    if pct.is_integer():
        return f"{int(pct)}%"
    return f"{pct}%"


def _build_navigation_insights(patterns):
    """Generate deterministic navigation insights from PatternMiningResult payload."""
    if not isinstance(patterns, dict):
        return []

    insights = []
    journeys = patterns.get("common_journeys") or patterns.get("page_patterns") or []
    top_journey_pattern = None

    if journeys:
        top_journey = journeys[0]
        pattern_list = top_journey.get("pattern") or []
        session_count = int(top_journey.get("session_count", 0) or 0)
        support = float(top_journey.get("support", 0.0) or 0.0)
        if pattern_list and session_count > 0:
            top_journey_pattern = list(pattern_list)
            path_str = " → ".join(str(p) for p in pattern_list)
            insights.append(
                {
                    "type": "navigation",
                    "title": "Common User Journey",
                    "message": (
                        f"{path_str} occurred in {_format_percentage(support)} "
                        f"of sessions ({session_count:,} sessions)."
                    ),
                    "severity": "info",
                    "metric": {
                        "name": "common_journey",
                        "value": {
                            "pattern": [str(p) for p in pattern_list],
                            "session_count": session_count,
                            "support": round(support, 4),
                        },
                    },
                }
            )

    transitions = patterns.get("transitions") or []
    if transitions:
        top_transition = transitions[0]
        from_page = top_transition.get("from")
        to_page = top_transition.get("to")
        unique_sessions = int(top_transition.get("unique_sessions", 0) or 0)
        support = float(top_transition.get("support", 0.0) or 0.0)
        if (
            from_page is not None
            and to_page is not None
            and unique_sessions > 0
            and top_journey_pattern != [from_page, to_page]
        ):
            insights.append(
                {
                    "type": "navigation",
                    "title": "Frequent Page Transition",
                    "message": (
                        f"{from_page} → {to_page} occurred in {_format_percentage(support)} "
                        f"of sessions ({unique_sessions:,} sessions)."
                    ),
                    "severity": "info",
                    "metric": {
                        "name": "top_transition",
                        "value": {
                            "from": str(from_page),
                            "to": str(to_page),
                            "unique_sessions": unique_sessions,
                            "support": round(support, 4),
                        },
                    },
                }
            )

    return insights


def _build_traffic_insights(analytics):
    """Generate peak traffic period insight when events exist."""
    peak_hour = analytics.get("peak_traffic_hour")
    if peak_hour is None:
        return []
    try:
        hour_int = int(peak_hour)
    except (TypeError, ValueError):
        return []

    if not (0 <= hour_int <= 23):
        return []

    return [
        {
            "type": "traffic",
            "title": "Peak Traffic Period",
            "message": f"Most user activity occurred around {hour_int:02d}:00.",
            "severity": "info",
            "metric": {
                "name": "peak_traffic_hour",
                "value": hour_int,
            },
        }
    ]


def _build_content_insights(analytics):
    """Generate most and least visited page insights from page_view rankings."""
    insights = []
    most_visited = analytics.get("most_visited_pages") or []
    least_visited = analytics.get("least_visited_pages") or []

    top_page_url = None
    if most_visited:
        top = most_visited[0]
        page_url = top.get("page_url")
        visits = int(top.get("visits", 0) or 0)
        if page_url is not None and visits > 0:
            top_page_url = str(page_url)
            view_label = "page view" if visits == 1 else "page views"
            insights.append(
                {
                    "type": "content",
                    "title": "Most Visited Page",
                    "message": (
                        f"{top_page_url} was the most visited page with "
                        f"{visits:,} {view_label}."
                    ),
                    "severity": "info",
                    "metric": {
                        "name": "most_visited_page",
                        "value": {
                            "page_url": top_page_url,
                            "visits": visits,
                        },
                    },
                }
            )

    if least_visited:
        least = least_visited[0]
        page_url = least.get("page_url")
        visits = int(least.get("visits", 0) or 0)
        if page_url is not None and visits > 0 and str(page_url) != top_page_url:
            insights.append(
                {
                    "type": "content",
                    "title": "Least Visited Page",
                    "message": (
                        f"Among recorded page views, {page_url} had the fewest "
                        f"visits ({visits:,})."
                    ),
                    "severity": "info",
                    "metric": {
                        "name": "least_visited_page",
                        "value": {
                            "page_url": str(page_url),
                            "visits": visits,
                        },
                    },
                }
            )

    return insights


def _build_engagement_insights(analytics):
    """Generate neutral session engagement summary from session/page averages."""
    total_sessions = int(analytics.get("total_sessions", 0) or 0)
    if total_sessions <= 0:
        return []

    avg_pages = analytics.get("average_pages_per_session")
    avg_events = analytics.get("average_events_per_session")
    avg_duration = analytics.get("average_session_duration")

    if avg_pages is not None and float(avg_pages) > 0:
        avg_pages_val = round(float(avg_pages), 2)
        duration_suffix = ""
        if avg_duration is not None and float(avg_duration) > 0:
            duration_suffix = f" with an average session duration of {round(float(avg_duration), 2)} seconds"
        return [
            {
                "type": "engagement",
                "title": "Average Session Engagement",
                "message": (
                    f"Users viewed an average of {avg_pages_val} pages per session"
                    f"{duration_suffix}."
                ),
                "severity": "info",
                "metric": {
                    "name": "average_pages_per_session",
                    "value": avg_pages_val,
                },
            }
        ]

    if avg_events is not None and float(avg_events) > 0:
        avg_events_val = round(float(avg_events), 2)
        return [
            {
                "type": "engagement",
                "title": "Average Session Engagement",
                "message": (
                    f"Sessions averaged {avg_events_val} events across "
                    f"{total_sessions:,} sessions."
                ),
                "severity": "info",
                "metric": {
                    "name": "average_events_per_session",
                    "value": avg_events_val,
                },
            }
        ]

    return []


def _build_device_insights(analytics):
    """Generate primary device insight if valid device counts exist."""
    raw_devices = analytics.get("device_counts") or {}
    if not isinstance(raw_devices, dict):
        return []

    valid_devices = {
        str(k): int(v)
        for k, v in raw_devices.items()
        if k is not None and str(k).strip() != "" and isinstance(v, (int, float)) and int(v) > 0
    }
    if not valid_devices:
        return []

    total_device_events = sum(valid_devices.values())
    if total_device_events <= 0:
        return []

    top_device, top_count = min(
        valid_devices.items(),
        key=lambda item: (-item[1], item[0]),
    )
    pct_str = _format_percentage(top_count / total_device_events)
    pct_val = round((top_count / total_device_events) * 100, 1)

    return [
        {
            "type": "device",
            "title": "Primary Device",
            "message": f"{top_device} accounted for {pct_str} of recorded activity.",
            "severity": "info",
            "metric": {
                "name": "primary_device",
                "value": {
                    "device": top_device,
                    "count": top_count,
                    "percentage": pct_val,
                },
            },
        }
    ]


def _build_entry_exit_insights(analytics):
    """Generate neutral entry and exit page insights from session boundary counts."""
    insights = []
    entry_pages = analytics.get("entry_pages") or {}
    exit_pages = analytics.get("exit_pages") or {}

    if isinstance(entry_pages, dict):
        valid_entries = {
            str(k): int(v)
            for k, v in entry_pages.items()
            if k is not None and str(k).strip() != "" and isinstance(v, (int, float)) and int(v) > 0
        }
        if valid_entries:
            top_entry, entry_count = min(
                valid_entries.items(),
                key=lambda item: (-item[1], item[0]),
            )
            session_label = "session" if entry_count == 1 else "sessions"
            insights.append(
                {
                    "type": "exit",
                    "title": "Common Entry Page",
                    "message": (
                        f"{top_entry} was the most common session entry page "
                        f"({entry_count:,} {session_label})."
                    ),
                    "severity": "info",
                    "metric": {
                        "name": "top_entry_page",
                        "value": {
                            "page_url": top_entry,
                            "sessions": entry_count,
                        },
                    },
                }
            )

    if isinstance(exit_pages, dict):
        valid_exits = {
            str(k): int(v)
            for k, v in exit_pages.items()
            if k is not None and str(k).strip() != "" and isinstance(v, (int, float)) and int(v) > 0
        }
        if valid_exits:
            top_exit, exit_count = min(
                valid_exits.items(),
                key=lambda item: (-item[1], item[0]),
            )
            session_label = "session" if exit_count == 1 else "sessions"
            insights.append(
                {
                    "type": "exit",
                    "title": "Common Exit Page",
                    "message": (
                        f"{top_exit} was the most common session exit page "
                        f"({exit_count:,} {session_label})."
                    ),
                    "severity": "info",
                    "metric": {
                        "name": "top_exit_page",
                        "value": {
                            "page_url": top_exit,
                            "sessions": exit_count,
                        },
                    },
                }
            )

    return insights


def _build_conversion_insights(analytics):
    """Generate neutral purchase activity insight from action_counts."""
    action_counts = analytics.get("action_counts") or {}
    if not isinstance(action_counts, dict):
        return []

    purchase_count = int(action_counts.get("purchase", 0) or 0)
    if purchase_count > 0:
        event_label = "event was" if purchase_count == 1 else "events were"
        return [
            {
                "type": "conversion",
                "title": "Purchase Activity",
                "message": f"{purchase_count:,} purchase {event_label} recorded.",
                "severity": "positive",
                "metric": {
                    "name": "purchase_events",
                    "value": purchase_count,
                },
            }
        ]

    return [
        {
            "type": "conversion",
            "title": "Purchase Activity",
            "message": "No purchase events were recorded in the uploaded dataset.",
            "severity": "info",
            "metric": {
                "name": "purchase_events",
                "value": 0,
            },
        }
    ]


def generate_insights(dataset):
    """
    Generate deterministic, data-backed business intelligence insights from
    AnalysisResult and (when available) PatternMiningResult.

    Raises ValueError if AnalysisResult does not exist for the dataset.
    """
    analysis_result = AnalysisResult.objects.filter(dataset=dataset).first()
    if analysis_result is None:
        raise ValueError("Analytics must be calculated before generating insights.")

    analytics = analysis_result.results if isinstance(analysis_result.results, dict) else {}
    total_events = int(analytics.get("total_events", 0) or 0)
    total_sessions = int(analytics.get("total_sessions", 0) or 0)

    if total_events <= 0 or total_sessions <= 0:
        return []

    mining_result = PatternMiningResult.objects.filter(dataset=dataset).first()
    patterns = (
        mining_result.results
        if mining_result is not None and isinstance(mining_result.results, dict)
        else {}
    )

    insights = []
    insights.extend(_build_navigation_insights(patterns))
    insights.extend(_build_traffic_insights(analytics))
    insights.extend(_build_content_insights(analytics))
    insights.extend(_build_engagement_insights(analytics))
    insights.extend(_build_device_insights(analytics))
    insights.extend(_build_entry_exit_insights(analytics))
    insights.extend(_build_conversion_insights(analytics))

    return insights[:10]
