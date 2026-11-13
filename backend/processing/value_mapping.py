"""
Dynamic action value mapping configuration and normalization algorithms for web access logs.
Maps arbitrary action/event values from the dataset's action column to standard internal actions.
"""
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd

ALLOWED_ACTIONS: List[str] = [
    "page_view",
    "click",
    "search",
    "add_to_cart",
    "remove_from_cart",
    "purchase",
    "login",
    "logout",
    "other",
]

ACTION_ALIASES: Dict[str, List[str]] = {
    "page_view": [
        "page_view",
        "view",
        "visit",
        "pageview",
        "page-view",
        "pv",
        "view_page",
    ],
    "click": [
        "click",
        "link_click",
        "linkclick",
        "button_click",
    ],
    "search": [
        "search",
        "search_query",
        "search_query_submitted",
        "query",
    ],
    "add_to_cart": [
        "add_to_cart",
        "add_cart",
        "cart_add",
        "add-cart",
        "addtocart",
    ],
    "remove_from_cart": [
        "remove_from_cart",
        "remove_cart",
        "cart_remove",
        "remove-cart",
        "removefromcart",
    ],
    "purchase": [
        "purchase",
        "order_completed",
        "checkout_completed",
        "order",
        "checkout",
        "buy",
    ],
    "login": [
        "login",
        "sign_in",
        "signin",
        "log_in",
    ],
    "logout": [
        "logout",
        "sign_out",
        "signout",
        "log_out",
    ],
}


def normalize_action_value(val: Any) -> str:
    """
    Trim whitespace, lowercase, and normalize spaces, hyphens, and underscores.
    """
    if val is None:
        return ""
    s = str(val).strip().lower()
    # Replace spaces and hyphens with underscores
    s = re.sub(r'[\s\-]+', '_', s)
    # Collapse multiple consecutive underscores
    s = re.sub(r'_+', '_', s)
    return s


def _clean_alphanumeric(val: Any) -> str:
    """
    Collapse to alphanumeric for comparison (e.g. 'pageview' -> 'pageview').
    """
    if val is None:
        return ""
    return re.sub(r'[^a-z0-9]', '', str(val).lower())


def _build_action_alias_lookup() -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Build underscore and collapsed lookup maps for standard action aliases.
    """
    underscore_map: Dict[str, str] = {}
    collapsed_map: Dict[str, str] = {}

    for action, aliases in ACTION_ALIASES.items():
        all_aliases = set(aliases) | {action}
        for alias in all_aliases:
            norm_u = normalize_action_value(alias)
            norm_c = _clean_alphanumeric(alias)
            if norm_u and norm_u not in underscore_map:
                underscore_map[norm_u] = action
            if norm_c and norm_c not in collapsed_map:
                collapsed_map[norm_c] = action

    return underscore_map, collapsed_map


UNDERSCORE_ACTION_LOOKUP, COLLAPSED_ACTION_LOOKUP = _build_action_alias_lookup()


def map_action_values(values: List[Any]) -> Dict[str, Any]:
    """
    Inspects unique raw action values and returns:
    - auto_mapping: Dict[original_val, standard_action]
    - unknown_values: List[original_val]
    - ambiguous_values: List[original_val]

    Note: Unknown values are NOT automatically mapped to 'other'.
    """
    auto_mapping: Dict[str, str] = {}
    unknown_values: List[str] = []
    ambiguous_values: List[str] = []

    # Preserve order of appearance while ensuring uniqueness
    seen = set()
    unique_vals = []
    for v in values:
        v_str = str(v).strip()
        if v_str and v_str not in seen:
            seen.add(v_str)
            unique_vals.append(v_str)

    for val in unique_vals:
        norm_u = normalize_action_value(val)
        norm_c = _clean_alphanumeric(val)

        matched_action = None

        # 1. Exact match against allowed actions
        if norm_u in ALLOWED_ACTIONS:
            matched_action = norm_u
        # 2. Check normalized underscore lookup
        elif norm_u in UNDERSCORE_ACTION_LOOKUP:
            matched_action = UNDERSCORE_ACTION_LOOKUP[norm_u]
        # 3. Check collapsed alphanumeric lookup
        elif norm_c in COLLAPSED_ACTION_LOOKUP:
            matched_action = COLLAPSED_ACTION_LOOKUP[norm_c]

        if matched_action:
            auto_mapping[val] = matched_action
        else:
            unknown_values.append(val)

    return {
        "auto_mapping": auto_mapping,
        "unknown_values": unknown_values,
        "ambiguous_values": ambiguous_values,
    }


def get_unique_action_values(dataset) -> List[str]:
    """
    Extracts unique non-empty string values from the dataset's action column via Pandas.
    Requires column mapping for 'action' to be set and the CSV file to exist on disk.
    """
    if not dataset.column_mapping or 'action' not in dataset.column_mapping:
        raise ValueError(
            "Column mapping has not been completed. The 'action' column is not mapped yet."
        )

    action_col = dataset.column_mapping['action']
    file_path = dataset.file_path

    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Uploaded CSV file not found on disk at '{file_path}'."
        )

    # Read the action column from the CSV
    df = pd.read_csv(file_path, usecols=[action_col])
    raw_vals = df[action_col].dropna().tolist()

    seen = set()
    unique_vals = []
    for v in raw_vals:
        v_str = str(v).strip()
        if v_str and v_str not in seen:
            seen.add(v_str)
            unique_vals.append(v_str)

    return unique_vals


def validate_manual_value_mapping(
    unique_action_values: List[str],
    user_mapping: Any,
    auto_mapping: Optional[Dict[str, str]] = None,
) -> Tuple[bool, Optional[str], Optional[Dict[str, str]]]:
    """
    Validates manual value mapping for the action column.

    Validation rules:
    - mapping must be a non-empty dictionary
    - every target action must be in ALLOWED_ACTIONS
    - every source value must exist in unique_action_values
    - unknown source values cannot silently disappear (all unique action values
      must be present in the merged mapping)

    Returns:
        (is_valid: bool, error_message: Optional[str], final_mapping: Optional[dict])
    """
    if not isinstance(user_mapping, dict):
        return False, "Field 'mapping' must be a JSON object/dictionary.", None

    if not user_mapping:
        return False, "Mapping cannot be empty.", None

    unique_set = set(unique_action_values)

    # 1. Validate every target action belongs to ALLOWED_ACTIONS
    for src, target in user_mapping.items():
        if target not in ALLOWED_ACTIONS:
            return (
                False,
                f"Invalid target action '{target}'. Allowed actions are: {', '.join(ALLOWED_ACTIONS)}.",
                None,
            )

    # 2. Validate every source value exists in the dataset's action column
    for src in user_mapping.keys():
        if src not in unique_set:
            return (
                False,
                f"Source value '{src}' does not exist in the dataset's action column.",
                None,
            )

    # 3. Combine auto-mapping with user-provided mappings
    final_mapping: Dict[str, str] = dict(auto_mapping or {})
    final_mapping.update(user_mapping)

    # 4. Ensure no action values silently disappear
    missing_sources = [v for v in unique_action_values if v not in final_mapping]
    if missing_sources:
        return (
            False,
            f"Unmapped action value(s): {missing_sources}. "
            "All action values must be mapped to an allowed action (e.g. 'other').",
            None,
        )

    return True, None, final_mapping
