import os
import shutil
import uuid
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AnalysisResult, Dataset, InsightResult, PatternMiningResult, Session


def clean_test_uploads():
    """Helper to clean test files created in BASE_DIR/uploads."""
    uploads_dir = os.path.join(settings.BASE_DIR, 'uploads')
    if os.path.exists(uploads_dir):
        for f in os.listdir(uploads_dir):
            if f.endswith('.csv'):
                try:
                    os.remove(os.path.join(uploads_dir, f))
                except OSError:
                    pass


class DatasetUploadAPITests(APITestCase):
    def setUp(self):
        self.upload_url = reverse('dataset-upload')

    def tearDown(self):
        clean_test_uploads()

    def test_valid_csv_upload(self):
        csv_content = b"timestamp,ip_address,url,status_code\n2026-01-01 10:00:00,192.168.1.1,/home,200\n"
        uploaded_file = SimpleUploadedFile("web_logs.csv", csv_content, content_type="text/csv")

        response = self.client.post(self.upload_url, {'file': uploaded_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('job_id', response.data)
        self.assertEqual(response.data['filename'], "web_logs.csv")
        self.assertEqual(
            response.data['headers'],
            ["timestamp", "ip_address", "url", "status_code"]
        )
        self.assertEqual(response.data['status'], "uploaded")

        # Check auto_mapping information returned in upload response
        self.assertIn('auto_mapping', response.data)
        self.assertIn('unmapped_required', response.data)
        self.assertIn('unmapped_optional', response.data)

        # Verify UUID format, DB record and persisted file
        job_id = uuid.UUID(response.data['job_id'])
        dataset = Dataset.objects.get(job_id=job_id)
        self.assertEqual(dataset.filename, "web_logs.csv")
        self.assertEqual(dataset.status, "uploaded")
        self.assertEqual(dataset.headers, ["timestamp", "ip_address", "url", "status_code"])
        self.assertTrue(os.path.exists(dataset.file_path))

    def test_missing_file(self):
        response = self.client.post(self.upload_url, {}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(Dataset.objects.count(), 0)

    def test_non_csv_file(self):
        txt_file = SimpleUploadedFile("records.txt", b"col1,col2\n1,2", content_type="text/plain")

        response = self.client.post(self.upload_url, {'file': txt_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(Dataset.objects.count(), 0)

    def test_empty_csv(self):
        empty_file = SimpleUploadedFile("empty.csv", b"", content_type="text/csv")

        response = self.client.post(self.upload_url, {'file': empty_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(Dataset.objects.count(), 0)

    def test_malformed_csv(self):
        malformed_content = b'col1,col2\n"unclosed_quote,value'
        malformed_file = SimpleUploadedFile("malformed.csv", malformed_content, content_type="text/csv")

        response = self.client.post(self.upload_url, {'file': malformed_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(Dataset.objects.count(), 0)

    def test_file_larger_than_50mb(self):
        large_size = 50 * 1024 * 1024 + 1024
        large_file = SimpleUploadedFile("oversized.csv", b"a" * large_size, content_type="text/csv")

        response = self.client.post(self.upload_url, {'file': large_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        self.assertIn('error', response.data)
        self.assertEqual(Dataset.objects.count(), 0)


class ColumnMappingAPITests(APITestCase):
    def setUp(self):
        self.map_url = reverse('map-columns')
        self.dataset = Dataset.objects.create(
            filename="access_log.csv",
            status=Dataset.STATUS_UPLOADED,
            headers=["customer_number", "created", "page", "activity", "device_category"],
        )

    def tearDown(self):
        clean_test_uploads()

    def test_manual_mapping_with_valid_columns(self):
        """Test 7: Manual mapping with valid columns updates dataset and sets status to 'mapping'."""
        payload = {
            "job_id": str(self.dataset.job_id),
            "mapping": {
                "user_id": "customer_number",
                "timestamp": "created",
                "page_url": "page",
                "action": "activity",
                "device": "device_category",
            }
        }
        response = self.client.post(self.map_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["job_id"], str(self.dataset.job_id))
        self.assertEqual(response.data["status"], "mapping")
        self.assertEqual(response.data["mapping"]["user_id"], "customer_number")
        self.assertEqual(response.data["mapping"]["timestamp"], "created")
        self.assertEqual(response.data["mapping"]["page_url"], "page")
        self.assertEqual(response.data["mapping"]["action"], "activity")
        self.assertEqual(response.data["mapping"]["device"], "device_category")

        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, "mapping")
        self.assertEqual(self.dataset.column_mapping["user_id"], "customer_number")

    def test_manual_mapping_with_nonexistent_source_column(self):
        """Test 8: Manual mapping with a source column not in CSV headers returns HTTP 400."""
        payload = {
            "job_id": str(self.dataset.job_id),
            "mapping": {
                "user_id": "nonexistent_header",
                "timestamp": "created",
                "page_url": "page",
                "action": "activity",
            }
        }
        response = self.client.post(self.map_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("nonexistent_header", response.data["error"])

        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, "uploaded")

    def test_duplicate_source_column_mapping(self):
        """Test 9: Mapping multiple logical fields to the same source column returns HTTP 400."""
        payload = {
            "job_id": str(self.dataset.job_id),
            "mapping": {
                "user_id": "customer_number",
                "timestamp": "created",
                "page_url": "page",
                "action": "page",
            }
        }
        response = self.client.post(self.map_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Duplicate source column mapping", response.data["error"])

        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, "uploaded")

    def test_nonexistent_job_id(self):
        """Test 10: Nonexistent job_id returns HTTP 404."""
        random_uuid = str(uuid.uuid4())
        payload = {
            "job_id": random_uuid,
            "mapping": {
                "user_id": "customer_number",
                "timestamp": "created",
                "page_url": "page",
                "action": "activity",
            }
        }
        response = self.client.post(self.map_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_missing_required_fields_in_manual_mapping(self):
        """Test manual mapping missing a required logical field returns HTTP 400."""
        payload = {
            "job_id": str(self.dataset.job_id),
            "mapping": {
                "user_id": "customer_number",
                "timestamp": "created",
                "page_url": "page",
            }
        }
        response = self.client.post(self.map_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Missing required logical field", response.data["error"])

    def test_invalid_mapping_type(self):
        """Test sending non-dict mapping returns HTTP 400."""
        payload = {
            "job_id": str(self.dataset.job_id),
            "mapping": ["not", "an", "object"]
        }
        response = self.client.post(self.map_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_get_map_columns_info(self):
        """Test GET /api/map-columns?job_id=... returns auto-mapping and header details."""
        response = self.client.get(f"{self.map_url}?job_id={self.dataset.job_id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["job_id"], str(self.dataset.job_id))
        self.assertEqual(response.data["headers"], self.dataset.headers)
        self.assertIn("auto_mapping", response.data)
        self.assertIn("unmapped_required", response.data)
        self.assertIn("unmapped_optional", response.data)


class ValueMappingAPITests(APITestCase):
    def setUp(self):
        self.upload_url = reverse('dataset-upload')
        self.column_map_url = reverse('map-columns')
        self.value_map_url = reverse('map-values')

        # Upload a dataset with action column containing various values
        csv_content = (
            b"user,time,url,event\n"
            b"u1,2026-01-01 10:00:00,/home,VIEW\n"
            b"u2,2026-01-01 10:01:00,/shop,click\n"
            b"u3,2026-01-01 10:02:00,/cart,ADD_CART\n"
            b"u4,2026-01-01 10:03:00,/buy,purchase\n"
            b"u5,2026-01-01 10:04:00,/item,hover_image\n"
        )
        uploaded_file = SimpleUploadedFile("events.csv", csv_content, content_type="text/csv")
        upload_resp = self.client.post(self.upload_url, {'file': uploaded_file}, format='multipart')
        self.assertEqual(upload_resp.status_code, status.HTTP_201_CREATED)
        self.job_id = upload_resp.data['job_id']

        # Complete column mapping
        col_map_resp = self.client.post(
            self.column_map_url,
            {
                "job_id": self.job_id,
                "mapping": {
                    "user_id": "user",
                    "timestamp": "time",
                    "page_url": "url",
                    "action": "event",
                }
            },
            format='json'
        )
        self.assertEqual(col_map_resp.status_code, status.HTTP_200_OK)

    def tearDown(self):
        clean_test_uploads()

    def test_get_map_values_endpoint(self):
        """Test GET /api/map-values?job_id=... returns unique actions and auto-mapping."""
        response = self.client.get(f"{self.value_map_url}?job_id={self.job_id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["job_id"], self.job_id)
        self.assertIn("VIEW", response.data["unique_values"])
        self.assertIn("click", response.data["unique_values"])
        self.assertIn("ADD_CART", response.data["unique_values"])
        self.assertIn("purchase", response.data["unique_values"])
        self.assertIn("hover_image", response.data["unique_values"])

        # Auto mapping suggestions
        self.assertEqual(response.data["auto_mapping"]["VIEW"], "page_view")
        self.assertEqual(response.data["auto_mapping"]["click"], "click")
        self.assertEqual(response.data["auto_mapping"]["ADD_CART"], "add_to_cart")
        self.assertEqual(response.data["auto_mapping"]["purchase"], "purchase")

        # Unknown values
        self.assertEqual(response.data["unknown_values"], ["hover_image"])
        self.assertIn("page_view", response.data["allowed_actions"])
        self.assertIn("other", response.data["allowed_actions"])

    def test_manual_mapping_of_unknown_value_to_valid_action(self):
        """Test 7: Manual mapping of an unknown value to a valid standard action (e.g. 'click')."""
        payload = {
            "job_id": self.job_id,
            "mapping": {
                "hover_image": "click",
            }
        }
        response = self.client.post(self.value_map_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["job_id"], self.job_id)
        self.assertEqual(response.data["status"], "mapping")
        self.assertEqual(response.data["mapping"]["hover_image"], "click")
        self.assertEqual(response.data["mapping"]["VIEW"], "page_view")

        dataset = Dataset.objects.get(job_id=uuid.UUID(self.job_id))
        self.assertEqual(dataset.status, "mapping")
        self.assertEqual(dataset.value_mapping["hover_image"], "click")

    def test_manual_mapping_to_other(self):
        """Test 8: Manual mapping an unknown value to 'other'."""
        payload = {
            "job_id": self.job_id,
            "mapping": {
                "hover_image": "other",
            }
        }
        response = self.client.post(self.value_map_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["mapping"]["hover_image"], "other")

        dataset = Dataset.objects.get(job_id=uuid.UUID(self.job_id))
        self.assertEqual(dataset.value_mapping["hover_image"], "other")

    def test_invalid_target_action(self):
        """Test 9: Mapping to a non-standard target action returns HTTP 400."""
        payload = {
            "job_id": self.job_id,
            "mapping": {
                "hover_image": "super_custom_action",
            }
        }
        response = self.client.post(self.value_map_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Invalid target action", response.data["error"])

    def test_source_value_that_does_not_exist(self):
        """Test 10: Mapping a source value that doesn't exist in the CSV returns HTTP 400."""
        payload = {
            "job_id": self.job_id,
            "mapping": {
                "nonexistent_source_value": "click",
            }
        }
        response = self.client.post(self.value_map_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("does not exist in the dataset's action column", response.data["error"])

    def test_nonexistent_job_id(self):
        """Test 11: Submitting value mapping with a nonexistent job_id returns HTTP 404."""
        random_uuid = str(uuid.uuid4())
        payload = {
            "job_id": random_uuid,
            "mapping": {
                "hover_image": "other",
            }
        }
        response = self.client.post(self.value_map_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_empty_or_invalid_mapping(self):
        """Test 12: Empty mapping or non-dict mapping returns HTTP 400."""
        resp_empty = self.client.post(
            self.value_map_url,
            {"job_id": self.job_id, "mapping": {}},
            format='json'
        )
        self.assertEqual(resp_empty.status_code, status.HTTP_400_BAD_REQUEST)

        resp_list = self.client.post(
            self.value_map_url,
            {"job_id": self.job_id, "mapping": ["invalid"]},
            format='json'
        )
        self.assertEqual(resp_list.status_code, status.HTTP_400_BAD_REQUEST)

    def test_map_values_without_action_column_mapped(self):
        """Test attempting value mapping before column mapping returns HTTP 400."""
        unmapped_dataset = Dataset.objects.create(
            filename="unmapped.csv",
            status=Dataset.STATUS_UPLOADED,
            headers=["col1", "col2"],
            column_mapping={},
        )
        response = self.client.get(f"{self.value_map_url}?job_id={unmapped_dataset.job_id}")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("action", response.data["error"])


class ProcessAPITests(APITestCase):
    def setUp(self):
        self.upload_url = reverse('dataset-upload')
        self.column_map_url = reverse('map-columns')
        self.value_map_url = reverse('map-values')
        self.process_url = reverse('process-dataset')

        # Upload a dataset
        csv_content = (
            b"user,time,url,event\n"
            b"u1,2026-01-01 10:00:00,/home,VIEW\n"
            b"u2,2026-01-01 10:01:00,/shop,click\n"
            b"u1,2026-01-01 10:00:00,/home,VIEW\n"  # duplicate
            b",2026-01-01 10:02:00,/cart,ADD_CART\n"  # missing user
            b"u3,invalid-date,/buy,purchase\n"  # invalid date
        )
        uploaded_file = SimpleUploadedFile("logs.csv", csv_content, content_type="text/csv")
        upload_resp = self.client.post(self.upload_url, {'file': uploaded_file}, format='multipart')
        self.assertEqual(upload_resp.status_code, status.HTTP_201_CREATED)
        self.job_id = upload_resp.data['job_id']

        # Complete column mapping
        self.client.post(
            self.column_map_url,
            {
                "job_id": self.job_id,
                "mapping": {
                    "user_id": "user",
                    "timestamp": "time",
                    "page_url": "url",
                    "action": "event",
                }
            },
            format='json'
        )

        # Complete value mapping
        self.client.post(
            self.value_map_url,
            {
                "job_id": self.job_id,
                "mapping": {
                    "VIEW": "page_view",
                    "click": "click",
                    "ADD_CART": "add_to_cart",
                    "purchase": "purchase",
                }
            },
            format='json'
        )

    def tearDown(self):
        clean_test_uploads()

    def test_successful_process_endpoint(self):
        """Test 13: Successful /api/process triggers cleaning, quality reporting, and status='completed'."""
        response = self.client.post(self.process_url, {"job_id": self.job_id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["job_id"], self.job_id)
        self.assertEqual(response.data["status"], "completed")
        self.assertIn("quality_report", response.data)

        report = response.data["quality_report"]
        self.assertEqual(report["rows_before"], 5)
        self.assertEqual(report["rows_after"], 2)
        self.assertEqual(report["rows_removed"], 3)
        self.assertEqual(report["missing_user_id"], 1)
        self.assertEqual(report["invalid_timestamp"], 1)
        self.assertEqual(report["duplicate_rows"], 1)

        # Verify DB updates
        dataset = Dataset.objects.get(job_id=uuid.UUID(self.job_id))
        self.assertEqual(dataset.status, "completed")
        self.assertTrue(os.path.exists(dataset.cleaned_file_path))

    def test_processing_failure_missing_file(self):
        """Test 14: Processing fails cleanly if the underlying CSV file is missing, setting status to 'failed'."""
        dataset = Dataset.objects.get(job_id=uuid.UUID(self.job_id))
        if os.path.exists(dataset.file_path):
            os.remove(dataset.file_path)

        response = self.client.post(self.process_url, {"job_id": self.job_id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

        dataset.refresh_from_db()
        self.assertEqual(dataset.status, "failed")

    def test_dataset_status_transitions(self):
        """Test 15: Verify complete status transitions: uploaded -> mapping -> completed."""
        csv_content = b"user_id,timestamp,page_url,action\nu1,2026-01-01 10:00:00,/home,page_view\n"
        up_resp = self.client.post(
            self.upload_url,
            {'file': SimpleUploadedFile("clean.csv", csv_content, content_type="text/csv")},
            format='multipart'
        )
        j_id = up_resp.data['job_id']
        ds = Dataset.objects.get(job_id=uuid.UUID(j_id))
        self.assertEqual(ds.status, "uploaded")

        # Column mapping
        self.client.post(
            self.column_map_url,
            {
                "job_id": j_id,
                "mapping": {
                    "user_id": "user_id",
                    "timestamp": "timestamp",
                    "page_url": "page_url",
                    "action": "action",
                }
            },
            format='json'
        )
        ds.refresh_from_db()
        self.assertEqual(ds.status, "mapping")

        # Value mapping
        self.client.post(
            self.value_map_url,
            {"job_id": j_id, "mapping": {"page_view": "page_view"}},
            format='json'
        )
        ds.refresh_from_db()
        self.assertEqual(ds.status, "mapping")

        # Process
        proc_resp = self.client.post(self.process_url, {"job_id": j_id}, format='json')
        self.assertEqual(proc_resp.status_code, status.HTTP_200_OK)
        ds.refresh_from_db()
        self.assertEqual(ds.status, "completed")

    def test_process_missing_column_mapping(self):
        """Test /api/process fails with HTTP 400 if column mapping is not completed."""
        ds = Dataset.objects.create(filename="nomap.csv", status=Dataset.STATUS_UPLOADED)
        response = self.client.post(self.process_url, {"job_id": str(ds.job_id)}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Column mapping", response.data["error"])

    def test_process_missing_value_mapping(self):
        """Test /api/process fails with HTTP 400 if value mapping is not completed."""
        ds = Dataset.objects.create(
            filename="noval.csv",
            status=Dataset.STATUS_MAPPING,
            column_mapping={
                "user_id": "u",
                "timestamp": "t",
                "page_url": "p",
                "action": "a",
            },
            value_mapping={},
        )
        response = self.client.post(self.process_url, {"job_id": str(ds.job_id)}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Value mapping", response.data["error"])

    def test_process_nonexistent_job_id(self):
        """Test /api/process with nonexistent job_id returns HTTP 404."""
        response = self.client.post(self.process_url, {"job_id": str(uuid.uuid4())}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_process_endpoint(self):
        """Test GET /api/process?job_id=... returns current processing status and quality report."""
        # Process the setup dataset first
        self.client.post(self.process_url, {"job_id": self.job_id}, format='json')

        response = self.client.get(f"{self.process_url}?job_id={self.job_id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["job_id"], self.job_id)
        self.assertEqual(response.data["status"], "completed")
        self.assertIn("quality_report", response.data)


class SessionizeAPITests(APITestCase):
    def setUp(self):
        self.upload_url = reverse('dataset-upload')
        self.column_map_url = reverse('map-columns')
        self.value_map_url = reverse('map-values')
        self.process_url = reverse('process-dataset')
        self.sessionize_url = reverse('sessionize-dataset')

        csv_content = (
            b"user,time,url,event\n"
            b"U1,2026-01-01 10:00:00,/home,VIEW\n"
            b"U1,2026-01-01 10:15:00,/products,click\n"
            b"U1,2026-01-01 10:55:00,/cart,ADD_CART\n"
            b"U2,2026-01-01 10:05:00,/home,VIEW\n"
        )
        uploaded_file = SimpleUploadedFile("session_logs.csv", csv_content, content_type="text/csv")
        upload_resp = self.client.post(self.upload_url, {'file': uploaded_file}, format='multipart')
        self.assertEqual(upload_resp.status_code, status.HTTP_201_CREATED)
        self.job_id = upload_resp.data['job_id']

        self.client.post(
            self.column_map_url,
            {
                "job_id": self.job_id,
                "mapping": {
                    "user_id": "user",
                    "timestamp": "time",
                    "page_url": "url",
                    "action": "event",
                },
            },
            format='json',
        )
        self.client.post(
            self.value_map_url,
            {
                "job_id": self.job_id,
                "mapping": {
                    "VIEW": "page_view",
                    "click": "click",
                    "ADD_CART": "add_to_cart",
                },
            },
            format='json',
        )
        proc_resp = self.client.post(self.process_url, {"job_id": self.job_id}, format='json')
        self.assertEqual(proc_resp.status_code, status.HTTP_200_OK)

    def tearDown(self):
        clean_test_uploads()

    def test_sessionize_default_timeout_30(self):
        """Test 12: Default timeout is 30 minutes and API returns clean summary without file paths."""
        response = self.client.post(self.sessionize_url, {"job_id": self.job_id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["job_id"], self.job_id)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["timeout_minutes"], 30)
        self.assertEqual(response.data["total_sessions"], 3)
        self.assertEqual(response.data["total_users"], 2)
        self.assertTrue(response.data["sessionized_file_available"])

        # Do not expose internal filesystem paths
        self.assertNotIn("sessionized_file_path", response.data)
        self.assertNotIn("cleaned_file_path", response.data)
        self.assertNotIn("file_path", response.data)

        # Verify Session rows created in DB
        self.assertEqual(Session.objects.filter(dataset__job_id=uuid.UUID(self.job_id)).count(), 3)

    def test_sessionize_custom_timeout(self):
        """Test 13: Custom timeout via API works (e.g. timeout=60 merges U1's 40m gap)."""
        response = self.client.post(
            self.sessionize_url,
            {"job_id": self.job_id, "timeout_minutes": 60},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["timeout_minutes"], 60)
        self.assertEqual(response.data["total_sessions"], 2)
        self.assertEqual(response.data["total_users"], 2)

    def test_invalid_timeout_rejected(self):
        """Test 14: Invalid timeout values (0, negative, string, bool, null) are rejected with HTTP 400."""
        for bad_timeout in [0, -10, "thirty", True, None]:
            resp = self.client.post(
                self.sessionize_url,
                {"job_id": self.job_id, "timeout_minutes": bad_timeout},
                format='json',
            )
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("error", resp.data)

    def test_missing_cleaned_file_handled_gracefully(self):
        """Test 15: Missing cleaned CSV file returns HTTP 400 gracefully."""
        ds = Dataset.objects.get(job_id=uuid.UUID(self.job_id))
        if os.path.exists(ds.cleaned_file_path):
            os.remove(ds.cleaned_file_path)

        resp = self.client.post(self.sessionize_url, {"job_id": self.job_id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", resp.data)

    def test_rerun_sessionization_no_duplicate_sessions(self):
        """Test 17: Rerunning /api/sessionize replaces previous Session rows without duplicates."""
        resp1 = self.client.post(self.sessionize_url, {"job_id": self.job_id}, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(Session.objects.filter(dataset__job_id=uuid.UUID(self.job_id)).count(), 3)

        # Rerun with custom timeout
        resp2 = self.client.post(
            self.sessionize_url,
            {"job_id": self.job_id, "timeout_minutes": 60},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(Session.objects.filter(dataset__job_id=uuid.UUID(self.job_id)).count(), 2)

    def test_sessionize_uncleaned_dataset_rejected(self):
        """Test attempting to sessionize before cleaning completes returns HTTP 400."""
        uncleaned = Dataset.objects.create(filename="raw.csv", status=Dataset.STATUS_MAPPING)
        resp = self.client.post(self.sessionize_url, {"job_id": str(uncleaned.job_id)}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", resp.data)

    def test_sessionize_nonexistent_job_id_returns_404(self):
        """Test /api/sessionize with nonexistent job_id returns HTTP 404."""
        resp = self.client.post(self.sessionize_url, {"job_id": str(uuid.uuid4())}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_sessionize_summary(self):
        """Test GET /api/sessionize?job_id=... returns current sessionization summary."""
        self.client.post(self.sessionize_url, {"job_id": self.job_id}, format='json')
        resp = self.client.get(f"{self.sessionize_url}?job_id={self.job_id}")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["job_id"], self.job_id)
        self.assertEqual(resp.data["total_sessions"], 3)
        self.assertEqual(resp.data["total_users"], 2)
        self.assertTrue(resp.data["sessionized_file_available"])


class AnalyzeAPITests(APITestCase):
    def setUp(self):
        self.upload_url = reverse('dataset-upload')
        self.column_map_url = reverse('map-columns')
        self.value_map_url = reverse('map-values')
        self.process_url = reverse('process-dataset')
        self.sessionize_url = reverse('sessionize-dataset')
        self.analyze_url = reverse('analyze-dataset')

        csv_content = (
            b"user,time,url,event,device\n"
            b"U1,2026-01-01 10:00:00,/home,VIEW,mobile\n"
            b"U1,2026-01-01 10:05:00,/product,VIEW,mobile\n"
            b"U1,2026-01-01 10:06:00,/cart,ADD_CART,mobile\n"
            b"U2,2026-01-01 11:00:00,/home,VIEW,desktop\n"
        )
        uploaded_file = SimpleUploadedFile("analytics_logs.csv", csv_content, content_type="text/csv")
        upload_resp = self.client.post(self.upload_url, {'file': uploaded_file}, format='multipart')
        self.assertEqual(upload_resp.status_code, status.HTTP_201_CREATED)
        self.job_id = upload_resp.data['job_id']

        self.client.post(
            self.column_map_url,
            {
                "job_id": self.job_id,
                "mapping": {
                    "user_id": "user",
                    "timestamp": "time",
                    "page_url": "url",
                    "action": "event",
                    "device": "device",
                },
            },
            format='json',
        )
        self.client.post(
            self.value_map_url,
            {
                "job_id": self.job_id,
                "mapping": {
                    "VIEW": "page_view",
                    "ADD_CART": "add_to_cart",
                },
            },
            format='json',
        )
        proc_resp = self.client.post(self.process_url, {"job_id": self.job_id}, format='json')
        self.assertEqual(proc_resp.status_code, status.HTTP_200_OK)

        sess_resp = self.client.post(self.sessionize_url, {"job_id": self.job_id}, format='json')
        self.assertEqual(sess_resp.status_code, status.HTTP_200_OK)

    def tearDown(self):
        clean_test_uploads()

    def test_post_analyze_success_and_persists_result(self):
        """Test 1: POST /api/analyze computes metrics, saves AnalysisResult, and omits file paths."""
        response = self.client.post(self.analyze_url, {"job_id": self.job_id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["job_id"], self.job_id)
        self.assertEqual(response.data["status"], "completed")
        self.assertIn("analytics", response.data)

        analytics = response.data["analytics"]
        self.assertEqual(analytics["total_users"], 2)
        self.assertEqual(analytics["total_sessions"], 2)
        self.assertEqual(analytics["total_events"], 4)
        self.assertEqual(analytics["average_session_duration"], 180.0)
        self.assertEqual(analytics["average_events_per_session"], 2.0)
        self.assertEqual(analytics["average_pages_per_session"], 1.5)
        self.assertEqual(analytics["device_counts"], {"mobile": 3, "desktop": 1})
        self.assertEqual(analytics["entry_pages"], {"/home": 2})
        self.assertEqual(analytics["exit_pages"], {"/cart": 1, "/home": 1})

        # Ensure internal filesystem paths are never exposed
        self.assertNotIn("sessionized_file_path", response.data)
        self.assertNotIn("cleaned_file_path", response.data)
        self.assertNotIn("file_path", response.data)

        # Verify DB persistence
        saved = AnalysisResult.objects.get(dataset__job_id=uuid.UUID(self.job_id))
        self.assertEqual(saved.results["total_events"], 4)

    def test_get_analyze_returns_saved_analytics(self):
        """Test 2: GET /api/analyze?job_id=... returns previously computed analytics."""
        post_resp = self.client.post(self.analyze_url, {"job_id": self.job_id}, format='json')
        self.assertEqual(post_resp.status_code, status.HTTP_200_OK)

        get_resp = self.client.get(f"{self.analyze_url}?job_id={self.job_id}")
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(get_resp.data["job_id"], self.job_id)
        self.assertEqual(get_resp.data["status"], "completed")
        self.assertEqual(get_resp.data["analytics"], post_resp.data["analytics"])

    def test_post_analyze_recalculates_and_updates_existing_result(self):
        """Test 3: Repeated POST /api/analyze updates AnalysisResult cleanly without duplicates."""
        resp1 = self.client.post(self.analyze_url, {"job_id": self.job_id}, format='json')
        resp2 = self.client.post(self.analyze_url, {"job_id": self.job_id}, format='json')

        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(
            AnalysisResult.objects.filter(dataset__job_id=uuid.UUID(self.job_id)).count(),
            1,
        )

    def test_post_analyze_missing_or_invalid_job_id_returns_400(self):
        """Test 4: POST /api/analyze with missing or malformed job_id returns 400."""
        missing_resp = self.client.post(self.analyze_url, {}, format='json')
        self.assertEqual(missing_resp.status_code, status.HTTP_400_BAD_REQUEST)

        invalid_resp = self.client.post(self.analyze_url, {"job_id": "not-a-uuid"}, format='json')
        self.assertEqual(invalid_resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_analyze_nonexistent_job_id_returns_404(self):
        """Test 5: POST /api/analyze with unknown UUID returns 404."""
        unknown_id = str(uuid.uuid4())
        resp = self.client.post(self.analyze_url, {"job_id": unknown_id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_analyze_before_sessionization_returns_400(self):
        """Test 6: POST /api/analyze on un-sessionized dataset returns 400."""
        unready = Dataset.objects.create(
            filename="unready.csv",
            status=Dataset.STATUS_COMPLETED,
            sessionized_file_path="",
        )
        resp = self.client.post(self.analyze_url, {"job_id": str(unready.job_id)}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_analyze_missing_job_id_or_not_calculated_returns_400_and_404(self):
        """Test 7: GET /api/analyze handles missing/invalid job_id (400) and missing result (404)."""
        no_param = self.client.get(self.analyze_url)
        self.assertEqual(no_param.status_code, status.HTTP_400_BAD_REQUEST)

        bad_param = self.client.get(f"{self.analyze_url}?job_id=bad-uuid")
        self.assertEqual(bad_param.status_code, status.HTTP_400_BAD_REQUEST)

        not_found_ds = self.client.get(f"{self.analyze_url}?job_id={uuid.uuid4()}")
        self.assertEqual(not_found_ds.status_code, status.HTTP_404_NOT_FOUND)

        not_analyzed = self.client.get(f"{self.analyze_url}?job_id={self.job_id}")
        self.assertEqual(not_analyzed.status_code, status.HTTP_404_NOT_FOUND)


class MinePatternsAPITests(APITestCase):
    def setUp(self):
        self.upload_url = reverse('dataset-upload')
        self.column_map_url = reverse('map-columns')
        self.value_map_url = reverse('map-values')
        self.process_url = reverse('process-dataset')
        self.sessionize_url = reverse('sessionize-dataset')
        self.mine_url = reverse('mine-patterns')

        csv_content = (
            b"user,time,url,event\n"
            b"U1,2026-01-01 10:00:00,/home,VIEW\n"
            b"U1,2026-01-01 10:01:00,/products,CLICK\n"
            b"U1,2026-01-01 10:02:00,/cart,ADD_CART\n"
            b"U2,2026-01-01 11:00:00,/home,VIEW\n"
            b"U2,2026-01-01 11:01:00,/products,CLICK\n"
            b"U3,2026-01-01 12:00:00,/about,VIEW\n"
            b"U3,2026-01-01 12:01:00,/contact,VIEW\n"
        )
        uploaded_file = SimpleUploadedFile("mine_logs.csv", csv_content, content_type="text/csv")
        upload_resp = self.client.post(self.upload_url, {'file': uploaded_file}, format='multipart')
        self.assertEqual(upload_resp.status_code, status.HTTP_201_CREATED)
        self.job_id = upload_resp.data['job_id']

        self.client.post(
            self.column_map_url,
            {
                "job_id": self.job_id,
                "mapping": {
                    "user_id": "user",
                    "timestamp": "time",
                    "page_url": "url",
                    "action": "event",
                },
            },
            format='json',
        )
        self.client.post(
            self.value_map_url,
            {
                "job_id": self.job_id,
                "mapping": {
                    "VIEW": "page_view",
                    "CLICK": "click",
                    "ADD_CART": "add_to_cart",
                },
            },
            format='json',
        )
        proc_resp = self.client.post(self.process_url, {"job_id": self.job_id}, format='json')
        self.assertEqual(proc_resp.status_code, status.HTTP_200_OK)

        sess_resp = self.client.post(self.sessionize_url, {"job_id": self.job_id}, format='json')
        self.assertEqual(sess_resp.status_code, status.HTTP_200_OK)

    def tearDown(self):
        clean_test_uploads()

    def test_post_mine_patterns_success(self):
        """Test 1: POST /api/mine-patterns runs successfully with defaults and persists result."""
        response = self.client.post(self.mine_url, {"job_id": self.job_id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["job_id"], self.job_id)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["min_support"], 0.1)
        self.assertEqual(response.data["max_pattern_length"], 3)

        patterns = response.data["patterns"]
        self.assertIn("page_patterns", patterns)
        self.assertIn("action_patterns", patterns)
        self.assertIn("transitions", patterns)
        self.assertIn("common_journeys", patterns)
        self.assertEqual(patterns["page_patterns"][0]["pattern"], ["/home", "/products"])
        self.assertEqual(patterns["page_patterns"][0]["session_count"], 2)

        saved = PatternMiningResult.objects.get(dataset__job_id=uuid.UUID(self.job_id))
        self.assertEqual(saved.min_support, 0.1)
        self.assertEqual(saved.max_pattern_length, 3)

    def test_get_mine_patterns_success(self):
        """Test 2: GET /api/mine-patterns?job_id=... returns saved pattern mining results."""
        post_resp = self.client.post(self.mine_url, {"job_id": self.job_id}, format='json')
        self.assertEqual(post_resp.status_code, status.HTTP_200_OK)

        get_resp = self.client.get(f"{self.mine_url}?job_id={self.job_id}")
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(get_resp.data["job_id"], self.job_id)
        self.assertEqual(get_resp.data["status"], "completed")
        self.assertEqual(get_resp.data["patterns"], post_resp.data["patterns"])

        # Missing result on another dataset or invalid query params
        missing_param = self.client.get(self.mine_url)
        self.assertEqual(missing_param.status_code, status.HTTP_400_BAD_REQUEST)

        bad_uuid = self.client.get(f"{self.mine_url}?job_id=invalid-uuid")
        self.assertEqual(bad_uuid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_custom_min_support_filters_patterns(self):
        """Test 3: Custom min_support parameter controls pattern filtering."""
        resp = self.client.post(
            self.mine_url,
            {"job_id": self.job_id, "min_support": 0.5},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["min_support"], 0.5)
        page_patterns = [p["pattern"] for p in resp.data["patterns"]["page_patterns"]]
        self.assertEqual(page_patterns, [["/home", "/products"]])

    def test_custom_max_pattern_length_caps_pattern_length(self):
        """Test 4: Custom max_pattern_length restricts maximum mined pattern length."""
        resp = self.client.post(
            self.mine_url,
            {"job_id": self.job_id, "min_support": 0.1, "max_pattern_length": 2},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["max_pattern_length"], 2)
        self.assertTrue(
            all(p["length"] <= 2 for p in resp.data["patterns"]["page_patterns"])
        )

    def test_invalid_min_support_returns_400(self):
        """Test 5: Invalid min_support values return HTTP 400."""
        for bad_val in [0, -0.2, 1.5, "abc"]:
            resp = self.client.post(
                self.mine_url,
                {"job_id": self.job_id, "min_support": bad_val},
                format='json',
            )
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_max_pattern_length_returns_400(self):
        """Test 6: Invalid max_pattern_length values return HTTP 400."""
        for bad_val in [1, 0, -3, 2.5, "three"]:
            resp = self.client.post(
                self.mine_url,
                {"job_id": self.job_id, "max_pattern_length": bad_val},
                format='json',
            )
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sessionization_not_completed_returns_400_and_get_returns_404(self):
        """Test 7: POST returns 400 before sessionization; GET returns 404 before mining."""
        unready = Dataset.objects.create(
            filename="unready.csv",
            status=Dataset.STATUS_COMPLETED,
            sessionized_file_path="",
        )
        post_resp = self.client.post(
            self.mine_url,
            {"job_id": str(unready.job_id)},
            format='json',
        )
        self.assertEqual(post_resp.status_code, status.HTTP_400_BAD_REQUEST)

        get_resp = self.client.get(f"{self.mine_url}?job_id={self.job_id}")
        self.assertEqual(get_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_job_id_returns_404(self):
        """Test 8: POST and GET with nonexistent job_id return HTTP 404."""
        unknown_id = str(uuid.uuid4())
        post_resp = self.client.post(self.mine_url, {"job_id": unknown_id}, format='json')
        self.assertEqual(post_resp.status_code, status.HTTP_404_NOT_FOUND)

        get_resp = self.client.get(f"{self.mine_url}?job_id={unknown_id}")
        self.assertEqual(get_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_or_invalid_job_id_returns_400(self):
        """Test 9: Missing or malformed job_id in POST returns HTTP 400."""
        missing_resp = self.client.post(self.mine_url, {}, format='json')
        self.assertEqual(missing_resp.status_code, status.HTTP_400_BAD_REQUEST)

        invalid_resp = self.client.post(
            self.mine_url,
            {"job_id": "not-a-uuid"},
            format='json',
        )
        self.assertEqual(invalid_resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rerunning_mining_updates_existing_result(self):
        """Test 10: Re-running POST /api/mine-patterns updates existing PatternMiningResult."""
        resp1 = self.client.post(
            self.mine_url,
            {"job_id": self.job_id, "min_support": 0.1, "max_pattern_length": 3},
            format='json',
        )
        resp2 = self.client.post(
            self.mine_url,
            {"job_id": self.job_id, "min_support": 0.6, "max_pattern_length": 2},
            format='json',
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

        qs = PatternMiningResult.objects.filter(dataset__job_id=uuid.UUID(self.job_id))
        self.assertEqual(qs.count(), 1)
        saved = qs.first()
        self.assertEqual(saved.min_support, 0.6)
        self.assertEqual(saved.max_pattern_length, 2)

    def test_filesystem_paths_not_exposed(self):
        """Test 11: Responses from POST and GET /api/mine-patterns never expose file paths."""
        post_resp = self.client.post(self.mine_url, {"job_id": self.job_id}, format='json')
        get_resp = self.client.get(f"{self.mine_url}?job_id={self.job_id}")

        for resp in (post_resp, get_resp):
            self.assertNotIn("sessionized_file_path", resp.data)
            self.assertNotIn("cleaned_file_path", resp.data)
            self.assertNotIn("file_path", resp.data)


class EndToEndPipelineIntegrationTests(APITestCase):
    def setUp(self):
        self.upload_url = reverse('dataset-upload')
        self.map_columns_url = reverse('map-columns')
        self.map_values_url = reverse('map-values')
        self.process_url = reverse('process-dataset')
        self.sessionize_url = reverse('sessionize-dataset')
        self.analyze_url = reverse('analyze-dataset')
        self.mine_url = reverse('mine-patterns')
        self.insights_url = reverse('insights')

        self.csv_content = (
            "visitor_id,datetime,url,event,device\n"
            # U001 Session 1: 18:00 -> 18:05 -> 18:35 (exact 30-min gap, same session) -> 18:38
            "U001,2026-11-10 18:00:00,/home,VIEW,mobile\n"
            "U001,2026-11-10 18:05:00,/products,VIEW,mobile\n"
            "U001,2026-11-10 18:35:00,/laptops,CLICK,mobile\n"
            "U001,2026-11-10 18:38:00,/cart,ADD_CART,mobile\n"
            # U001 Session 2: 19:09 (31-min gap from 18:38, new session)
            "U001,2026-11-10 19:09:00,/home,VIEW,mobile\n"
            "U001,2026-11-10 19:12:00,/products,VIEW,mobile\n"
            "U001,2026-11-10 19:15:00,/checkout,PURCHASE,mobile\n"
            # U002 Session 3
            "U002,2026-11-10 19:00:00,/home,VIEW,desktop\n"
            "U002,2026-11-10 19:04:00,/products,VIEW,desktop\n"
            "U002,2026-11-10 19:08:00,/cart,VIEW,desktop\n"
            # Invalid row (missing timestamp) to verify cleaning drops it
            "U003,,/broken,VIEW,desktop\n"
        ).encode("utf-8")

    def tearDown(self):
        clean_test_uploads()

    def _upload_and_process(self):
        uploaded = SimpleUploadedFile("e2e_nonstandard.csv", self.csv_content, content_type="text/csv")
        upload_resp = self.client.post(self.upload_url, {"file": uploaded}, format="multipart")
        self.assertEqual(upload_resp.status_code, status.HTTP_201_CREATED)
        job_id = upload_resp.data["job_id"]
        self.assertEqual(
            upload_resp.data["headers"],
            ["visitor_id", "datetime", "url", "event", "device"],
        )

        col_resp = self.client.post(
            self.map_columns_url,
            {
                "job_id": job_id,
                "mapping": {
                    "user_id": "visitor_id",
                    "timestamp": "datetime",
                    "page_url": "url",
                    "action": "event",
                    "device": "device",
                },
            },
            format="json",
        )
        self.assertEqual(col_resp.status_code, status.HTTP_200_OK)

        val_resp = self.client.post(
            self.map_values_url,
            {
                "job_id": job_id,
                "mapping": {
                    "VIEW": "page_view",
                    "CLICK": "click",
                    "ADD_CART": "add_to_cart",
                    "PURCHASE": "purchase",
                },
            },
            format="json",
        )
        self.assertEqual(val_resp.status_code, status.HTTP_200_OK)

        proc_resp = self.client.post(self.process_url, {"job_id": job_id}, format="json")
        self.assertEqual(proc_resp.status_code, status.HTTP_200_OK)
        return job_id, upload_resp, col_resp, val_resp, proc_resp

    def test_complete_e2e_pipeline_with_non_standard_csv_and_boundaries(self):
        """E2E Test 1: Full 8-stage pipeline from non-standard CSV upload to BI insights."""
        import os
        import pandas as pd

        job_id, _, _, _, proc_resp = self._upload_and_process()
        dataset = Dataset.objects.get(job_id=uuid.UUID(job_id))

        # Verify column & value mappings persisted
        self.assertEqual(dataset.column_mapping["user_id"], "visitor_id")
        self.assertEqual(dataset.column_mapping["timestamp"], "datetime")
        self.assertEqual(dataset.column_mapping["page_url"], "url")
        self.assertEqual(dataset.column_mapping["action"], "event")
        self.assertEqual(dataset.value_mapping["VIEW"], "page_view")
        self.assertEqual(dataset.value_mapping["CLICK"], "click")
        self.assertEqual(dataset.value_mapping["ADD_CART"], "add_to_cart")

        # Verify cleaning standardized columns and dropped invalid row
        self.assertTrue(os.path.exists(dataset.cleaned_file_path))
        cleaned_df = pd.read_csv(dataset.cleaned_file_path)
        for col in ("user_id", "timestamp", "page_url", "action", "device"):
            self.assertIn(col, cleaned_df.columns)
        self.assertEqual(len(cleaned_df), 10)
        self.assertNotIn("U003", cleaned_df["user_id"].astype(str).tolist())
        self.assertEqual(proc_resp.data["quality_report"]["rows_removed"], 1)

        # Stage 5: Sessionization (verifies 30-min same session vs 31-min new session)
        sess_resp = self.client.post(self.sessionize_url, {"job_id": job_id}, format="json")
        self.assertEqual(sess_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(sess_resp.data["total_users"], 2)
        self.assertEqual(sess_resp.data["total_sessions"], 3)
        dataset.refresh_from_db()
        self.assertTrue(os.path.exists(dataset.sessionized_file_path))
        sessionized_df = pd.read_csv(dataset.sessionized_file_path)
        self.assertIn("session_id", sessionized_df.columns)
        self.assertEqual(Session.objects.filter(dataset=dataset).count(), 3)

        # Stage 6: Analytics
        analyze_resp = self.client.post(self.analyze_url, {"job_id": job_id}, format="json")
        self.assertEqual(analyze_resp.status_code, status.HTTP_200_OK)
        analytics = analyze_resp.data["analytics"]
        self.assertEqual(analytics["total_users"], 2)
        self.assertEqual(analytics["total_sessions"], 3)
        self.assertEqual(analytics["total_events"], 10)
        self.assertGreater(len(analytics["most_visited_pages"]), 0)
        self.assertEqual(analytics["action_counts"]["page_view"], 7)
        self.assertEqual(analytics["action_counts"]["purchase"], 1)

        # Stage 7: Sequential Pattern Mining
        mine_resp = self.client.post(self.mine_url, {"job_id": job_id}, format="json")
        self.assertEqual(mine_resp.status_code, status.HTTP_200_OK)
        patterns = mine_resp.data["patterns"]
        self.assertGreater(len(patterns["page_patterns"]), 0)
        self.assertGreater(len(patterns["action_patterns"]), 0)
        self.assertGreater(len(patterns["transitions"]), 0)
        self.assertGreater(len(patterns["common_journeys"]), 0)

        # Stage 8: BI Insight Generation
        insights_resp = self.client.post(self.insights_url, {"job_id": job_id}, format="json")
        self.assertEqual(insights_resp.status_code, status.HTTP_200_OK)
        insights = insights_resp.data["insights"]
        self.assertGreater(len(insights), 0)
        for item in insights:
            self.assertIn("type", item)
            self.assertIn("title", item)
            self.assertIn("message", item)
            self.assertIn("severity", item)

        # Verify GET endpoints and no exposed filesystem paths
        get_analyze = self.client.get(f"{self.analyze_url}?job_id={job_id}")
        get_mine = self.client.get(f"{self.mine_url}?job_id={job_id}")
        get_insights = self.client.get(f"{self.insights_url}?job_id={job_id}")
        self.assertEqual(get_analyze.status_code, status.HTTP_200_OK)
        self.assertEqual(get_mine.status_code, status.HTTP_200_OK)
        self.assertEqual(get_insights.status_code, status.HTTP_200_OK)

        for resp in (
            sess_resp,
            analyze_resp,
            mine_resp,
            insights_resp,
            get_analyze,
            get_mine,
            get_insights,
        ):
            self.assertNotIn("file_path", resp.data)
            self.assertNotIn("cleaned_file_path", resp.data)
            self.assertNotIn("sessionized_file_path", resp.data)

    def test_pipeline_idempotency_no_duplicate_records(self):
        """E2E Test 2: Re-running sessionize, analyze, mine-patterns, and insights creates no duplicates."""
        job_id, _, _, _, _ = self._upload_and_process()
        dataset = Dataset.objects.get(job_id=uuid.UUID(job_id))

        for _ in range(2):
            self.assertEqual(
                self.client.post(self.sessionize_url, {"job_id": job_id}, format="json").status_code,
                status.HTTP_200_OK,
            )
            self.assertEqual(
                self.client.post(self.analyze_url, {"job_id": job_id}, format="json").status_code,
                status.HTTP_200_OK,
            )
            self.assertEqual(
                self.client.post(self.mine_url, {"job_id": job_id}, format="json").status_code,
                status.HTTP_200_OK,
            )
            self.assertEqual(
                self.client.post(self.insights_url, {"job_id": job_id}, format="json").status_code,
                status.HTTP_200_OK,
            )

        self.assertEqual(Session.objects.filter(dataset=dataset).count(), 3)
        self.assertEqual(AnalysisResult.objects.filter(dataset=dataset).count(), 1)
        self.assertEqual(PatternMiningResult.objects.filter(dataset=dataset).count(), 1)
        self.assertEqual(InsightResult.objects.filter(dataset=dataset).count(), 1)

    def test_pipeline_rejects_invalid_stage_order(self):
        """E2E Test 3: Downstream stages reject requests before prerequisite stages complete."""
        job_id, _, _, _, _ = self._upload_and_process()

        # Before sessionization: analyze, mine-patterns, and insights must return 400
        self.assertEqual(
            self.client.post(self.analyze_url, {"job_id": job_id}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(self.mine_url, {"job_id": job_id}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(self.insights_url, {"job_id": job_id}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # After sessionization but before analyze: insights must return 400
        self.assertEqual(
            self.client.post(self.sessionize_url, {"job_id": job_id}, format="json").status_code,
            status.HTTP_200_OK,
        )
        insights_early = self.client.post(self.insights_url, {"job_id": job_id}, format="json")
        self.assertEqual(insights_early.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Analytics must be calculated", insights_early.data["error"])


class InsightsAPITests(APITestCase):
    def setUp(self):
        self.upload_url = "/api/upload"
        self.map_url = "/api/map-columns"
        self.values_url = "/api/map-values"
        self.process_url = "/api/process"
        self.sessionize_url = "/api/sessionize"
        self.analyze_url = "/api/analyze"
        self.mine_url = "/api/mine-patterns"
        self.insights_url = "/api/insights"

        csv_content = (
            "user_id,timestamp,page_url,action,device\n"
            "U1,2026-01-01 10:00:00,/home,page_view,mobile\n"
            "U1,2026-01-01 10:02:00,/products,page_view,mobile\n"
            "U1,2026-01-01 10:04:00,/cart,purchase,mobile\n"
            "U2,2026-01-01 11:00:00,/home,page_view,desktop\n"
            "U2,2026-01-01 11:02:00,/products,page_view,desktop\n"
            "U2,2026-01-01 11:05:00,/about,page_view,desktop\n"
        ).encode("utf-8")
        uploaded = SimpleUploadedFile("insights.csv", csv_content, content_type="text/csv")
        upload_resp = self.client.post(self.upload_url, {"file": uploaded}, format="multipart")
        self.job_id = upload_resp.data["job_id"]

        self.client.post(
            self.map_url,
            {
                "job_id": self.job_id,
                "mapping": {
                    "user_id": "user_id",
                    "timestamp": "timestamp",
                    "page_url": "page_url",
                    "action": "action",
                    "device": "device",
                },
            },
            format="json",
        )
        self.client.post(
            self.values_url,
            {
                "job_id": self.job_id,
                "mapping": {"page_view": "page_view", "purchase": "purchase"},
            },
            format="json",
        )
        proc_resp = self.client.post(self.process_url, {"job_id": self.job_id}, format="json")
        self.assertEqual(proc_resp.status_code, status.HTTP_200_OK)
        sess_resp = self.client.post(self.sessionize_url, {"job_id": self.job_id}, format="json")
        self.assertEqual(sess_resp.status_code, status.HTTP_200_OK)

    def tearDown(self):
        clean_test_uploads()

    def test_post_insights_success_with_analytics_and_patterns(self):
        """Test 1: POST /api/insights generates and persists InsightResult."""
        self.client.post(self.analyze_url, {"job_id": self.job_id}, format="json")
        self.client.post(self.mine_url, {"job_id": self.job_id}, format="json")

        resp = self.client.post(self.insights_url, {"job_id": self.job_id}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(str(resp.data["job_id"]), self.job_id)
        self.assertEqual(resp.data["status"], Dataset.STATUS_COMPLETED)
        self.assertIsInstance(resp.data["insights"], list)
        self.assertGreater(len(resp.data["insights"]), 0)
        self.assertTrue(
            InsightResult.objects.filter(dataset__job_id=uuid.UUID(self.job_id)).exists()
        )

    def test_get_insights_success(self):
        """Test 2: GET /api/insights?job_id=... returns saved insights."""
        self.client.post(self.analyze_url, {"job_id": self.job_id}, format="json")
        post_resp = self.client.post(self.insights_url, {"job_id": self.job_id}, format="json")

        get_resp = self.client.get(f"{self.insights_url}?job_id={self.job_id}")
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(get_resp.data["insights"], post_resp.data["insights"])

    def test_missing_and_invalid_job_id_return_400(self):
        """Tests 3 & 4: Missing or malformed job_id returns HTTP 400 on POST and GET."""
        self.assertEqual(
            self.client.post(self.insights_url, {}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(self.insights_url, {"job_id": "bad-uuid"}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get(self.insights_url).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get(f"{self.insights_url}?job_id=bad-uuid").status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_nonexistent_dataset_returns_404(self):
        """Test 5: Unknown job_id UUID returns HTTP 404."""
        unknown = str(uuid.uuid4())
        self.assertEqual(
            self.client.post(self.insights_url, {"job_id": unknown}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(f"{self.insights_url}?job_id={unknown}").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_analytics_not_calculated_returns_400_and_get_returns_404(self):
        """Test 6: POST /api/insights without AnalysisResult returns HTTP 400."""
        post_resp = self.client.post(self.insights_url, {"job_id": self.job_id}, format="json")
        self.assertEqual(post_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Analytics must be calculated", post_resp.data["error"])

        get_resp = self.client.get(f"{self.insights_url}?job_id={self.job_id}")
        self.assertEqual(get_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_pattern_mining_not_calculated_still_succeeds(self):
        """Test 7: POST /api/insights succeeds using analytics only when PatternMiningResult is absent."""
        self.client.post(self.analyze_url, {"job_id": self.job_id}, format="json")
        resp = self.client.post(self.insights_url, {"job_id": self.job_id}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreater(len(resp.data["insights"]), 0)
        self.assertEqual(
            [i for i in resp.data["insights"] if i["type"] == "navigation"],
            [],
        )

    def test_rerunning_insights_updates_existing_result(self):
        """Test 8: Re-running POST /api/insights updates existing InsightResult without duplicates."""
        self.client.post(self.analyze_url, {"job_id": self.job_id}, format="json")
        resp1 = self.client.post(self.insights_url, {"job_id": self.job_id}, format="json")
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # Now run pattern mining and re-run insights
        self.client.post(self.mine_url, {"job_id": self.job_id}, format="json")
        resp2 = self.client.post(self.insights_url, {"job_id": self.job_id}, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

        qs = InsightResult.objects.filter(dataset__job_id=uuid.UUID(self.job_id))
        self.assertEqual(qs.count(), 1)
        self.assertTrue(any(i["type"] == "navigation" for i in qs.first().insights))

    def test_filesystem_paths_not_exposed(self):
        """Test 9: Responses from POST and GET /api/insights never expose file paths."""
        self.client.post(self.analyze_url, {"job_id": self.job_id}, format="json")
        post_resp = self.client.post(self.insights_url, {"job_id": self.job_id}, format="json")
        get_resp = self.client.get(f"{self.insights_url}?job_id={self.job_id}")

        for resp in (post_resp, get_resp):
            self.assertNotIn("sessionized_file_path", resp.data)
            self.assertNotIn("cleaned_file_path", resp.data)
            self.assertNotIn("file_path", resp.data)


class EndToEndPipelineIntegrationTests(APITestCase):
    def setUp(self):
        self.upload_url = reverse('dataset-upload')
        self.map_columns_url = reverse('map-columns')
        self.map_values_url = reverse('map-values')
        self.process_url = reverse('process-dataset')
        self.sessionize_url = reverse('sessionize-dataset')
        self.analyze_url = reverse('analyze-dataset')
        self.mine_url = reverse('mine-patterns')
        self.insights_url = reverse('insights')

        self.csv_content = (
            "visitor_id,datetime,url,event,device\n"
            # U001 Session 1: 18:00 -> 18:05 -> 18:35 (exact 30-min gap, same session) -> 18:38
            "U001,2026-11-10 18:00:00,/home,VIEW,mobile\n"
            "U001,2026-11-10 18:05:00,/products,VIEW,mobile\n"
            "U001,2026-11-10 18:35:00,/laptops,CLICK,mobile\n"
            "U001,2026-11-10 18:38:00,/cart,ADD_CART,mobile\n"
            # U001 Session 2: 19:09 (31-min gap from 18:38, new session)
            "U001,2026-11-10 19:09:00,/home,VIEW,mobile\n"
            "U001,2026-11-10 19:12:00,/products,VIEW,mobile\n"
            "U001,2026-11-10 19:15:00,/checkout,PURCHASE,mobile\n"
            # U002 Session 3
            "U002,2026-11-10 19:00:00,/home,VIEW,desktop\n"
            "U002,2026-11-10 19:04:00,/products,VIEW,desktop\n"
            "U002,2026-11-10 19:08:00,/cart,VIEW,desktop\n"
            # Invalid row (missing timestamp) to verify cleaning drops it
            "U003,,/broken,VIEW,desktop\n"
        ).encode("utf-8")

    def tearDown(self):
        clean_test_uploads()

    def _upload_and_process(self):
        uploaded = SimpleUploadedFile("e2e_nonstandard.csv", self.csv_content, content_type="text/csv")
        upload_resp = self.client.post(self.upload_url, {"file": uploaded}, format="multipart")
        self.assertEqual(upload_resp.status_code, status.HTTP_201_CREATED)
        job_id = upload_resp.data["job_id"]
        self.assertEqual(
            upload_resp.data["headers"],
            ["visitor_id", "datetime", "url", "event", "device"],
        )

        col_resp = self.client.post(
            self.map_columns_url,
            {
                "job_id": job_id,
                "mapping": {
                    "user_id": "visitor_id",
                    "timestamp": "datetime",
                    "page_url": "url",
                    "action": "event",
                    "device": "device",
                },
            },
            format="json",
        )
        self.assertEqual(col_resp.status_code, status.HTTP_200_OK)

        val_resp = self.client.post(
            self.map_values_url,
            {
                "job_id": job_id,
                "mapping": {
                    "VIEW": "page_view",
                    "CLICK": "click",
                    "ADD_CART": "add_to_cart",
                    "PURCHASE": "purchase",
                },
            },
            format="json",
        )
        self.assertEqual(val_resp.status_code, status.HTTP_200_OK)

        proc_resp = self.client.post(self.process_url, {"job_id": job_id}, format="json")
        self.assertEqual(proc_resp.status_code, status.HTTP_200_OK)
        return job_id, upload_resp, col_resp, val_resp, proc_resp

    def test_complete_e2e_pipeline_with_non_standard_csv_and_boundaries(self):
        """E2E Test 1: Full 8-stage pipeline from non-standard CSV upload to BI insights."""
        import os
        import pandas as pd

        job_id, _, _, _, proc_resp = self._upload_and_process()
        dataset = Dataset.objects.get(job_id=uuid.UUID(job_id))

        # Verify column & value mappings persisted
        self.assertEqual(dataset.column_mapping["user_id"], "visitor_id")
        self.assertEqual(dataset.column_mapping["timestamp"], "datetime")
        self.assertEqual(dataset.column_mapping["page_url"], "url")
        self.assertEqual(dataset.column_mapping["action"], "event")
        self.assertEqual(dataset.value_mapping["VIEW"], "page_view")
        self.assertEqual(dataset.value_mapping["CLICK"], "click")
        self.assertEqual(dataset.value_mapping["ADD_CART"], "add_to_cart")

        # Verify cleaning standardized columns and dropped invalid row
        self.assertTrue(os.path.exists(dataset.cleaned_file_path))
        cleaned_df = pd.read_csv(dataset.cleaned_file_path)
        for col in ("user_id", "timestamp", "page_url", "action", "device"):
            self.assertIn(col, cleaned_df.columns)
        self.assertEqual(len(cleaned_df), 10)
        self.assertNotIn("U003", cleaned_df["user_id"].astype(str).tolist())
        self.assertEqual(proc_resp.data["quality_report"]["rows_removed"], 1)

        # Stage 5: Sessionization (verifies 30-min same session vs 31-min new session)
        sess_resp = self.client.post(self.sessionize_url, {"job_id": job_id}, format="json")
        self.assertEqual(sess_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(sess_resp.data["total_users"], 2)
        self.assertEqual(sess_resp.data["total_sessions"], 3)
        dataset.refresh_from_db()
        self.assertTrue(os.path.exists(dataset.sessionized_file_path))
        sessionized_df = pd.read_csv(dataset.sessionized_file_path)
        self.assertIn("session_id", sessionized_df.columns)
        self.assertEqual(Session.objects.filter(dataset=dataset).count(), 3)

        # Stage 6: Analytics
        analyze_resp = self.client.post(self.analyze_url, {"job_id": job_id}, format="json")
        self.assertEqual(analyze_resp.status_code, status.HTTP_200_OK)
        analytics = analyze_resp.data["analytics"]
        self.assertEqual(analytics["total_users"], 2)
        self.assertEqual(analytics["total_sessions"], 3)
        self.assertEqual(analytics["total_events"], 10)
        self.assertGreater(len(analytics["most_visited_pages"]), 0)
        self.assertEqual(analytics["action_counts"]["page_view"], 7)
        self.assertEqual(analytics["action_counts"]["purchase"], 1)

        # Stage 7: Sequential Pattern Mining
        mine_resp = self.client.post(self.mine_url, {"job_id": job_id}, format="json")
        self.assertEqual(mine_resp.status_code, status.HTTP_200_OK)
        patterns = mine_resp.data["patterns"]
        self.assertGreater(len(patterns["page_patterns"]), 0)
        self.assertGreater(len(patterns["action_patterns"]), 0)
        self.assertGreater(len(patterns["transitions"]), 0)
        self.assertGreater(len(patterns["common_journeys"]), 0)

        # Stage 8: BI Insight Generation
        insights_resp = self.client.post(self.insights_url, {"job_id": job_id}, format="json")
        self.assertEqual(insights_resp.status_code, status.HTTP_200_OK)
        insights = insights_resp.data["insights"]
        self.assertGreater(len(insights), 0)
        for item in insights:
            self.assertIn("type", item)
            self.assertIn("title", item)
            self.assertIn("message", item)
            self.assertIn("severity", item)

        # Verify GET endpoints and no exposed filesystem paths
        get_analyze = self.client.get(f"{self.analyze_url}?job_id={job_id}")
        get_mine = self.client.get(f"{self.mine_url}?job_id={job_id}")
        get_insights = self.client.get(f"{self.insights_url}?job_id={job_id}")
        self.assertEqual(get_analyze.status_code, status.HTTP_200_OK)
        self.assertEqual(get_mine.status_code, status.HTTP_200_OK)
        self.assertEqual(get_insights.status_code, status.HTTP_200_OK)

        for resp in (
            sess_resp,
            analyze_resp,
            mine_resp,
            insights_resp,
            get_analyze,
            get_mine,
            get_insights,
        ):
            self.assertNotIn("file_path", resp.data)
            self.assertNotIn("cleaned_file_path", resp.data)
            self.assertNotIn("sessionized_file_path", resp.data)

    def test_pipeline_idempotency_no_duplicate_records(self):
        """E2E Test 2: Re-running sessionize, analyze, mine-patterns, and insights creates no duplicates."""
        job_id, _, _, _, _ = self._upload_and_process()
        dataset = Dataset.objects.get(job_id=uuid.UUID(job_id))

        for _ in range(2):
            self.assertEqual(
                self.client.post(self.sessionize_url, {"job_id": job_id}, format="json").status_code,
                status.HTTP_200_OK,
            )
            self.assertEqual(
                self.client.post(self.analyze_url, {"job_id": job_id}, format="json").status_code,
                status.HTTP_200_OK,
            )
            self.assertEqual(
                self.client.post(self.mine_url, {"job_id": job_id}, format="json").status_code,
                status.HTTP_200_OK,
            )
            self.assertEqual(
                self.client.post(self.insights_url, {"job_id": job_id}, format="json").status_code,
                status.HTTP_200_OK,
            )

        self.assertEqual(Session.objects.filter(dataset=dataset).count(), 3)
        self.assertEqual(AnalysisResult.objects.filter(dataset=dataset).count(), 1)
        self.assertEqual(PatternMiningResult.objects.filter(dataset=dataset).count(), 1)
        self.assertEqual(InsightResult.objects.filter(dataset=dataset).count(), 1)

    def test_pipeline_rejects_invalid_stage_order(self):
        """E2E Test 3: Downstream stages reject requests before prerequisite stages complete."""
        job_id, _, _, _, _ = self._upload_and_process()

        # Before sessionization: analyze, mine-patterns, and insights must return 400
        self.assertEqual(
            self.client.post(self.analyze_url, {"job_id": job_id}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(self.mine_url, {"job_id": job_id}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(self.insights_url, {"job_id": job_id}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # After sessionization but before analyze: insights must return 400
        self.assertEqual(
            self.client.post(self.sessionize_url, {"job_id": job_id}, format="json").status_code,
            status.HTTP_200_OK,
        )
        insights_early = self.client.post(self.insights_url, {"job_id": job_id}, format="json")
        self.assertEqual(insights_early.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Analytics must be calculated", insights_early.data["error"])


class CorsHeadersAPITests(APITestCase):
    def test_cors_preflight_allowed_for_localhost(self):
        response = self.client.options(
            '/api/upload',
            HTTP_ORIGIN='http://localhost:5173',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), 'http://localhost:5173')

    def test_cors_preflight_allowed_for_vercel_domain(self):
        response = self.client.options(
            '/api/upload',
            HTTP_ORIGIN='https://web-access-mining.vercel.app',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), 'https://web-access-mining.vercel.app')

    def test_cors_preflight_rejected_for_disallowed_origin(self):
        response = self.client.options(
            '/api/upload',
            HTTP_ORIGIN='https://malicious-site.com',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )
        self.assertIsNone(response.headers.get('Access-Control-Allow-Origin'))





