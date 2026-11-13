"""
Dynamic column mapping configuration and algorithms for web access records.
Maps arbitrary CSV column headers to standardized internal logical fields.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

REQUIRED_FIELDS = [
    "user_id",
    "timestamp",
    "page_url",
    "action",
]

OPTIONAL_FIELDS = [
    "session_id",
    "device",
    "referrer",
]

ALL_LOGICAL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

# Maintainable alias dictionary mapping logical field names to known alias variants.
COLUMN_ALIASES: Dict[str, List[str]] = {
    "user_id": [
        "user_id",
        "customer_id",
        "visitor_id",
        "userid",
        "user",
        "customer",
        "client_id",
        "uid",
    ],
    "timestamp": [
        "timestamp",
        "time",
        "datetime",
        "date_time",
        "event_time",
        "created_at",
        "log_time",
        "access_time",
    ],
    "page_url": [
        "page_url",
        "url",
        "page",
        "path",
        "request_path",
        "uri",
        "request_url",
        "target_url",
    ],
    "action": [
        "action",
        "event",
        "event_type",
        "activity",
        "activity_type",
        "event_name",
        "method",
        "verb",
    ],
    "session_id": [
        "session_id",
        "session",
        "sessionid",
        "sess_id",
    ],
    "device": [
        "device",
        "device_type",
        "platform",
        "os",
        "user_agent",
    ],
    "referrer": [
        "referrer",
        "referer",
        "referring_url",
        "http_referer",
    ],
}


def normalize_name(name: str) -> str:
    """
    Normalize column header string:
    - trim whitespace
    - lowercase
    - replace spaces, hyphens, and multiple underscores with a single underscore
    """
    if not name:
        return ""
    stripped = name.strip().lower()
    # Replace spaces and hyphens with underscores
    cleaned = re.sub(r'[\s\-]+', '_', stripped)
    # Collapse multiple consecutive underscores
    cleaned = re.sub(r'_+', '_', cleaned)
    return cleaned


def _clean_alphanumeric(name: str) -> str:
    """
    Remove all non-alphanumeric characters for collapsed comparison.
    e.g. 'Customer_ID' -> 'customerid'
    """
    return re.sub(r'[^a-z0-9]', '', (name or '').lower())


def _build_alias_lookup() -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Build lookup maps from normalized alias to logical field.
    Returns:
        (underscore_lookup, collapsed_lookup)
    """
    underscore_map: Dict[str, str] = {}
    collapsed_map: Dict[str, str] = {}

    for field, aliases in COLUMN_ALIASES.items():
        # Always include the logical field itself as an alias
        all_aliases = set(aliases) | {field}
        for alias in all_aliases:
            norm_u = normalize_name(alias)
            norm_c = _clean_alphanumeric(alias)
            if norm_u and norm_u not in underscore_map:
                underscore_map[norm_u] = field
            if norm_c and norm_c not in collapsed_map:
                collapsed_map[norm_c] = field

    return underscore_map, collapsed_map


UNDERSCORE_ALIAS_LOOKUP, COLLAPSED_ALIAS_LOOKUP = _build_alias_lookup()


def map_columns(headers: List[str]) -> Dict[str, Any]:
    """
    Automatically maps a list of CSV headers to internal logical fields based
    on known aliases and normalized exact matching.

    Returns a dict with:
        - auto_mapping: Dict[str, str] (logical_field -> original header)
        - unmapped_required: List[str] (required logical fields not mapped)
        - unmapped_optional: List[str] (optional logical fields not mapped)
        - unmapped_columns: List[str] (input headers that were not mapped)
        - ambiguous: Dict[str, List[str]] (logical fields matching multiple input headers)
    """
    # Track which logical field matches which input header(s)
    field_to_headers: Dict[str, List[str]] = {field: [] for field in ALL_LOGICAL_FIELDS}
    header_to_fields: Dict[str, List[str]] = {h: [] for h in headers}

    for header in headers:
        norm_u = normalize_name(header)
        norm_c = _clean_alphanumeric(header)

        matched_field = None

        # 1. Exact match against logical field name
        if norm_u in ALL_LOGICAL_FIELDS:
            matched_field = norm_u
        # 2. Check normalized underscore lookup
        elif norm_u in UNDERSCORE_ALIAS_LOOKUP:
            matched_field = UNDERSCORE_ALIAS_LOOKUP[norm_u]
        # 3. Check collapsed alphanumeric lookup (e.g. 'eventtime' -> 'timestamp')
        elif norm_c in COLLAPSED_ALIAS_LOOKUP:
            matched_field = COLLAPSED_ALIAS_LOOKUP[norm_c]

        if matched_field:
            field_to_headers[matched_field].append(header)
            header_to_fields[header].append(matched_field)

    auto_mapping: Dict[str, str] = {}
    ambiguous: Dict[str, List[str]] = {}
    mapped_headers: Set[str] = set()

    # Identify clean 1-to-1 mappings vs ambiguous mappings
    for field, matching_headers in field_to_headers.items():
        if len(matching_headers) == 1:
            header = matching_headers[0]
            # Ensure the header wasn't claimed by multiple logical fields
            if len(header_to_fields[header]) == 1:
                auto_mapping[field] = header
                mapped_headers.add(header)
            else:
                ambiguous[field] = matching_headers
        elif len(matching_headers) > 1:
            # Multiple input headers match this single logical field -> ambiguous
            ambiguous[field] = matching_headers

    unmapped_required = [f for f in REQUIRED_FIELDS if f not in auto_mapping]
    unmapped_optional = [f for f in OPTIONAL_FIELDS if f not in auto_mapping]
    unmapped_columns = [h for h in headers if h not in mapped_headers]

    return {
        "auto_mapping": auto_mapping,
        "unmapped_required": unmapped_required,
        "unmapped_optional": unmapped_optional,
        "unmapped_columns": unmapped_columns,
        "ambiguous": ambiguous,
    }


def validate_manual_mapping(
    headers: List[str], mapping: Any
) -> Tuple[bool, Optional[str], Optional[Dict[str, str]]]:
    """
    Validates a manual column mapping against the uploaded CSV headers.

    Validation rules:
    - mapping must be a dict
    - all required logical fields must be present and non-empty
    - all logical fields must be valid known fields
    - all mapped source columns must actually exist in headers
    - two logical fields cannot use the same source column
    - optional fields may remain unmapped

    Returns:
        (is_valid: bool, error_message: Optional[str], normalized_mapping: Optional[dict])
    """
    if not isinstance(mapping, dict):
        return False, "Mapping must be a JSON object/dictionary.", None

    if not mapping:
        return False, "Mapping cannot be empty. Required fields must be provided.", None

    # 1. Check for unknown logical fields
    unknown_fields = [f for f in mapping.keys() if f not in ALL_LOGICAL_FIELDS]
    if unknown_fields:
        return (
            False,
            f"Invalid logical field(s): {', '.join(unknown_fields)}. "
            f"Allowed fields are: {', '.join(ALL_LOGICAL_FIELDS)}.",
            None,
        )

    # 2. Check that all required logical fields are mapped with non-empty values
    missing_required = [
        f for f in REQUIRED_FIELDS if f not in mapping or not str(mapping[f]).strip()
    ]
    if missing_required:
        return (
            False,
            f"Missing required logical field(s): {', '.join(missing_required)}.",
            None,
        )

    # 3. Check that mapped source columns actually exist in uploaded CSV headers
    headers_set = set(headers)
    for logical_field, source_col in mapping.items():
        if source_col not in headers_set:
            return (
                False,
                f"Source column '{source_col}' mapped to '{logical_field}' does not exist in the uploaded CSV headers.",
                None,
            )

    # 4. Check that two logical fields cannot incorrectly use the same source column
    source_cols = list(mapping.values())
    duplicates = [col for col in set(source_cols) if source_cols.count(col) > 1]
    if duplicates:
        return (
            False,
            f"Duplicate source column mapping: '{', '.join(duplicates)}' cannot be mapped to multiple logical fields.",
            None,
        )

    # Cleaned/normalized mapping with string values
    cleaned_mapping = {str(k): str(v) for k, v in mapping.items()}
    return True, None, cleaned_mapping
