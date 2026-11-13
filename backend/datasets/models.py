import uuid
from django.db import models


class Dataset(models.Model):
    STATUS_UPLOADED = 'uploaded'
    STATUS_MAPPING = 'mapping'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_UPLOADED, 'Uploaded'),
        (STATUS_MAPPING, 'Mapping'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    job_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500, blank=True, default='')
    cleaned_file_path = models.CharField(max_length=500, blank=True, default='')
    sessionized_file_path = models.CharField(max_length=500, blank=True, default='')
    upload_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_UPLOADED,
    )
    headers = models.JSONField(default=list, blank=True)
    column_mapping = models.JSONField(default=dict, blank=True)
    value_mapping = models.JSONField(default=dict, blank=True)
    quality_report = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.filename} ({self.status})"


class Session(models.Model):
    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        related_name='sessions',
    )
    session_id = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration = models.DurationField()
    event_count = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['dataset', 'session_id'],
                name='unique_dataset_session',
            )
        ]
        indexes = [
            models.Index(fields=['dataset', 'user_id']),
        ]

    def __str__(self):
        return f"{self.session_id} ({self.user_id})"


class AnalysisResult(models.Model):
    dataset = models.OneToOneField(
        Dataset,
        on_delete=models.CASCADE,
        related_name='analysis_result',
    )
    results = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AnalysisResult ({self.dataset.job_id})"


class PatternMiningResult(models.Model):
    dataset = models.OneToOneField(
        Dataset,
        on_delete=models.CASCADE,
        related_name='pattern_mining_result',
    )
    results = models.JSONField(default=dict)
    min_support = models.FloatField(default=0.1)
    max_pattern_length = models.PositiveIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PatternMiningResult ({self.dataset.job_id})"


class InsightResult(models.Model):
    dataset = models.OneToOneField(
        Dataset,
        on_delete=models.CASCADE,
        related_name='insight_result',
    )
    insights = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"InsightResult ({self.dataset.job_id})"

