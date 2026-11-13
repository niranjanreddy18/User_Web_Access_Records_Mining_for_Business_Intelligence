from rest_framework import serializers
from .models import Dataset


class DatasetUploadSerializer(serializers.Serializer):
    """
    Serializer to validate incoming file upload request.
    """
    file = serializers.FileField(required=True)


class DatasetUploadResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for the upload response containing dataset metadata, parsed headers,
    and automatic column mapping suggestions.
    """
    headers = serializers.ListField(child=serializers.CharField(), required=False)
    auto_mapping = serializers.DictField(child=serializers.CharField(), required=False)
    unmapped_required = serializers.ListField(child=serializers.CharField(), required=False)
    unmapped_optional = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = Dataset
        fields = [
            'job_id',
            'filename',
            'status',
            'headers',
            'auto_mapping',
            'unmapped_required',
            'unmapped_optional',
        ]


class ColumnMappingRequestSerializer(serializers.Serializer):
    """
    Serializer to validate the incoming manual column mapping request.
    """
    job_id = serializers.UUIDField(required=True)
    mapping = serializers.DictField(required=True)


class ColumnMappingResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for the column mapping submission response.
    """
    mapping = serializers.DictField(source='column_mapping', read_only=True)

    class Meta:
        model = Dataset
        fields = ['job_id', 'status', 'mapping', 'column_mapping']


class ValueMappingRequestSerializer(serializers.Serializer):
    """
    Serializer to validate incoming manual value mapping request.
    """
    job_id = serializers.UUIDField(required=True)
    mapping = serializers.DictField(required=True)


class ValueMappingResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for value mapping submission response.
    """
    mapping = serializers.DictField(source='value_mapping', read_only=True)

    class Meta:
        model = Dataset
        fields = ['job_id', 'status', 'mapping', 'value_mapping']


class ProcessRequestSerializer(serializers.Serializer):
    """
    Serializer to validate incoming process request.
    """
    job_id = serializers.UUIDField(required=True)


class ProcessResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for dataset processing response including quality report.
    """
    class Meta:
        model = Dataset
        fields = ['job_id', 'status', 'quality_report']


class SessionizeRequestSerializer(serializers.Serializer):
    """
    Serializer to validate incoming sessionization request.
    """
    job_id = serializers.UUIDField(required=True)
    timeout_minutes = serializers.FloatField(required=False, default=30)


class SessionizeResponseSerializer(serializers.Serializer):
    """
    Serializer for sessionization summary response.
    """
    job_id = serializers.UUIDField()
    status = serializers.CharField()
    timeout_minutes = serializers.FloatField()
    total_sessions = serializers.IntegerField()
    total_users = serializers.IntegerField()
    sessionized_file_available = serializers.BooleanField()


class AnalyzeRequestSerializer(serializers.Serializer):
    """
    Serializer to validate incoming analytics request.
    """
    job_id = serializers.UUIDField(required=True)


class AnalyzeResponseSerializer(serializers.Serializer):
    """
    Serializer for analytics response.
    """
    job_id = serializers.UUIDField()
    status = serializers.CharField()
    analytics = serializers.JSONField()


class MinePatternsRequestSerializer(serializers.Serializer):
    """
    Serializer to validate incoming sequential pattern mining request.
    """
    job_id = serializers.UUIDField(required=True)
    min_support = serializers.FloatField(required=False, default=0.1)
    max_pattern_length = serializers.IntegerField(required=False, default=3)


class MinePatternsResponseSerializer(serializers.Serializer):
    """
    Serializer for sequential pattern mining response.
    """
    job_id = serializers.UUIDField()
    status = serializers.CharField()
    min_support = serializers.FloatField()
    max_pattern_length = serializers.IntegerField()
    patterns = serializers.JSONField()


class InsightsRequestSerializer(serializers.Serializer):
    """
    Serializer to validate incoming BI insight generation request.
    """
    job_id = serializers.UUIDField(required=True)


class InsightsResponseSerializer(serializers.Serializer):
    """
    Serializer for BI insight generation response.
    """
    job_id = serializers.UUIDField()
    status = serializers.CharField()
    insights = serializers.JSONField()

