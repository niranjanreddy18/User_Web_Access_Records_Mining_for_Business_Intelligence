import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone
import pandas as pd
from django.conf import settings
from django.test import TestCase
from processing.analytics import calculate_analytics
from processing.cleaning import clean_dataset
from processing.pattern_mining import mine_patterns
from processing.mapping import (
    COLUMN_ALIASES,
    REQUIRED_FIELDS,
    OPTIONAL_FIELDS,
    map_columns,
    normalize_name,
    validate_manual_mapping,
)
from processing.sessionization import sessionize_dataset
from processing.value_mapping import (
    ALLOWED_ACTIONS,
    ACTION_ALIASES,
    map_action_values,
    normalize_action_value,
    validate_manual_value_mapping,
)
from datasets.models import Dataset, Session


def clean_test_uploads():
    uploads_dir = os.path.join(settings.BASE_DIR, 'uploads')
    if os.path.exists(uploads_dir):
        for f in os.listdir(uploads_dir):
            if f.endswith('.csv'):
                try:
                    os.remove(os.path.join(uploads_dir, f))
                except OSError:
                    pass


class ColumnMappingUnitTests(TestCase):
    def test_exact_standard_column_names(self):
        """Test 1: Exact standard column names map directly to logical fields."""
        headers = ["user_id", "timestamp", "page_url", "action"]
        result = map_columns(headers)

        self.assertEqual(
            result["auto_mapping"],
            {
                "user_id": "user_id",
                "timestamp": "timestamp",
                "page_url": "page_url",
                "action": "action",
            }
        )
        self.assertEqual(result["unmapped_required"], [])
        self.assertEqual(set(result["unmapped_optional"]), set(OPTIONAL_FIELDS))
        self.assertEqual(result["unmapped_columns"], [])

    def test_known_aliases(self):
        """Test 2: Known alias names map to standard internal logical fields."""
        headers = ["customer_id", "time", "url", "event", "device_type"]
        result = map_columns(headers)

        self.assertEqual(
            result["auto_mapping"],
            {
                "user_id": "customer_id",
                "timestamp": "time",
                "page_url": "url",
                "action": "event",
                "device": "device_type",
            }
        )
        self.assertEqual(result["unmapped_required"], [])
        self.assertIn("session_id", result["unmapped_optional"])
        self.assertIn("referrer", result["unmapped_optional"])
        self.assertNotIn("device", result["unmapped_optional"])
        self.assertEqual(result["unmapped_columns"], [])

    def test_case_differences(self):
        """Test 3: Upper/mixed case headers map correctly."""
        headers = ["Customer_ID", "TIMESTAMP", "Page_URL", "Action"]
        result = map_columns(headers)

        self.assertEqual(
            result["auto_mapping"],
            {
                "user_id": "Customer_ID",
                "timestamp": "TIMESTAMP",
                "page_url": "Page_URL",
                "action": "Action",
            }
        )
        self.assertEqual(result["unmapped_required"], [])

    def test_spaces_and_underscores(self):
        """Test 4: Space-separated and hyphenated headers map cleanly."""
        headers = ["Customer ID", "Event Time", "Request Path", "Activity Type", "Session ID"]
        result = map_columns(headers)

        self.assertEqual(
            result["auto_mapping"],
            {
                "user_id": "Customer ID",
                "timestamp": "Event Time",
                "page_url": "Request Path",
                "action": "Activity Type",
                "session_id": "Session ID",
            }
        )
        self.assertEqual(result["unmapped_required"], [])
        self.assertNotIn("session_id", result["unmapped_optional"])

    def test_completely_unknown_column_names(self):
        """Test 5: Unknown column names are preserved in unmapped_columns without being blindly mapped."""
        headers = ["Browser", "ip_address", "random_score", "extra_notes"]
        result = map_columns(headers)

        self.assertEqual(result["auto_mapping"], {})
        self.assertEqual(set(result["unmapped_required"]), set(REQUIRED_FIELDS))
        self.assertEqual(result["unmapped_columns"], headers)

    def test_missing_required_fields(self):
        """Test 6: When input headers lack required fields, they appear in unmapped_required."""
        headers = ["Customer_ID", "Event Time", "URL", "Browser"]
        result = map_columns(headers)

        self.assertEqual(
            result["auto_mapping"],
            {
                "user_id": "Customer_ID",
                "timestamp": "Event Time",
                "page_url": "URL",
            }
        )
        self.assertEqual(result["unmapped_required"], ["action"])
        self.assertEqual(result["unmapped_columns"], ["Browser"])

    def test_ambiguous_mappings(self):
        """Test ambiguity detection when multiple input headers could match the same logical field."""
        headers = ["customer_id", "visitor_id", "time", "url", "action"]
        result = map_columns(headers)

        self.assertIn("user_id", result["ambiguous"])
        self.assertNotIn("user_id", result["auto_mapping"])
        self.assertIn("user_id", result["unmapped_required"])
        self.assertEqual(result["auto_mapping"]["timestamp"], "time")
        self.assertEqual(result["auto_mapping"]["page_url"], "url")
        self.assertEqual(result["auto_mapping"]["action"], "action")

    def test_validate_manual_mapping_helper(self):
        """Test validation rules for manual column mapping."""
        headers = ["col_user", "col_time", "col_page", "col_action", "col_extra"]

        valid_mapping = {
            "user_id": "col_user",
            "timestamp": "col_time",
            "page_url": "col_page",
            "action": "col_action",
        }
        is_valid, err, cleaned = validate_manual_mapping(headers, valid_mapping)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

        is_valid, err, _ = validate_manual_mapping(headers, {"user_id": "col_user"})
        self.assertFalse(is_valid)
        self.assertIn("Missing required logical field", err)

        invalid_col_mapping = valid_mapping.copy()
        invalid_col_mapping["user_id"] = "nonexistent_col"
        is_valid, err, _ = validate_manual_mapping(headers, invalid_col_mapping)
        self.assertFalse(is_valid)
        self.assertIn("does not exist in the uploaded CSV headers", err)

        dup_mapping = valid_mapping.copy()
        dup_mapping["action"] = "col_user"
        is_valid, err, _ = validate_manual_mapping(headers, dup_mapping)
        self.assertFalse(is_valid)
        self.assertIn("Duplicate source column mapping", err)


class ValueMappingUnitTests(TestCase):
    def test_exact_standard_action_values(self):
        """Test 1: Exact standard action values map directly to themselves."""
        values = ["page_view", "click", "search", "purchase", "login", "logout"]
        result = map_action_values(values)

        self.assertEqual(
            result["auto_mapping"],
            {
                "page_view": "page_view",
                "click": "click",
                "search": "search",
                "purchase": "purchase",
                "login": "login",
                "logout": "logout",
            }
        )
        self.assertEqual(result["unknown_values"], [])

    def test_known_aliases(self):
        """Test 2: Known action aliases map to standardized actions."""
        values = ["view", "link_click", "search_query", "ADD_CART", "sign_in"]
        result = map_action_values(values)

        self.assertEqual(
            result["auto_mapping"],
            {
                "view": "page_view",
                "link_click": "click",
                "search_query": "search",
                "ADD_CART": "add_to_cart",
                "sign_in": "login",
            }
        )
        self.assertEqual(result["unknown_values"], [])

    def test_case_differences(self):
        """Test 3: Case differences map correctly."""
        values = ["VIEW", "CLICK", "SEARCH", "PURCHASE", "LOGOUT"]
        result = map_action_values(values)

        self.assertEqual(
            result["auto_mapping"],
            {
                "VIEW": "page_view",
                "CLICK": "click",
                "SEARCH": "search",
                "PURCHASE": "purchase",
                "LOGOUT": "logout",
            }
        )
        self.assertEqual(result["unknown_values"], [])

    def test_spaces_hyphens_underscores(self):
        """Test 4: Space, hyphen, and underscore variations map cleanly."""
        values = ["page-view", "add cart", "sign in", "cart_remove", "order-completed"]
        result = map_action_values(values)

        self.assertEqual(
            result["auto_mapping"],
            {
                "page-view": "page_view",
                "add cart": "add_to_cart",
                "sign in": "login",
                "cart_remove": "remove_from_cart",
                "order-completed": "purchase",
            }
        )
        self.assertEqual(result["unknown_values"], [])

    def test_multiple_unique_action_values(self):
        """Test 5: Multiple unique action values with duplicates preserved in order."""
        values = ["VIEW", "click", "ADD_CART", "purchase", "hover_image", "VIEW", "click"]
        result = map_action_values(values)

        self.assertEqual(
            result["auto_mapping"],
            {
                "VIEW": "page_view",
                "click": "click",
                "ADD_CART": "add_to_cart",
                "purchase": "purchase",
            }
        )
        self.assertEqual(result["unknown_values"], ["hover_image"])

    def test_unknown_action_values(self):
        """Test 6: Unknown action values are returned as unknown without automatically mapping to 'other'."""
        values = ["hover_image", "scroll_down", "zoom_preview", "download_pdf"]
        result = map_action_values(values)

        self.assertEqual(result["auto_mapping"], {})
        self.assertEqual(
            result["unknown_values"],
            ["hover_image", "scroll_down", "zoom_preview", "download_pdf"]
        )

    def test_validate_manual_value_mapping_helper(self):
        """Test validate_manual_value_mapping helper function."""
        unique_vals = ["VIEW", "click", "hover_image"]
        auto_map = {"VIEW": "page_view", "click": "click"}

        is_valid, err, final_map = validate_manual_value_mapping(
            unique_action_values=unique_vals,
            user_mapping={"hover_image": "other"},
            auto_mapping=auto_map,
        )
        self.assertTrue(is_valid)
        self.assertEqual(
            final_map,
            {"VIEW": "page_view", "click": "click", "hover_image": "other"}
        )

        is_valid, err, _ = validate_manual_value_mapping(
            unique_action_values=unique_vals,
            user_mapping={"hover_image": "invalid_action_name"},
            auto_mapping=auto_map,
        )
        self.assertFalse(is_valid)
        self.assertIn("Invalid target action", err)

        is_valid, err, _ = validate_manual_value_mapping(
            unique_action_values=unique_vals,
            user_mapping={"unknown_nonexistent": "click"},
            auto_mapping=auto_map,
        )
        self.assertFalse(is_valid)
        self.assertIn("does not exist in the dataset's action column", err)

        is_valid, err, _ = validate_manual_value_mapping(
            unique_action_values=unique_vals,
            user_mapping={"VIEW": "page_view"},
            auto_mapping={},
        )
        self.assertFalse(is_valid)
        self.assertIn("Unmapped action value(s)", err)


class DataCleaningUnitTests(TestCase):
    def setUp(self):
        self.uploads_dir = os.path.join(settings.BASE_DIR, 'uploads')
        os.makedirs(self.uploads_dir, exist_ok=True)

    def tearDown(self):
        clean_test_uploads()

    def _create_dataset_with_csv(self, filename: str, content: str, col_mapping=None, val_mapping=None):
        job_id = uuid.uuid4()
        file_path = os.path.join(self.uploads_dir, f"{job_id}.csv")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return Dataset.objects.create(
            job_id=job_id,
            filename=filename,
            file_path=file_path,
            status=Dataset.STATUS_MAPPING,
            column_mapping=col_mapping if col_mapping is not None else {
                "user_id": "user_id",
                "timestamp": "timestamp",
                "page_url": "page_url",
                "action": "action",
            },
            value_mapping=val_mapping if val_mapping is not None else {
                "page_view": "page_view",
                "click": "click",
                "add_to_cart": "add_to_cart",
            },
        )

    def test_valid_standard_csv(self):
        """Test 1: Valid standard CSV is standardized cleanly without row losses."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "u1,2026-01-01 10:00:00,/home,page_view\n"
            "u2,2026-01-01 10:05:00,/shop,click\n"
        )
        dataset = self._create_dataset_with_csv("std.csv", content)
        df_clean, report = clean_dataset(dataset)

        self.assertEqual(len(df_clean), 2)
        self.assertEqual(report["rows_before"], 2)
        self.assertEqual(report["rows_after"], 2)
        self.assertEqual(report["rows_removed"], 0)
        self.assertEqual(list(df_clean.columns), ["user_id", "timestamp", "page_url", "action"])

    def test_csv_using_mapped_column_aliases(self):
        """Test 2: CSV with non-standard column aliases correctly renames to internal schema."""
        content = (
            "client_id,event_time,request_path,event_name\n"
            "c1,2026-01-01 12:00:00,/items,click\n"
            "c2,2026-01-01 12:01:00,/cart,add_to_cart\n"
        )
        col_mapping = {
            "user_id": "client_id",
            "timestamp": "event_time",
            "page_url": "request_path",
            "action": "event_name",
        }
        dataset = self._create_dataset_with_csv("alias.csv", content, col_mapping=col_mapping)
        df_clean, report = clean_dataset(dataset)

        self.assertEqual(len(df_clean), 2)
        self.assertEqual(list(df_clean.columns), ["user_id", "timestamp", "page_url", "action"])
        self.assertEqual(df_clean.iloc[0]["user_id"], "c1")
        self.assertEqual(df_clean.iloc[0]["page_url"], "/items")

    def test_action_values_using_aliases(self):
        """Test 3: Action values correctly transform using the dataset's value_mapping."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "u1,2026-01-01 10:00:00,/home,VIEW\n"
            "u2,2026-01-01 10:05:00,/cart,ADD_CART\n"
        )
        val_mapping = {
            "VIEW": "page_view",
            "ADD_CART": "add_to_cart",
        }
        dataset = self._create_dataset_with_csv("action_alias.csv", content, val_mapping=val_mapping)
        df_clean, report = clean_dataset(dataset)

        self.assertEqual(len(df_clean), 2)
        self.assertEqual(df_clean.iloc[0]["action"], "page_view")
        self.assertEqual(df_clean.iloc[1]["action"], "add_to_cart")

    def test_missing_user_id_rows(self):
        """Test 4: Rows with missing user_id are removed and tracked in quality report."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "u1,2026-01-01 10:00:00,/home,page_view\n"
            ",2026-01-01 10:01:00,/about,click\n"
            "   ,2026-01-01 10:02:00,/contact,click\n"
        )
        dataset = self._create_dataset_with_csv("missing_user.csv", content)
        df_clean, report = clean_dataset(dataset)

        self.assertEqual(len(df_clean), 1)
        self.assertEqual(report["rows_before"], 3)
        self.assertEqual(report["rows_after"], 1)
        self.assertEqual(report["missing_user_id"], 2)
        self.assertEqual(report["rows_removed"], 2)

    def test_invalid_timestamps(self):
        """Test 5: Rows with unparseable timestamps are dropped and counted as invalid_timestamp."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "u1,2026-01-01 10:00:00,/home,page_view\n"
            "u2,not-a-real-date,/shop,click\n"
            "u3,invalid_timestamp_string,/cart,add_to_cart\n"
        )
        dataset = self._create_dataset_with_csv("invalid_time.csv", content)
        df_clean, report = clean_dataset(dataset)

        self.assertEqual(len(df_clean), 1)
        self.assertEqual(report["invalid_timestamp"], 2)
        self.assertEqual(report["rows_after"], 1)

    def test_missing_timestamp_rows(self):
        """Test 6: Rows with empty or missing timestamps are counted as invalid_timestamp and removed."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "u1,2026-01-01 10:00:00,/home,page_view\n"
            "u2,,/shop,click\n"
        )
        dataset = self._create_dataset_with_csv("empty_time.csv", content)
        df_clean, report = clean_dataset(dataset)

        self.assertEqual(len(df_clean), 1)
        self.assertEqual(report["invalid_timestamp"], 1)
        self.assertEqual(report["rows_removed"], 1)

    def test_missing_page_url(self):
        """Test 7: Rows with missing page_url are removed and tracked in report."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "u1,2026-01-01 10:00:00,/home,page_view\n"
            "u2,2026-01-01 10:05:00,,click\n"
        )
        dataset = self._create_dataset_with_csv("missing_url.csv", content)
        df_clean, report = clean_dataset(dataset)

        self.assertEqual(len(df_clean), 1)
        self.assertEqual(report["missing_page_url"], 1)
        self.assertEqual(report["rows_after"], 1)

    def test_missing_action(self):
        """Test 8: Rows with missing or unmapped action are dropped and reported."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "u1,2026-01-01 10:00:00,/home,page_view\n"
            "u2,2026-01-01 10:05:00,/shop,\n"
            "u3,2026-01-01 10:06:00,/cart,unmapped_action\n"
        )
        dataset = self._create_dataset_with_csv("missing_action.csv", content)
        df_clean, report = clean_dataset(dataset)

        self.assertEqual(len(df_clean), 1)
        self.assertEqual(report["missing_action"], 2)
        self.assertEqual(report["rows_after"], 1)

    def test_exact_duplicate_rows(self):
        """Test 9: Exact duplicate rows are detected and removed."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "u1,2026-01-01 10:00:00,/home,page_view\n"
            "u1,2026-01-01 10:00:00,/home,page_view\n"
            "u2,2026-01-01 10:05:00,/shop,click\n"
        )
        dataset = self._create_dataset_with_csv("duplicates.csv", content)
        df_clean, report = clean_dataset(dataset)

        self.assertEqual(len(df_clean), 2)
        self.assertEqual(report["duplicate_rows"], 1)
        self.assertEqual(report["rows_removed"], 1)

    def test_quality_report_correctness(self):
        """Test 10: Verify quality report counts without double counting overlapping issues."""
        # Row 1: valid
        # Row 2: duplicate of row 1
        # Row 3: missing user_id AND missing page_url (overlapping)
        # Row 4: invalid timestamp
        content = (
            "user_id,timestamp,page_url,action\n"
            "u1,2026-01-01 10:00:00,/home,page_view\n"
            "u1,2026-01-01 10:00:00,/home,page_view\n"
            ",2026-01-01 10:01:00,,click\n"
            "u2,bad_timestamp,/shop,click\n"
        )
        dataset = self._create_dataset_with_csv("complex.csv", content)
        df_clean, report = clean_dataset(dataset)

        self.assertEqual(report["rows_before"], 4)
        self.assertEqual(report["rows_after"], 1)
        self.assertEqual(report["rows_removed"], 3)
        self.assertEqual(report["missing_user_id"], 1)
        self.assertEqual(report["missing_page_url"], 1)
        self.assertEqual(report["invalid_timestamp"], 1)
        self.assertEqual(report["duplicate_rows"], 1)

    def test_clean_dataset_missing_column_mapping(self):
        """Test 11: clean_dataset raises ValueError when column mapping is missing."""
        dataset = self._create_dataset_with_csv("nomap.csv", "a,b\n1,2", col_mapping={})
        with self.assertRaises(ValueError) as ctx:
            clean_dataset(dataset)
        self.assertIn("Column mapping", str(ctx.exception))

    def test_clean_dataset_missing_value_mapping(self):
        """Test 12: clean_dataset raises ValueError when value mapping is missing."""
        dataset = self._create_dataset_with_csv("noval.csv", "a,b\n1,2", val_mapping={})
        with self.assertRaises(ValueError) as ctx:
            clean_dataset(dataset)
        self.assertIn("Value mapping", str(ctx.exception))


class SessionizationUnitTests(TestCase):
    def setUp(self):
        self.uploads_dir = os.path.join(settings.BASE_DIR, "uploads")
        os.makedirs(self.uploads_dir, exist_ok=True)

    def tearDown(self):
        clean_test_uploads()

    def _create_cleaned_dataset(self, filename: str, cleaned_csv_content: str) -> Dataset:
        job_id = uuid.uuid4()
        cleaned_path = os.path.join(self.uploads_dir, f"cleaned_{job_id}.csv")
        with open(cleaned_path, "w", encoding="utf-8") as f:
            f.write(cleaned_csv_content)

        return Dataset.objects.create(
            job_id=job_id,
            filename=filename,
            cleaned_file_path=cleaned_path,
            status=Dataset.STATUS_COMPLETED,
        )

    def test_single_user_within_30_minutes_one_session(self):
        """Test 1: Single user with consecutive gaps <= 30 min stays in one session even if total > 30m."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "U101,2026-01-01 10:00:00,/home,page_view\n"
            "U101,2026-01-01 10:05:00,/products,click\n"
            "U101,2026-01-01 10:20:00,/cart,add_to_cart\n"
            "U101,2026-01-01 10:50:00,/checkout,purchase\n"
        )
        dataset = self._create_cleaned_dataset("u101.csv", content)
        df_sess, summary = sessionize_dataset(dataset)

        self.assertEqual(summary["total_sessions"], 1)
        self.assertEqual(summary["total_users"], 1)
        self.assertEqual(summary["timeout_minutes"], 30)
        sessions = Session.objects.filter(dataset=dataset)
        self.assertEqual(sessions.count(), 1)
        s = sessions.first()
        self.assertEqual(s.event_count, 4)
        self.assertEqual(s.duration, timedelta(minutes=50))

    def test_gap_exactly_30_minutes_same_session(self):
        """Test 2: Gap of exactly 30 minutes stays in the same session."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "U101,2026-01-01 10:00:00,/home,page_view\n"
            "U101,2026-01-01 10:30:00,/products,click\n"
        )
        dataset = self._create_cleaned_dataset("exact30.csv", content)
        df_sess, summary = sessionize_dataset(dataset, timeout_minutes=30)

        self.assertEqual(summary["total_sessions"], 1)
        s = Session.objects.get(dataset=dataset)
        self.assertEqual(s.event_count, 2)
        self.assertEqual(s.duration, timedelta(minutes=30))

    def test_gap_greater_than_30_minutes_new_session(self):
        """Test 3: Gap > 30 minutes starts a new session."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "U101,2026-01-01 10:00:00,/home,page_view\n"
            "U101,2026-01-01 10:20:00,/cart,add_to_cart\n"
            "U101,2026-01-01 10:55:00,/home,page_view\n"
        )
        dataset = self._create_cleaned_dataset("gap35.csv", content)
        df_sess, summary = sessionize_dataset(dataset)

        self.assertEqual(summary["total_sessions"], 2)
        sessions = list(Session.objects.filter(dataset=dataset).order_by("start_time"))
        self.assertEqual(sessions[0].event_count, 2)
        self.assertEqual(sessions[0].duration, timedelta(minutes=20))
        self.assertEqual(sessions[1].event_count, 1)
        self.assertEqual(sessions[1].duration, timedelta(0))

    def test_multiple_users_independent_sessions(self):
        """Test 4: Sessions are calculated independently per user."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "U1,2026-01-01 10:00:00,/home,page_view\n"
            "U2,2026-01-01 10:02:00,/home,page_view\n"
            "U1,2026-01-01 10:15:00,/shop,click\n"
            "U2,2026-01-01 10:45:00,/cart,add_to_cart\n"
        )
        dataset = self._create_cleaned_dataset("multi.csv", content)
        df_sess, summary = sessionize_dataset(dataset)

        # U1 has 1 session (10:00, 10:15); U2 has 2 sessions (10:02 and 10:45 -> 43m gap)
        self.assertEqual(summary["total_sessions"], 3)
        self.assertEqual(summary["total_users"], 2)
        self.assertEqual(Session.objects.filter(dataset=dataset, user_id="U1").count(), 1)
        self.assertEqual(Session.objects.filter(dataset=dataset, user_id="U2").count(), 2)

    def test_events_sorted_by_timestamp(self):
        """Test 5: Unordered input events are sorted chronologically before sessionizing."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "U1,2026-01-01 10:25:00,/checkout,purchase\n"
            "U1,2026-01-01 10:00:00,/home,page_view\n"
            "U1,2026-01-01 10:10:00,/products,click\n"
        )
        dataset = self._create_cleaned_dataset("unsorted.csv", content)
        df_sess, summary = sessionize_dataset(dataset)

        self.assertEqual(summary["total_sessions"], 1)
        s = Session.objects.get(dataset=dataset)
        self.assertEqual(s.start_time, datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(s.end_time, datetime(2026, 1, 1, 10, 25, 0, tzinfo=timezone.utc))
        self.assertEqual(s.duration, timedelta(minutes=25))
        # Verify dataframe order
        self.assertEqual(list(df_sess["page_url"]), ["/home", "/products", "/checkout"])

    def test_session_ids_unique_and_per_dataset(self):
        """Test 6: Generated session IDs are unique per dataset and not shared globally."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "U1,2026-01-01 10:00:00,/home,page_view\n"
            "U1,2026-01-01 11:00:00,/home,page_view\n"
        )
        ds_a = self._create_cleaned_dataset("a.csv", content)
        ds_b = self._create_cleaned_dataset("b.csv", content)

        df_a, _ = sessionize_dataset(ds_a)
        df_b, _ = sessionize_dataset(ds_b)

        sids_a = list(Session.objects.filter(dataset=ds_a).order_by("start_time").values_list("session_id", flat=True))
        sids_b = list(Session.objects.filter(dataset=ds_b).order_by("start_time").values_list("session_id", flat=True))

        self.assertEqual(sids_a, [f"{ds_a.job_id}-S0001", f"{ds_a.job_id}-S0002"])
        self.assertEqual(sids_b, [f"{ds_b.job_id}-S0001", f"{ds_b.job_id}-S0002"])
        self.assertEqual(len(set(sids_a)), 2)

    def test_session_metrics_start_end_duration_event_count_and_single_event_zero_duration(self):
        """Tests 7, 8, 9, 10, 11: Verify event_count, start_time, end_time, duration, and 0-duration single-event."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "U1,2026-01-01 09:00:00,/a,page_view\n"
            "U1,2026-01-01 09:05:00,/b,click\n"
            "U1,2026-01-01 09:20:00,/c,purchase\n"
            "U1,2026-01-01 12:00:00,/d,page_view\n"
        )
        dataset = self._create_cleaned_dataset("metrics.csv", content)
        sessionize_dataset(dataset)

        sessions = list(Session.objects.filter(dataset=dataset).order_by("start_time"))
        self.assertEqual(len(sessions), 2)

        # First session (3 events)
        self.assertEqual(sessions[0].event_count, 3)
        self.assertEqual(sessions[0].start_time, datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(sessions[0].end_time, datetime(2026, 1, 1, 9, 20, 0, tzinfo=timezone.utc))
        self.assertEqual(sessions[0].duration, timedelta(minutes=20))

        # Second session (1 event -> duration 0)
        self.assertEqual(sessions[1].event_count, 1)
        self.assertEqual(sessions[1].start_time, datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(sessions[1].end_time, datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(sessions[1].duration, timedelta(0))

    def test_custom_timeout_works(self):
        """Test 13: Custom timeout_minutes overrides default 30 minutes."""
        content = (
            "user_id,timestamp,page_url,action\n"
            "U1,2026-01-01 10:00:00,/a,page_view\n"
            "U1,2026-01-01 10:15:00,/b,click\n"
        )
        dataset = self._create_cleaned_dataset("custom.csv", content)

        # With timeout=10 minutes, 15 min gap -> 2 sessions
        _, summary = sessionize_dataset(dataset, timeout_minutes=10)
        self.assertEqual(summary["timeout_minutes"], 10)
        self.assertEqual(summary["total_sessions"], 2)

    def test_existing_session_id_policy(self):
        """Test 16: Preserve non-empty existing session_id and generate IDs for missing ones."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,EXT-100\n"
            "U1,2026-01-01 10:05:00,/shop,click,EXT-100\n"
            "U2,2026-01-01 10:10:00,/home,page_view,\n"
            "U2,2026-01-01 10:15:00,/cart,add_to_cart,\n"
        )
        dataset = self._create_cleaned_dataset("existing_sid.csv", content)
        df_sess, summary = sessionize_dataset(dataset)

        self.assertEqual(summary["total_sessions"], 2)
        u1_sess = Session.objects.get(dataset=dataset, user_id="U1")
        self.assertEqual(u1_sess.session_id, "EXT-100")
        self.assertEqual(u1_sess.event_count, 2)

        u2_sess = Session.objects.get(dataset=dataset, user_id="U2")
        self.assertEqual(u2_sess.session_id, f"{dataset.job_id}-S0001")
        self.assertEqual(u2_sess.event_count, 2)

    def test_sessionized_csv_saved_and_contains_session_id(self):
        """Tests 18, 19: Sessionized CSV contains session_id and dataset.sessionized_file_path is saved."""
        content = (
            "user_id,timestamp,page_url,action,device\n"
            "U1,2026-01-01 10:00:00,/home,page_view,mobile\n"
        )
        dataset = self._create_cleaned_dataset("save_check.csv", content)
        sessionize_dataset(dataset)

        dataset.refresh_from_db()
        self.assertTrue(dataset.sessionized_file_path)
        self.assertTrue(os.path.exists(dataset.sessionized_file_path))

        saved_df = pd.read_csv(dataset.sessionized_file_path)
        self.assertIn("session_id", saved_df.columns)
        self.assertIn("device", saved_df.columns)
        self.assertEqual(saved_df.iloc[0]["session_id"], f"{dataset.job_id}-S0001")


class AnalyticsUnitTests(TestCase):
    def setUp(self):
        self.uploads_dir = os.path.join(settings.BASE_DIR, "uploads")
        os.makedirs(self.uploads_dir, exist_ok=True)

    def tearDown(self):
        clean_test_uploads()

    def _create_sessionized_dataset(self, filename: str, csv_content: str) -> Dataset:
        job_id = uuid.uuid4()
        sessionized_path = os.path.join(self.uploads_dir, f"sessionized_{job_id}.csv")
        with open(sessionized_path, "w", encoding="utf-8") as f:
            f.write(csv_content)

        return Dataset.objects.create(
            job_id=job_id,
            filename=filename,
            sessionized_file_path=sessionized_path,
            status=Dataset.STATUS_COMPLETED,
        )

    def test_total_users_and_sessions_and_events(self):
        """Test 1: Computes unique users, unique sessions, and total events."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,S1\n"
            "U1,2026-01-01 10:02:00,/shop,click,S1\n"
            "U2,2026-01-01 11:00:00,/home,page_view,S2\n"
        )
        dataset = self._create_sessionized_dataset("totals.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(result["total_users"], 2)
        self.assertEqual(result["total_sessions"], 2)
        self.assertEqual(result["total_events"], 3)

    def test_average_session_duration_single_and_multi_event(self):
        """Test 2: Computes average_session_duration in float seconds across sessions."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,S1\n"
            "U1,2026-01-01 10:02:00,/shop,page_view,S1\n"
            "U2,2026-01-01 11:00:00,/about,page_view,S2\n"
        )
        dataset = self._create_sessionized_dataset("duration.csv", content)
        result = calculate_analytics(dataset)

        # S1 = 120s, S2 = 0s => mean = 60.0s
        self.assertEqual(result["average_session_duration"], 60.0)
        self.assertIsInstance(result["average_session_duration"], float)

    def test_average_events_per_session(self):
        """Test 3: Computes average_events_per_session accurately."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,S1\n"
            "U1,2026-01-01 10:01:00,/home,click,S1\n"
            "U1,2026-01-01 10:02:00,/cart,add_to_cart,S1\n"
            "U2,2026-01-01 11:00:00,/home,page_view,S2\n"
        )
        dataset = self._create_sessionized_dataset("avg_events.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(result["average_events_per_session"], 2.0)

    def test_average_pages_per_session_counts_only_page_view(self):
        """Test 4: Computes average_pages_per_session counting only action=='page_view'."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,S1\n"
            "U1,2026-01-01 10:01:00,/home,click,S1\n"
            "U1,2026-01-01 10:02:00,/shop,page_view,S1\n"
            "U2,2026-01-01 11:00:00,/home,page_view,S2\n"
        )
        dataset = self._create_sessionized_dataset("avg_pages.csv", content)
        result = calculate_analytics(dataset)

        # 3 page_views across 2 sessions => 1.5
        self.assertEqual(result["average_pages_per_session"], 1.5)

    def test_most_visited_pages_top_10_from_page_views(self):
        """Test 5: Returns top 10 most_visited_pages descending from page_view actions."""
        rows = ["user_id,timestamp,page_url,action,session_id"]
        for i in range(1, 13):
            for visit in range(i):
                rows.append(f"U1,2026-01-01 10:00:{visit:02d},/p{i},page_view,S1")
        # Non-page_view events on /ignored should not appear in page_view rankings
        for j in range(20):
            rows.append(f"U1,2026-01-01 11:00:{j:02d},/ignored,click,S1")

        dataset = self._create_sessionized_dataset("top_pages.csv", "\n".join(rows))
        result = calculate_analytics(dataset)

        most = result["most_visited_pages"]
        self.assertEqual(len(most), 10)
        self.assertEqual(most[0], {"page_url": "/p12", "visits": 12})
        self.assertEqual(most[-1], {"page_url": "/p3", "visits": 3})
        self.assertNotIn("/ignored", [p["page_url"] for p in most])

    def test_least_visited_pages_bottom_10_from_page_views(self):
        """Test 6: Returns bottom 10 least_visited_pages ascending from page_view actions."""
        rows = ["user_id,timestamp,page_url,action,session_id"]
        for i in range(1, 13):
            for visit in range(i):
                rows.append(f"U1,2026-01-01 10:00:{visit:02d},/p{i},page_view,S1")

        dataset = self._create_sessionized_dataset("least_pages.csv", "\n".join(rows))
        result = calculate_analytics(dataset)

        least = result["least_visited_pages"]
        self.assertEqual(len(least), 10)
        self.assertEqual(least[0], {"page_url": "/p1", "visits": 1})
        self.assertEqual(least[-1], {"page_url": "/p10", "visits": 10})

    def test_page_rankings_fewer_than_10_pages(self):
        """Test 7: When fewer than 10 pages exist, returns all available pages."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/a,page_view,S1\n"
            "U1,2026-01-01 10:01:00,/a,page_view,S1\n"
            "U1,2026-01-01 10:02:00,/b,page_view,S1\n"
        )
        dataset = self._create_sessionized_dataset("few_pages.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(
            result["most_visited_pages"],
            [{"page_url": "/a", "visits": 2}, {"page_url": "/b", "visits": 1}],
        )
        self.assertEqual(
            result["least_visited_pages"],
            [{"page_url": "/b", "visits": 1}, {"page_url": "/a", "visits": 2}],
        )

    def test_no_page_view_actions_returns_empty_pages_and_zero_avg_pages(self):
        """Test 8: Handles datasets containing no page_view actions gracefully."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/btn,click,S1\n"
            "U1,2026-01-01 10:01:00,/checkout,purchase,S1\n"
        )
        dataset = self._create_sessionized_dataset("no_pv.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(result["most_visited_pages"], [])
        self.assertEqual(result["least_visited_pages"], [])
        self.assertEqual(result["average_pages_per_session"], 0.0)
        self.assertEqual(result["action_counts"], {"click": 1, "purchase": 1})

    def test_action_counts_breakdown(self):
        """Test 9: Computes action_counts including standard and other actions."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,S1\n"
            "U1,2026-01-01 10:01:00,/home,page_view,S1\n"
            "U1,2026-01-01 10:02:00,/cart,add_to_cart,S1\n"
            "U1,2026-01-01 10:03:00,/misc,other,S1\n"
        )
        dataset = self._create_sessionized_dataset("actions.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(
            result["action_counts"],
            {"page_view": 2, "add_to_cart": 1, "other": 1},
        )

    def test_traffic_by_hour_always_24_buckets(self):
        """Test 10: traffic_by_hour always includes all 24 hours 0..23."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 00:15:00,/home,page_view,S1\n"
            "U1,2026-01-01 23:45:00,/end,page_view,S2\n"
        )
        dataset = self._create_sessionized_dataset("hours.csv", content)
        result = calculate_analytics(dataset)

        hourly = result["traffic_by_hour"]
        self.assertEqual(len(hourly), 24)
        self.assertEqual(hourly[0], {"hour": 0, "events": 1})
        self.assertEqual(hourly[12], {"hour": 12, "events": 0})
        self.assertEqual(hourly[23], {"hour": 23, "events": 1})

    def test_peak_traffic_hour_calculation(self):
        """Test 11: Identifies peak_traffic_hour with the highest event count."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 09:00:00,/a,page_view,S1\n"
            "U1,2026-01-01 14:00:00,/a,page_view,S2\n"
            "U2,2026-01-01 14:30:00,/b,click,S3\n"
            "U3,2026-01-01 14:45:00,/c,page_view,S4\n"
        )
        dataset = self._create_sessionized_dataset("peak.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(result["peak_traffic_hour"], 14)

    def test_traffic_by_day_sorted_dates(self):
        """Test 12: Aggregates traffic_by_day chronologically by YYYY-MM-DD."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-03 10:00:00,/a,page_view,S1\n"
            "U2,2026-01-01 10:00:00,/b,page_view,S2\n"
            "U2,2026-01-01 10:05:00,/c,click,S2\n"
        )
        dataset = self._create_sessionized_dataset("days.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(
            result["traffic_by_day"],
            [
                {"date": "2026-01-01", "events": 2},
                {"date": "2026-01-03", "events": 1},
            ],
        )

    def test_device_counts_when_device_column_present(self):
        """Test 13: Computes device_counts when optional device column exists."""
        content = (
            "user_id,timestamp,page_url,action,session_id,device\n"
            "U1,2026-01-01 10:00:00,/a,page_view,S1,mobile\n"
            "U1,2026-01-01 10:01:00,/b,click,S1,mobile\n"
            "U2,2026-01-01 11:00:00,/a,page_view,S2,desktop\n"
        )
        dataset = self._create_sessionized_dataset("devices.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(result["device_counts"], {"mobile": 2, "desktop": 1})

    def test_device_counts_when_device_column_missing(self):
        """Test 14: Returns empty dict for device_counts if device column is absent."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/a,page_view,S1\n"
        )
        dataset = self._create_sessionized_dataset("no_device.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(result["device_counts"], {})

    def test_entry_and_exit_pages_respect_timestamp_order(self):
        """Test 15: Entry and exit pages come from earliest/latest timestamp per session."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:10:00,/checkout,purchase,S1\n"
            "U1,2026-01-01 10:00:00,/landing,page_view,S1\n"
            "U1,2026-01-01 10:05:00,/product,page_view,S1\n"
            "U2,2026-01-01 11:00:00,/landing,page_view,S2\n"
            "U2,2026-01-01 11:05:00,/cart,add_to_cart,S2\n"
        )
        dataset = self._create_sessionized_dataset("entry_exit.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(result["entry_pages"], {"/landing": 2})
        self.assertEqual(result["exit_pages"], {"/checkout": 1, "/cart": 1})

    def test_single_event_session_entry_and_exit_page(self):
        """Test 16: Single-event session uses same page for entry and exit with 0 duration."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/only,page_view,S1\n"
        )
        dataset = self._create_sessionized_dataset("single.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(result["average_session_duration"], 0.0)
        self.assertEqual(result["entry_pages"], {"/only": 1})
        self.assertEqual(result["exit_pages"], {"/only": 1})

    def test_multiple_sessions_per_user_and_multiple_users(self):
        """Test 17: Correctly distinguishes multiple sessions belonging to the same user."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,U1-S1\n"
            "U1,2026-01-01 10:01:00,/shop,page_view,U1-S1\n"
            "U1,2026-01-01 15:00:00,/cart,page_view,U1-S2\n"
            "U2,2026-01-01 16:00:00,/home,page_view,U2-S1\n"
        )
        dataset = self._create_sessionized_dataset("multi_sess.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(result["total_users"], 2)
        self.assertEqual(result["total_sessions"], 3)
        self.assertEqual(result["total_events"], 4)
        self.assertEqual(result["average_session_duration"], 20.0)

    def test_empty_sessionized_csv_returns_safe_defaults(self):
        """Test 18: Empty sessionized CSV (headers only) returns zeroed metrics cleanly."""
        content = "user_id,timestamp,page_url,action,session_id\n"
        dataset = self._create_sessionized_dataset("empty.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(result["total_users"], 0)
        self.assertEqual(result["total_sessions"], 0)
        self.assertEqual(result["total_events"], 0)
        self.assertEqual(result["average_session_duration"], 0.0)
        self.assertEqual(result["most_visited_pages"], [])
        self.assertEqual(result["least_visited_pages"], [])
        self.assertEqual(result["action_counts"], {})
        self.assertEqual(len(result["traffic_by_hour"]), 24)
        self.assertIsNone(result["peak_traffic_hour"])
        self.assertEqual(result["traffic_by_day"], [])
        self.assertEqual(result["device_counts"], {})
        self.assertEqual(result["entry_pages"], {})
        self.assertEqual(result["exit_pages"], {})

    def test_invalid_timestamps_dropped_safely(self):
        """Test 19: Rows with invalid timestamps are ignored without crashing."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,not-a-timestamp,/bad,page_view,S1\n"
            "U1,2026-01-01 10:00:00,/good,page_view,S1\n"
        )
        dataset = self._create_sessionized_dataset("bad_ts.csv", content)
        result = calculate_analytics(dataset)

        self.assertEqual(result["total_events"], 1)
        self.assertEqual(result["most_visited_pages"], [{"page_url": "/good", "visits": 1}])

    def test_missing_sessionized_file_raises_file_not_found(self):
        """Test 20: Raises FileNotFoundError when sessionized file path is missing."""
        dataset = Dataset.objects.create(
            filename="missing.csv",
            sessionized_file_path="",
            status=Dataset.STATUS_COMPLETED,
        )
        with self.assertRaises(FileNotFoundError):
            calculate_analytics(dataset)

    def test_missing_required_columns_raises_value_error(self):
        """Test 21: Raises ValueError when required columns are missing from CSV."""
        content = "user_id,timestamp,page_url,action\nU1,2026-01-01 10:00:00,/a,page_view\n"
        dataset = self._create_sessionized_dataset("missing_col.csv", content)
        with self.assertRaises(ValueError) as ctx:
            calculate_analytics(dataset)
        self.assertIn("session_id", str(ctx.exception))


class PatternMiningUnitTests(TestCase):
    def setUp(self):
        self.uploads_dir = os.path.join(settings.BASE_DIR, "uploads")
        os.makedirs(self.uploads_dir, exist_ok=True)

    def tearDown(self):
        clean_test_uploads()

    def _create_sessionized_dataset(self, filename: str, csv_content: str) -> Dataset:
        job_id = uuid.uuid4()
        sessionized_path = os.path.join(self.uploads_dir, f"sessionized_{job_id}.csv")
        with open(sessionized_path, "w", encoding="utf-8") as f:
            f.write(csv_content)

        return Dataset.objects.create(
            job_id=job_id,
            filename=filename,
            sessionized_file_path=sessionized_path,
            status=Dataset.STATUS_COMPLETED,
        )

    def test_two_event_pattern_detection(self):
        """Test 1: Detects length-2 sequential page patterns accurately."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,S1\n"
            "U1,2026-01-01 10:01:00,/products,page_view,S1\n"
        )
        dataset = self._create_sessionized_dataset("pm_len2.csv", content)
        res = mine_patterns(dataset, min_support=0.5, max_pattern_length=2)

        self.assertEqual(
            res["page_patterns"],
            [{"pattern": ["/home", "/products"], "length": 2, "session_count": 1, "support": 1.0}],
        )

    def test_three_event_pattern_detection(self):
        """Test 2: Detects length-3 sequential patterns sorted by support desc, length desc."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,S1\n"
            "U1,2026-01-01 10:01:00,/products,page_view,S1\n"
            "U1,2026-01-01 10:02:00,/cart,add_to_cart,S1\n"
        )
        dataset = self._create_sessionized_dataset("pm_len3.csv", content)
        res = mine_patterns(dataset, min_support=0.5, max_pattern_length=3)

        patterns = [p["pattern"] for p in res["page_patterns"]]
        self.assertEqual(patterns[0], ["/home", "/products", "/cart"])
        self.assertIn(["/home", "/products"], patterns)
        self.assertIn(["/products", "/cart"], patterns)

    def test_min_support_filtering(self):
        """Test 3: Filters out patterns below min_support threshold."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,S1\n"
            "U1,2026-01-01 10:01:00,/cart,page_view,S1\n"
            "U2,2026-01-01 11:00:00,/home,page_view,S2\n"
            "U2,2026-01-01 11:01:00,/blog,page_view,S2\n"
            "U3,2026-01-01 12:00:00,/home,page_view,S3\n"
            "U3,2026-01-01 12:01:00,/blog,page_view,S3\n"
            "U4,2026-01-01 13:00:00,/about,page_view,S4\n"
            "U4,2026-01-01 13:01:00,/contact,page_view,S4\n"
        )
        dataset = self._create_sessionized_dataset("pm_filter.csv", content)
        res = mine_patterns(dataset, min_support=0.5, max_pattern_length=2)

        self.assertEqual(
            res["page_patterns"],
            [{"pattern": ["/home", "/blog"], "length": 2, "session_count": 2, "support": 0.5}],
        )

    def test_support_calculation_and_sorting(self):
        """Test 4: Computes support = session_count / total_sessions with deterministic sorting."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/a,page_view,S1\n"
            "U1,2026-01-01 10:01:00,/b,page_view,S1\n"
            "U2,2026-01-01 11:00:00,/c,page_view,S2\n"
            "U2,2026-01-01 11:01:00,/d,page_view,S2\n"
            "U3,2026-01-01 12:00:00,/e,page_view,S3\n"
            "U3,2026-01-01 12:01:00,/f,page_view,S3\n"
            "U4,2026-01-01 13:00:00,/a,page_view,S4\n"
            "U4,2026-01-01 13:01:00,/b,page_view,S4\n"
        )
        dataset = self._create_sessionized_dataset("pm_support.csv", content)
        res = mine_patterns(dataset, min_support=0.25, max_pattern_length=2)

        self.assertEqual(
            res["page_patterns"][0],
            {"pattern": ["/a", "/b"], "length": 2, "session_count": 2, "support": 0.5},
        )
        # Remaining tied patterns ordered lexically
        tied = [p["pattern"] for p in res["page_patterns"][1:]]
        self.assertEqual(tied, [["/c", "/d"], ["/e", "/f"]])

    def test_unique_session_counting_across_repeated_patterns_in_same_session(self):
        """Tests 5 & 6: A pattern repeated inside one session counts only once toward support."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/a,page_view,S1\n"
            "U1,2026-01-01 10:01:00,/b,page_view,S1\n"
            "U1,2026-01-01 10:02:00,/a,page_view,S1\n"
            "U1,2026-01-01 10:03:00,/b,page_view,S1\n"
            "U2,2026-01-01 11:00:00,/x,page_view,S2\n"
            "U2,2026-01-01 11:01:00,/y,page_view,S2\n"
        )
        dataset = self._create_sessionized_dataset("pm_intra.csv", content)
        res = mine_patterns(dataset, min_support=0.1, max_pattern_length=2)

        ab_pattern = next(p for p in res["page_patterns"] if p["pattern"] == ["/a", "/b"])
        self.assertEqual(ab_pattern["session_count"], 1)
        self.assertEqual(ab_pattern["support"], 0.5)

    def test_multiple_users_and_multiple_sessions_per_user(self):
        """Tests 7 & 8: Handles multiple users and multiple sessions for one user independently."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,U1-S1\n"
            "U1,2026-01-01 10:01:00,/shop,page_view,U1-S1\n"
            "U1,2026-01-01 14:00:00,/home,page_view,U1-S2\n"
            "U1,2026-01-01 14:01:00,/shop,page_view,U1-S2\n"
            "U2,2026-01-01 15:00:00,/home,page_view,U2-S1\n"
            "U2,2026-01-01 15:01:00,/shop,page_view,U2-S1\n"
        )
        dataset = self._create_sessionized_dataset("pm_multi.csv", content)
        res = mine_patterns(dataset, min_support=0.1, max_pattern_length=2)

        self.assertEqual(
            res["page_patterns"],
            [{"pattern": ["/home", "/shop"], "length": 2, "session_count": 3, "support": 1.0}],
        )

    def test_sessions_kept_separate_no_cross_session_pattern(self):
        """Test 9: Adjacent events across different sessions never form a pattern."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/end_of_s1,page_view,S1\n"
            "U1,2026-01-01 11:00:00,/start_of_s2,page_view,S2\n"
        )
        dataset = self._create_sessionized_dataset("pm_sep.csv", content)
        res = mine_patterns(dataset, min_support=0.1, max_pattern_length=3)

        self.assertEqual(res["page_patterns"], [])
        self.assertEqual(res["transitions"], [])

    def test_chronological_ordering_respected(self):
        """Test 10: Unsorted CSV rows are sorted chronologically per session before mining."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:05:00,/checkout,purchase,S1\n"
            "U1,2026-01-01 10:00:00,/home,page_view,S1\n"
            "U1,2026-01-01 10:02:00,/cart,add_to_cart,S1\n"
        )
        dataset = self._create_sessionized_dataset("pm_chrono.csv", content)
        res = mine_patterns(dataset, min_support=0.5, max_pattern_length=3)

        self.assertEqual(
            res["page_patterns"][0]["pattern"],
            ["/home", "/cart", "/checkout"],
        )

    def test_max_pattern_length_limits_and_exceeding_session_length(self):
        """Test 11: Respects max_pattern_length cap and safely handles values longer than sessions."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/a,page_view,S1\n"
            "U1,2026-01-01 10:01:00,/b,click,S1\n"
            "U1,2026-01-01 10:02:00,/c,add_to_cart,S1\n"
            "U1,2026-01-01 10:03:00,/d,purchase,S1\n"
        )
        dataset = self._create_sessionized_dataset("pm_maxlen.csv", content)

        res_cap2 = mine_patterns(dataset, min_support=0.5, max_pattern_length=2)
        self.assertTrue(all(p["length"] <= 2 for p in res_cap2["page_patterns"]))

        res_cap10 = mine_patterns(dataset, min_support=0.5, max_pattern_length=10)
        self.assertEqual(max(p["length"] for p in res_cap10["page_patterns"]), 4)

    def test_consecutive_duplicate_pages_collapsed_but_non_consecutive_kept(self):
        """Test 12: Consecutive duplicate pages collapse while /home -> /products -> /home stays."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,S1\n"
            "U1,2026-01-01 10:00:30,/home,click,S1\n"
            "U1,2026-01-01 10:01:00,/products,page_view,S1\n"
            "U1,2026-01-01 10:02:00,/home,page_view,S1\n"
        )
        dataset = self._create_sessionized_dataset("pm_dedup.csv", content)
        res = mine_patterns(dataset, min_support=0.5, max_pattern_length=3)

        patterns = [p["pattern"] for p in res["page_patterns"]]
        self.assertIn(["/home", "/products", "/home"], patterns)
        self.assertNotIn(["/home", "/home"], patterns)

    def test_action_patterns_and_no_page_view_events(self):
        """Test 13: Computes action_patterns properly even without page_view events."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/p1,click,S1\n"
            "U1,2026-01-01 10:01:00,/p2,add_to_cart,S1\n"
            "U1,2026-01-01 10:02:00,/p3,purchase,S1\n"
            "U2,2026-01-01 11:00:00,/p1,click,S2\n"
            "U2,2026-01-01 11:01:00,/p2,add_to_cart,S2\n"
        )
        dataset = self._create_sessionized_dataset("pm_actions.csv", content)
        res = mine_patterns(dataset, min_support=0.5, max_pattern_length=3)

        action_list = [p["pattern"] for p in res["action_patterns"]]
        self.assertEqual(action_list[0], ["click", "add_to_cart"])
        self.assertIn(["click", "add_to_cart", "purchase"], action_list)

    def test_transitions_transition_count_vs_unique_sessions_and_top_20(self):
        """Test 14: Transitions track transition_count vs unique_sessions separately and cap at 20."""
        rows = ["user_id,timestamp,page_url,action,session_id"]
        # S1 repeats /a -> /b twice
        rows.extend([
            "U1,2026-01-01 10:00:00,/a,page_view,S1",
            "U1,2026-01-01 10:01:00,/b,page_view,S1",
            "U1,2026-01-01 10:02:00,/a,page_view,S1",
            "U1,2026-01-01 10:03:00,/b,page_view,S1",
        ])
        # 25 additional sessions creating 25 other transitions
        for i in range(1, 26):
            rows.append(f"U{i+1},2026-01-01 11:{i:02d}:00,/x{i},page_view,SX{i}")
            rows.append(f"U{i+1},2026-01-01 11:{i:02d}:30,/y{i},page_view,SX{i}")

        dataset = self._create_sessionized_dataset("pm_trans.csv", "\n".join(rows))
        res = mine_patterns(dataset, min_support=0.01, max_pattern_length=2)

        transitions = res["transitions"]
        self.assertEqual(len(transitions), 20)
        ab = next(t for t in transitions if t["from"] == "/a" and t["to"] == "/b")
        self.assertEqual(ab["transition_count"], 2)
        self.assertEqual(ab["unique_sessions"], 1)
        self.assertEqual(ab["support"], round(1 / 26, 4))

    def test_common_journeys_derived_and_limited_to_20(self):
        """Test 15: common_journeys mirrors top 20 page_patterns with length >= 2."""
        rows = ["user_id,timestamp,page_url,action,session_id"]
        for i in range(1, 26):
            rows.append(f"U1,2026-01-01 10:{i:02d}:00,/p{i},page_view,S1")

        dataset = self._create_sessionized_dataset("pm_journeys.csv", "\n".join(rows))
        res = mine_patterns(dataset, min_support=0.5, max_pattern_length=2)

        self.assertGreater(len(res["page_patterns"]), 20)
        self.assertEqual(len(res["common_journeys"]), 20)
        self.assertEqual(res["common_journeys"], res["page_patterns"][:20])

    def test_empty_dataset_and_invalid_timestamps(self):
        """Test 16: Empty CSV and invalid-timestamp-only CSV return empty lists without error."""
        empty_ds = self._create_sessionized_dataset(
            "pm_empty.csv",
            "user_id,timestamp,page_url,action,session_id\n",
        )
        self.assertEqual(
            mine_patterns(empty_ds),
            {"page_patterns": [], "action_patterns": [], "transitions": [], "common_journeys": []},
        )

        bad_ts_ds = self._create_sessionized_dataset(
            "pm_badts.csv",
            "user_id,timestamp,page_url,action,session_id\nU1,invalid,/a,page_view,S1\n",
        )
        self.assertEqual(
            mine_patterns(bad_ts_ds),
            {"page_patterns": [], "action_patterns": [], "transitions": [], "common_journeys": []},
        )

    def test_one_event_sessions(self):
        """Test 17: One-event sessions produce no length >= 2 patterns or transitions."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/only,page_view,S1\n"
            "U2,2026-01-01 11:00:00,/other,click,S2\n"
        )
        dataset = self._create_sessionized_dataset("pm_one_event.csv", content)
        res = mine_patterns(dataset, min_support=0.1, max_pattern_length=3)

        self.assertEqual(res["page_patterns"], [])
        self.assertEqual(res["action_patterns"], [])
        self.assertEqual(res["transitions"], [])
        self.assertEqual(res["common_journeys"], [])

    def test_missing_required_column_raises_value_error(self):
        """Test 18: Missing required CSV column raises ValueError."""
        content = "user_id,timestamp,page_url,action\nU1,2026-01-01 10:00:00,/a,page_view\n"
        dataset = self._create_sessionized_dataset("pm_nocol.csv", content)
        with self.assertRaises(ValueError) as ctx:
            mine_patterns(dataset)
        self.assertIn("session_id", str(ctx.exception))

    def test_min_support_equal_to_1_requires_all_sessions(self):
        """Test 19: min_support=1 only returns patterns present in 100% of sessions."""
        content = (
            "user_id,timestamp,page_url,action,session_id\n"
            "U1,2026-01-01 10:00:00,/home,page_view,S1\n"
            "U1,2026-01-01 10:01:00,/shop,page_view,S1\n"
            "U1,2026-01-01 10:02:00,/cart,add_to_cart,S1\n"
            "U2,2026-01-01 11:00:00,/home,page_view,S2\n"
            "U2,2026-01-01 11:01:00,/shop,page_view,S2\n"
        )
        dataset = self._create_sessionized_dataset("pm_sup1.csv", content)
        res = mine_patterns(dataset, min_support=1, max_pattern_length=3)

        self.assertEqual(
            res["page_patterns"],
            [{"pattern": ["/home", "/shop"], "length": 2, "session_count": 2, "support": 1.0}],
        )

    def test_invalid_input_parameters_raise_value_error(self):
        """Test 20: Rejects invalid min_support (<=0, >1, non-number) and max_pattern_length (<2, non-int)."""
        content = "user_id,timestamp,page_url,action,session_id\nU1,2026-01-01 10:00:00,/a,page_view,S1\n"
        dataset = self._create_sessionized_dataset("pm_badparams.csv", content)

        for bad_sup in [0, -0.5, 1.01, "0.2", True]:
            with self.assertRaises(ValueError):
                mine_patterns(dataset, min_support=bad_sup)

        for bad_len in [1, 0, -2, 2.5, "3", False]:
            with self.assertRaises(ValueError):
                mine_patterns(dataset, max_pattern_length=bad_len)


class InsightsUnitTests(TestCase):
    def _create_dataset_with_results(self, analytics=None, patterns=None):
        from datasets.models import AnalysisResult, Dataset, PatternMiningResult

        dataset = Dataset.objects.create(
            filename="test.csv",
            status=Dataset.STATUS_COMPLETED,
        )
        if analytics is not None:
            AnalysisResult.objects.create(dataset=dataset, results=analytics)
        if patterns is not None:
            PatternMiningResult.objects.create(dataset=dataset, results=patterns)
        return dataset

    def _base_analytics(self):
        return {
            "total_users": 10,
            "total_sessions": 20,
            "total_events": 100,
            "average_session_duration": 145.5,
            "average_events_per_session": 5.0,
            "average_pages_per_session": 4.2,
            "most_visited_pages": [
                {"page_url": "/products", "visits": 50},
                {"page_url": "/home", "visits": 30},
            ],
            "least_visited_pages": [
                {"page_url": "/about", "visits": 3},
            ],
            "action_counts": {
                "page_view": 70,
                "click": 20,
                "purchase": 10,
            },
            "traffic_by_hour": [{"hour": 19, "events": 40}],
            "peak_traffic_hour": 19,
            "traffic_by_day": [{"date": "2026-01-01", "events": 100}],
            "device_counts": {"Mobile": 68, "Desktop": 32},
            "entry_pages": {"/home": 14, "/products": 6},
            "exit_pages": {"/cart": 11, "/checkout": 9},
        }

    def _base_patterns(self):
        return {
            "page_patterns": [
                {
                    "pattern": ["/home", "/products", "/laptops"],
                    "length": 3,
                    "session_count": 7,
                    "support": 0.35,
                }
            ],
            "action_patterns": [
                {
                    "pattern": ["page_view", "click"],
                    "length": 2,
                    "session_count": 12,
                    "support": 0.6,
                }
            ],
            "transitions": [
                {
                    "from": "/home",
                    "to": "/products",
                    "transition_count": 18,
                    "unique_sessions": 15,
                    "support": 0.75,
                }
            ],
            "common_journeys": [
                {
                    "pattern": ["/home", "/products", "/laptops"],
                    "length": 3,
                    "session_count": 7,
                    "support": 0.35,
                }
            ],
        }

    def test_peak_traffic_insight(self):
        """Test 1: Peak traffic insight is generated with hour metric."""
        from processing.insights import generate_insights

        ds = self._create_dataset_with_results(analytics=self._base_analytics())
        insights = generate_insights(ds)
        traffic = [i for i in insights if i["type"] == "traffic"]
        self.assertEqual(len(traffic), 1)
        self.assertEqual(traffic[0]["title"], "Peak Traffic Period")
        self.assertIn("19:00", traffic[0]["message"])
        self.assertEqual(traffic[0]["metric"], {"name": "peak_traffic_hour", "value": 19})

    def test_session_engagement_insight(self):
        """Test 2: Session engagement insight uses average pages per session neutrally."""
        from processing.insights import generate_insights

        ds = self._create_dataset_with_results(analytics=self._base_analytics())
        insights = generate_insights(ds)
        engagement = [i for i in insights if i["type"] == "engagement"]
        self.assertEqual(len(engagement), 1)
        self.assertEqual(engagement[0]["title"], "Average Session Engagement")
        self.assertIn("4.2", engagement[0]["message"])
        self.assertEqual(engagement[0]["metric"]["value"], 4.2)

    def test_most_and_least_visited_page_insights(self):
        """Tests 3 & 4: Most visited and least visited page insights use neutral wording."""
        from processing.insights import generate_insights

        ds = self._create_dataset_with_results(analytics=self._base_analytics())
        insights = generate_insights(ds)
        content = [i for i in insights if i["type"] == "content"]
        self.assertEqual(len(content), 2)
        self.assertEqual(content[0]["title"], "Most Visited Page")
        self.assertIn("/products", content[0]["message"])
        self.assertIn("50", content[0]["message"])
        self.assertEqual(content[1]["title"], "Least Visited Page")
        self.assertIn("/about", content[1]["message"])
        self.assertNotIn("underperforming", content[1]["message"].lower())

    def test_device_insight(self):
        """Test 5: Primary device insight includes device name and percentage."""
        from processing.insights import generate_insights

        ds = self._create_dataset_with_results(analytics=self._base_analytics())
        insights = generate_insights(ds)
        device = [i for i in insights if i["type"] == "device"]
        self.assertEqual(len(device), 1)
        self.assertEqual(device[0]["title"], "Primary Device")
        self.assertIn("Mobile", device[0]["message"])
        self.assertIn("68%", device[0]["message"])

    def test_common_journey_insight(self):
        """Test 6: Common journey insight reports pattern, session count, and support neutrally."""
        from processing.insights import generate_insights

        ds = self._create_dataset_with_results(
            analytics=self._base_analytics(),
            patterns=self._base_patterns(),
        )
        insights = generate_insights(ds)
        nav = [i for i in insights if i["type"] == "navigation"]
        self.assertGreaterEqual(len(nav), 1)
        self.assertEqual(nav[0]["title"], "Common User Journey")
        self.assertIn("/home → /products → /laptops", nav[0]["message"])
        self.assertIn("occurred in", nav[0]["message"])
        self.assertNotIn("caused", nav[0]["message"].lower())

    def test_entry_and_exit_page_insights(self):
        """Tests 7 & 8: Entry and exit page insights are neutral (no abandonment claim)."""
        from processing.insights import generate_insights

        ds = self._create_dataset_with_results(analytics=self._base_analytics())
        insights = generate_insights(ds)
        exits = [i for i in insights if i["type"] == "exit"]
        self.assertEqual(len(exits), 2)
        self.assertEqual(exits[0]["title"], "Common Entry Page")
        self.assertIn("/home", exits[0]["message"])
        self.assertEqual(exits[1]["title"], "Common Exit Page")
        self.assertIn("/cart", exits[1]["message"])
        self.assertNotIn("abandon", exits[1]["message"].lower())

    def test_purchase_and_zero_purchase_insights(self):
        """Tests 9 & 10: Purchase activity insight handles positive and zero purchase counts."""
        from processing.insights import generate_insights

        ds_with_purchase = self._create_dataset_with_results(analytics=self._base_analytics())
        insights1 = generate_insights(ds_with_purchase)
        conv1 = [i for i in insights1 if i["type"] == "conversion"]
        self.assertEqual(len(conv1), 1)
        self.assertIn("10 purchase events were recorded", conv1[0]["message"])

        no_purchase = self._base_analytics()
        no_purchase["action_counts"] = {"page_view": 70, "click": 30}
        ds_no_purchase = self._create_dataset_with_results(analytics=no_purchase)
        insights2 = generate_insights(ds_no_purchase)
        conv2 = [i for i in insights2 if i["type"] == "conversion"]
        self.assertEqual(len(conv2), 1)
        self.assertEqual(conv2[0]["severity"], "info")
        self.assertIn("No purchase events were recorded", conv2[0]["message"])

    def test_no_device_data_omits_device_insight(self):
        """Test 11: Empty or missing device_counts omits device insight."""
        from processing.insights import generate_insights

        analytics = self._base_analytics()
        analytics["device_counts"] = {}
        ds = self._create_dataset_with_results(analytics=analytics)
        insights = generate_insights(ds)
        self.assertEqual([i for i in insights if i["type"] == "device"], [])

    def test_no_pattern_mining_result_still_generates_analytics_insights(self):
        """Test 12: Insights work without PatternMiningResult."""
        from processing.insights import generate_insights

        ds = self._create_dataset_with_results(analytics=self._base_analytics(), patterns=None)
        insights = generate_insights(ds)
        self.assertGreater(len(insights), 0)
        self.assertEqual([i for i in insights if i["type"] == "navigation"], [])

    def test_empty_dataset_returns_no_insights(self):
        """Test 13: Empty dataset analytics returns empty list without filler."""
        from processing.insights import generate_insights

        empty_analytics = {
            "total_users": 0,
            "total_sessions": 0,
            "total_events": 0,
            "average_session_duration": 0.0,
            "average_events_per_session": 0.0,
            "average_pages_per_session": 0.0,
            "most_visited_pages": [],
            "least_visited_pages": [],
            "action_counts": {},
            "traffic_by_hour": [],
            "peak_traffic_hour": None,
            "traffic_by_day": [],
            "device_counts": {},
            "entry_pages": {},
            "exit_pages": {},
        }
        ds = self._create_dataset_with_results(analytics=empty_analytics)
        self.assertEqual(generate_insights(ds), [])

    def test_maximum_10_insights_and_deterministic_output(self):
        """Tests 14 & 15: Output capped at 10 insights and identical across repeated calls."""
        from processing.insights import generate_insights

        ds = self._create_dataset_with_results(
            analytics=self._base_analytics(),
            patterns=self._base_patterns(),
        )
        run1 = generate_insights(ds)
        run2 = generate_insights(ds)
        self.assertLessEqual(len(run1), 10)
        self.assertEqual(run1, run2)

    def test_no_unsupported_claims_and_valid_schema(self):
        """Test 16: Every insight uses allowed type/severity and avoids unsupported claims."""
        from processing.insights import generate_insights

        allowed_types = {"traffic", "engagement", "content", "navigation", "device", "conversion", "exit"}
        allowed_severities = {"info", "positive", "warning"}
        forbidden_phrases = ("underperforming", "abandoning", "caused users to", "conversion rate")

        ds = self._create_dataset_with_results(
            analytics=self._base_analytics(),
            patterns=self._base_patterns(),
        )
        insights = generate_insights(ds)
        for item in insights:
            self.assertIn(item["type"], allowed_types)
            self.assertIn(item["severity"], allowed_severities)
            self.assertIn("title", item)
            self.assertIn("message", item)
            self.assertIn("metric", item)
            lower_msg = item["message"].lower()
            for phrase in forbidden_phrases:
                self.assertNotIn(phrase, lower_msg)

    def test_missing_analytics_sections_handled_gracefully(self):
        """Test 17: Partial/minimal analytics dict does not crash."""
        from processing.insights import generate_insights

        minimal = {
            "total_users": 1,
            "total_sessions": 1,
            "total_events": 1,
            "peak_traffic_hour": 8,
        }
        ds = self._create_dataset_with_results(analytics=minimal)
        insights = generate_insights(ds)
        self.assertTrue(any(i["type"] == "traffic" for i in insights))

    def test_combined_analytics_and_patterns_prioritizes_navigation_first(self):
        """Test 18: Navigation insights appear first when PatternMiningResult is present."""
        from processing.insights import generate_insights

        ds = self._create_dataset_with_results(
            analytics=self._base_analytics(),
            patterns=self._base_patterns(),
        )
        insights = generate_insights(ds)
        self.assertEqual(insights[0]["type"], "navigation")

    def test_missing_analysis_result_raises_value_error(self):
        """Missing AnalysisResult raises ValueError."""
        from processing.insights import generate_insights

        ds = self._create_dataset_with_results(analytics=None)
        with self.assertRaises(ValueError):
            generate_insights(ds)



