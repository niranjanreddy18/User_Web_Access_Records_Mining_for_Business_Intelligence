import os
import uuid
from django.conf import settings
import pandas as pd
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from processing.analytics import calculate_analytics
from processing.cleaning import clean_dataset, REQUIRED_FIELDS
from processing.insights import generate_insights
from processing.mapping import map_columns, validate_manual_mapping
from processing.pattern_mining import mine_patterns, validate_mining_params
from processing.sessionization import (
    DEFAULT_TIMEOUT_MINUTES,
    sessionize_dataset,
    validate_timeout_minutes,
)
from processing.value_mapping import (
    ALLOWED_ACTIONS,
    get_unique_action_values,
    map_action_values,
    validate_manual_value_mapping,
)
from .models import AnalysisResult, Dataset, InsightResult, PatternMiningResult, Session
from .serializers import (
    AnalyzeResponseSerializer,
    ColumnMappingResponseSerializer,
    DatasetUploadResponseSerializer,
    InsightsResponseSerializer,
    MinePatternsResponseSerializer,
    ProcessResponseSerializer,
    SessionizeResponseSerializer,
    ValueMappingResponseSerializer,
)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


class DatasetUploadView(APIView):
    """
    POST /api/upload
    Accepts multipart/form-data CSV file upload, validates it,
    persists the file to disk, creates a Dataset instance, extracts column headers,
    performs automatic column mapping, and returns job_id, headers, and mapping info.
    """
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        # 1. Validate file presence
        if 'file' not in request.FILES:
            return Response(
                {"error": "No file was provided under the field 'file'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_file = request.FILES['file']

        # 2. Validate filename extension (.csv)
        filename = uploaded_file.name or ''
        if not filename.lower().endswith('.csv'):
            return Response(
                {"error": "Invalid file format. Only CSV files (.csv) are accepted."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Validate file size does not exceed 50 MB
        if uploaded_file.size > MAX_FILE_SIZE:
            return Response(
                {"error": f"File size exceeds the 50 MB limit. Uploaded size: {uploaded_file.size} bytes."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )

        # 4. Validate file is not empty
        if uploaded_file.size == 0:
            return Response(
                {"error": "The uploaded CSV file is empty."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 5. Parse CSV using Pandas to read column headers and check validity
        try:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, nrows=5)
            headers = [str(col) for col in df.columns.tolist()]
            if not headers:
                return Response(
                    {"error": "The CSV file does not contain any column headers."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except pd.errors.EmptyDataError:
            return Response(
                {"error": "The CSV file is empty or contains no data."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (pd.errors.ParserError, UnicodeDecodeError) as e:
            return Response(
                {"error": f"Malformed or unreadable CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to parse CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 6. Perform automatic column mapping (does not fail upload if unmapped)
        mapping_result = map_columns(headers)

        # 7. Persist CSV file to disk for subsequent pipeline phases
        job_id = uuid.uuid4()
        uploads_dir = os.path.join(settings.BASE_DIR, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        saved_file_path = os.path.join(uploads_dir, f"{job_id}.csv")

        uploaded_file.seek(0)
        with open(saved_file_path, 'wb+') as dest:
            for chunk in uploaded_file.chunks():
                dest.write(chunk)

        # 8. Create Dataset record
        dataset = Dataset.objects.create(
            job_id=job_id,
            filename=filename,
            file_path=saved_file_path,
            status=Dataset.STATUS_UPLOADED,
            headers=headers,
            column_mapping={},
            value_mapping={},
            quality_report={},
        )

        dataset.auto_mapping = mapping_result["auto_mapping"]
        dataset.unmapped_required = mapping_result["unmapped_required"]
        dataset.unmapped_optional = mapping_result["unmapped_optional"]

        # 9. Return response
        response_serializer = DatasetUploadResponseSerializer(dataset)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ColumnMappingView(APIView):
    """
    POST /api/map-columns
    Accepts user-defined manual column mapping for an existing dataset job.
    Validates required fields, source columns, and uniqueness, then updates
    dataset status to 'mapping'.

    GET /api/map-columns?job_id=<uuid>
    Returns header information, automatic mapping suggestions, and any saved mapping.
    """
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request, *args, **kwargs):
        job_id_param = request.query_params.get('job_id')
        if not job_id_param:
            return Response(
                {"error": "Query parameter 'job_id' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            job_id = uuid.UUID(str(job_id_param))
        except (ValueError, TypeError):
            return Response(
                {"error": f"Invalid UUID format for 'job_id': {job_id_param}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            dataset = Dataset.objects.get(job_id=job_id)
        except Dataset.DoesNotExist:
            return Response(
                {"error": f"Dataset with job_id '{job_id}' does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        mapping_result = map_columns(dataset.headers)

        return Response(
            {
                "job_id": str(dataset.job_id),
                "headers": dataset.headers,
                "auto_mapping": mapping_result["auto_mapping"],
                "unmapped_required": mapping_result["unmapped_required"],
                "unmapped_optional": mapping_result["unmapped_optional"],
                "column_mapping": dataset.column_mapping,
                "status": dataset.status,
            },
            status=status.HTTP_200_OK
        )

    def post(self, request, *args, **kwargs):
        # 1. Validate job_id in request body
        if 'job_id' not in request.data:
            return Response(
                {"error": "Field 'job_id' is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        job_id_val = request.data.get('job_id')
        try:
            job_id = uuid.UUID(str(job_id_val))
        except (ValueError, TypeError):
            return Response(
                {"error": f"Invalid UUID format for 'job_id': '{job_id_val}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Validate mapping object in request body
        if 'mapping' not in request.data:
            return Response(
                {"error": "Field 'mapping' is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        mapping = request.data.get('mapping')
        if not isinstance(mapping, dict):
            return Response(
                {"error": "Field 'mapping' must be a JSON object/dictionary."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Check dataset existence
        try:
            dataset = Dataset.objects.get(job_id=job_id)
        except Dataset.DoesNotExist:
            return Response(
                {"error": f"Dataset with job_id '{job_id}' does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 4. Validate manual mapping against uploaded dataset headers
        is_valid, error_msg, normalized_mapping = validate_manual_mapping(
            dataset.headers, mapping
        )
        if not is_valid:
            return Response(
                {"error": error_msg},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 5. Persist column mapping and transition status to 'mapping'
        dataset.column_mapping = normalized_mapping
        dataset.status = Dataset.STATUS_MAPPING
        dataset.save()

        # 6. Return response
        response_serializer = ColumnMappingResponseSerializer(dataset)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class ValueMappingView(APIView):
    """
    POST /api/map-values
    Accepts user-defined manual value mapping for the action column.
    Validates that every source value exists, every target action is in ALLOWED_ACTIONS,
    and no unknown action values silently disappear.

    GET /api/map-values?job_id=<uuid>
    Returns unique action values from the action column, automatic mapping suggestions,
    unknown values, and allowed target actions.
    """
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request, *args, **kwargs):
        job_id_param = request.query_params.get('job_id')
        if not job_id_param:
            return Response(
                {"error": "Query parameter 'job_id' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            job_id = uuid.UUID(str(job_id_param))
        except (ValueError, TypeError):
            return Response(
                {"error": f"Invalid UUID format for 'job_id': {job_id_param}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            dataset = Dataset.objects.get(job_id=job_id)
        except Dataset.DoesNotExist:
            return Response(
                {"error": f"Dataset with job_id '{job_id}' does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not dataset.column_mapping or 'action' not in dataset.column_mapping:
            return Response(
                {"error": "Column mapping has not been completed. The 'action' column must be mapped first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            unique_vals = get_unique_action_values(dataset)
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        mapping_result = map_action_values(unique_vals)

        return Response(
            {
                "job_id": str(dataset.job_id),
                "status": dataset.status,
                "unique_values": unique_vals,
                "auto_mapping": mapping_result["auto_mapping"],
                "unknown_values": mapping_result["unknown_values"],
                "allowed_actions": ALLOWED_ACTIONS,
                "value_mapping": dataset.value_mapping,
            },
            status=status.HTTP_200_OK
        )

    def post(self, request, *args, **kwargs):
        # 1. Validate job_id
        if 'job_id' not in request.data:
            return Response(
                {"error": "Field 'job_id' is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        job_id_val = request.data.get('job_id')
        try:
            job_id = uuid.UUID(str(job_id_val))
        except (ValueError, TypeError):
            return Response(
                {"error": f"Invalid UUID format for 'job_id': '{job_id_val}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Validate mapping object
        if 'mapping' not in request.data:
            return Response(
                {"error": "Field 'mapping' is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_mapping = request.data.get('mapping')
        if not isinstance(user_mapping, dict):
            return Response(
                {"error": "Field 'mapping' must be a JSON object/dictionary."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user_mapping:
            return Response(
                {"error": "Field 'mapping' cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Check dataset existence
        try:
            dataset = Dataset.objects.get(job_id=job_id)
        except Dataset.DoesNotExist:
            return Response(
                {"error": f"Dataset with job_id '{job_id}' does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 4. Check action column mapping
        if not dataset.column_mapping or 'action' not in dataset.column_mapping:
            return Response(
                {"error": "Column mapping has not been completed. The 'action' column must be mapped first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            unique_vals = get_unique_action_values(dataset)
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 5. Extract auto mapping for unique values
        auto_result = map_action_values(unique_vals)

        # 6. Validate manual value mapping
        is_valid, err_msg, final_mapping = validate_manual_value_mapping(
            unique_action_values=unique_vals,
            user_mapping=user_mapping,
            auto_mapping=auto_result["auto_mapping"],
        )
        if not is_valid:
            return Response(
                {"error": err_msg},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 7. Persist value mapping and remain in 'mapping' status
        dataset.value_mapping = final_mapping
        dataset.status = Dataset.STATUS_MAPPING
        dataset.save()

        # 8. Return response
        response_serializer = ValueMappingResponseSerializer(dataset)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class ProcessDatasetView(APIView):
    """
    POST /api/process
    Validates that column mapping and value mapping are complete, standardizes
    and cleans the dataset, removes invalid and duplicate rows, records the quality
    report, and transitions status from 'processing' to 'completed' (or 'failed' on error).

    GET /api/process?job_id=<uuid>
    Returns current processing status and quality report.
    """
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request, *args, **kwargs):
        job_id_param = request.query_params.get('job_id')
        if not job_id_param:
            return Response(
                {"error": "Query parameter 'job_id' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            job_id = uuid.UUID(str(job_id_param))
        except (ValueError, TypeError):
            return Response(
                {"error": f"Invalid UUID format for 'job_id': '{job_id_param}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            dataset = Dataset.objects.get(job_id=job_id)
        except Dataset.DoesNotExist:
            return Response(
                {"error": f"Dataset with job_id '{job_id}' does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        response_serializer = ProcessResponseSerializer(dataset)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        # 1. Validate job_id presence and format
        if 'job_id' not in request.data:
            return Response(
                {"error": "Field 'job_id' is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        job_id_val = request.data.get('job_id')
        try:
            job_id = uuid.UUID(str(job_id_val))
        except (ValueError, TypeError):
            return Response(
                {"error": f"Invalid UUID format for 'job_id': '{job_id_val}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Retrieve dataset
        try:
            dataset = Dataset.objects.get(job_id=job_id)
        except Dataset.DoesNotExist:
            return Response(
                {"error": f"Dataset with job_id '{job_id}' does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 3. Verify column mapping exists and contains all required fields
        if not dataset.column_mapping or not isinstance(dataset.column_mapping, dict):
            return Response(
                {"error": "Column mapping must be completed before processing."},
                status=status.HTTP_400_BAD_REQUEST
            )

        missing_required = [f for f in REQUIRED_FIELDS if f not in dataset.column_mapping]
        if missing_required:
            return Response(
                {"error": f"Missing required column mapping(s): {', '.join(missing_required)}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. Verify value mapping exists
        if not dataset.value_mapping or not isinstance(dataset.value_mapping, dict):
            return Response(
                {"error": "Value mapping must be completed before processing."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 5. Transition status to 'processing'
        dataset.status = Dataset.STATUS_PROCESSING
        dataset.save(update_fields=['status'])

        # 6. Execute data cleaning and standardization
        try:
            df_clean, quality_report = clean_dataset(dataset)
            dataset.quality_report = quality_report
            dataset.cleaned_file_path = os.path.join(
                settings.BASE_DIR, 'uploads', f"cleaned_{dataset.job_id}.csv"
            )
            dataset.status = Dataset.STATUS_COMPLETED
            dataset.save()

            response_serializer = ProcessResponseSerializer(dataset)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            dataset.status = Dataset.STATUS_FAILED
            dataset.save(update_fields=['status'])
            return Response(
                {"error": f"Data processing failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class SessionizeDatasetView(APIView):
    """
    POST /api/sessionize
    Sessionizes the cleaned CSV for a completed dataset using an inactivity timeout
    (default 30 minutes), writes the sessionized CSV, replaces existing Session records
    for idempotent reruns, and returns sessionization summary metrics.

    GET /api/sessionize?job_id=<uuid>
    Returns current sessionization summary for the dataset.
    """
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request, *args, **kwargs):
        job_id_param = request.query_params.get('job_id')
        if not job_id_param:
            return Response(
                {"error": "Query parameter 'job_id' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            job_id = uuid.UUID(str(job_id_param))
        except (ValueError, TypeError):
            return Response(
                {"error": f"Invalid UUID format for 'job_id': '{job_id_param}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            dataset = Dataset.objects.get(job_id=job_id)
        except Dataset.DoesNotExist:
            return Response(
                {"error": f"Dataset with job_id '{job_id}' does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        sessions_qs = Session.objects.filter(dataset=dataset)
        return Response(
            {
                "job_id": str(dataset.job_id),
                "status": dataset.status,
                "total_sessions": sessions_qs.count(),
                "total_users": sessions_qs.values('user_id').distinct().count(),
                "sessionized_file_available": bool(
                    dataset.sessionized_file_path and os.path.exists(dataset.sessionized_file_path)
                ),
            },
            status=status.HTTP_200_OK
        )

    def post(self, request, *args, **kwargs):
        # 1. Validate job_id presence and format
        if 'job_id' not in request.data:
            return Response(
                {"error": "Field 'job_id' is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        job_id_val = request.data.get('job_id')
        try:
            job_id = uuid.UUID(str(job_id_val))
        except (ValueError, TypeError):
            return Response(
                {"error": f"Invalid UUID format for 'job_id': '{job_id_val}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Validate timeout_minutes if supplied
        raw_timeout = request.data.get('timeout_minutes', DEFAULT_TIMEOUT_MINUTES)
        if 'timeout_minutes' in request.data:
            raw_timeout = request.data.get('timeout_minutes')
        try:
            timeout_val = validate_timeout_minutes(raw_timeout)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Retrieve dataset
        try:
            dataset = Dataset.objects.get(job_id=job_id)
        except Dataset.DoesNotExist:
            return Response(
                {"error": f"Dataset with job_id '{job_id}' does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 4. Validate cleaning completed and cleaned CSV exists
        if dataset.status != Dataset.STATUS_COMPLETED:
            return Response(
                {"error": "Dataset cleaning must be completed before sessionization."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not dataset.cleaned_file_path or not os.path.exists(dataset.cleaned_file_path):
            return Response(
                {"error": "Cleaned CSV file is missing or unavailable."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 5. Run sessionization
        try:
            _, summary = sessionize_dataset(dataset, timeout_minutes=timeout_val)
            return Response(summary, status=status.HTTP_200_OK)
        except (FileNotFoundError, ValueError) as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            dataset.status = Dataset.STATUS_FAILED
            dataset.save(update_fields=['status'])
            return Response(
                {"error": f"Sessionization failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


def _fetch_dataset_by_job_id(raw_job_id, missing_msg):
    """Validate UUID job_id and retrieve matching Dataset or error Response."""
    if raw_job_id is None or str(raw_job_id).strip() == "":
        return None, Response(
            {"error": missing_msg},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        parsed_uuid = uuid.UUID(str(raw_job_id))
    except (ValueError, TypeError):
        return None, Response(
            {"error": f"Invalid UUID format for 'job_id': '{raw_job_id}'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        dataset = Dataset.objects.get(job_id=parsed_uuid)
    except Dataset.DoesNotExist:
        return None, Response(
            {"error": f"Dataset with job_id '{parsed_uuid}' does not exist."},
            status=status.HTTP_404_NOT_FOUND
        )
    return dataset, None


class AnalyzeDatasetView(APIView):
    """
    POST /api/analyze -> calculates and persists web access analytics for a sessionized dataset.
    GET /api/analyze?job_id=<uuid> -> returns previously calculated analytics.
    """
    parser_classes = [JSONParser]

    def _build_response(self, dataset, analytics_data):
        serializer = AnalyzeResponseSerializer({
            "job_id": dataset.job_id,
            "status": Dataset.STATUS_COMPLETED,
            "analytics": analytics_data,
        })
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get(self, request, *args, **kwargs):
        dataset, error_response = _fetch_dataset_by_job_id(
            request.query_params.get('job_id'),
            "Query parameter 'job_id' is required."
        )
        if error_response is not None:
            return error_response

        analysis_result = AnalysisResult.objects.filter(dataset=dataset).first()
        if analysis_result is None:
            return Response(
                {"error": "Analytics have not been calculated for this dataset yet."},
                status=status.HTTP_404_NOT_FOUND
            )

        return self._build_response(dataset, analysis_result.results)

    def post(self, request, *args, **kwargs):
        if 'job_id' not in request.data:
            return Response(
                {"error": "Field 'job_id' is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        dataset, error_response = _fetch_dataset_by_job_id(
            request.data.get('job_id'),
            "Field 'job_id' is required in the request body."
        )
        if error_response is not None:
            return error_response

        if not dataset.sessionized_file_path or not os.path.exists(dataset.sessionized_file_path):
            return Response(
                {"error": "Sessionization must be completed before analytics can be calculated."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            analytics = calculate_analytics(dataset)
        except (FileNotFoundError, ValueError) as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Analytics calculation failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        AnalysisResult.objects.update_or_create(
            dataset=dataset,
            defaults={"results": analytics},
        )

        return self._build_response(dataset, analytics)


class MinePatternsView(APIView):
    """
    POST /api/mine-patterns -> runs sequential pattern mining and persists results.
    GET /api/mine-patterns?job_id=<uuid> -> returns previously mined patterns.
    """
    parser_classes = [JSONParser]

    def _build_response(self, dataset, min_support, max_pattern_length, patterns):
        serializer = MinePatternsResponseSerializer({
            "job_id": dataset.job_id,
            "status": Dataset.STATUS_COMPLETED,
            "min_support": min_support,
            "max_pattern_length": max_pattern_length,
            "patterns": patterns,
        })
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get(self, request, *args, **kwargs):
        dataset, error_response = _fetch_dataset_by_job_id(
            request.query_params.get('job_id'),
            "Query parameter 'job_id' is required."
        )
        if error_response is not None:
            return error_response

        mining_result = PatternMiningResult.objects.filter(dataset=dataset).first()
        if mining_result is None:
            return Response(
                {"error": "Pattern mining has not been executed for this dataset yet."},
                status=status.HTTP_404_NOT_FOUND
            )

        return self._build_response(
            dataset,
            mining_result.min_support,
            mining_result.max_pattern_length,
            mining_result.results,
        )

    def post(self, request, *args, **kwargs):
        if 'job_id' not in request.data:
            return Response(
                {"error": "Field 'job_id' is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        raw_min_support = request.data['min_support'] if 'min_support' in request.data else 0.1
        raw_max_length = (
            request.data['max_pattern_length']
            if 'max_pattern_length' in request.data
            else 3
        )
        try:
            min_support_val, max_len_val = validate_mining_params(
                min_support=raw_min_support,
                max_pattern_length=raw_max_length,
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        dataset, error_response = _fetch_dataset_by_job_id(
            request.data.get('job_id'),
            "Field 'job_id' is required in the request body."
        )
        if error_response is not None:
            return error_response

        if not dataset.sessionized_file_path or not os.path.exists(dataset.sessionized_file_path):
            return Response(
                {"error": "Sessionization must be completed before pattern mining can run."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            patterns = mine_patterns(
                dataset,
                min_support=min_support_val,
                max_pattern_length=max_len_val,
            )
        except (FileNotFoundError, ValueError) as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Pattern mining failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        PatternMiningResult.objects.update_or_create(
            dataset=dataset,
            defaults={
                "results": patterns,
                "min_support": min_support_val,
                "max_pattern_length": max_len_val,
            },
        )

        return self._build_response(dataset, min_support_val, max_len_val, patterns)


class InsightsView(APIView):
    """
    POST /api/insights -> generates and persists BI insights from analytics and optional patterns.
    GET /api/insights?job_id=<uuid> -> returns previously generated BI insights.
    """
    parser_classes = [JSONParser]

    def _build_response(self, dataset, insights):
        serializer = InsightsResponseSerializer({
            "job_id": dataset.job_id,
            "status": Dataset.STATUS_COMPLETED,
            "insights": insights,
        })
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get(self, request, *args, **kwargs):
        dataset, error_response = _fetch_dataset_by_job_id(
            request.query_params.get('job_id'),
            "Query parameter 'job_id' is required."
        )
        if error_response is not None:
            return error_response

        insight_result = InsightResult.objects.filter(dataset=dataset).first()
        if insight_result is None:
            return Response(
                {"error": "Insights have not been generated for this dataset yet."},
                status=status.HTTP_404_NOT_FOUND
            )

        return self._build_response(dataset, insight_result.insights)

    def post(self, request, *args, **kwargs):
        if 'job_id' not in request.data:
            return Response(
                {"error": "Field 'job_id' is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        dataset, error_response = _fetch_dataset_by_job_id(
            request.data.get('job_id'),
            "Field 'job_id' is required in the request body."
        )
        if error_response is not None:
            return error_response

        if not AnalysisResult.objects.filter(dataset=dataset).exists():
            return Response(
                {"error": "Analytics must be calculated before generating insights."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            insights = generate_insights(dataset)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Insight generation failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        InsightResult.objects.update_or_create(
            dataset=dataset,
            defaults={"insights": insights},
        )

        return self._build_response(dataset, insights)
