from django.urls import path
from .views import (
    AnalyzeDatasetView,
    ColumnMappingView,
    DatasetUploadView,
    InsightsView,
    MinePatternsView,
    ProcessDatasetView,
    SessionizeDatasetView,
    ValueMappingView,
)

urlpatterns = [
    path('upload', DatasetUploadView.as_view(), name='dataset-upload'),
    path('upload/', DatasetUploadView.as_view(), name='dataset-upload-slash'),
    path('map-columns', ColumnMappingView.as_view(), name='map-columns'),
    path('map-columns/', ColumnMappingView.as_view(), name='map-columns-slash'),
    path('map-values', ValueMappingView.as_view(), name='map-values'),
    path('map-values/', ValueMappingView.as_view(), name='map-values-slash'),
    path('process', ProcessDatasetView.as_view(), name='process-dataset'),
    path('process/', ProcessDatasetView.as_view(), name='process-dataset-slash'),
    path('sessionize', SessionizeDatasetView.as_view(), name='sessionize-dataset'),
    path('sessionize/', SessionizeDatasetView.as_view(), name='sessionize-dataset-slash'),
    path('analyze', AnalyzeDatasetView.as_view(), name='analyze-dataset'),
    path('analyze/', AnalyzeDatasetView.as_view(), name='analyze-dataset-slash'),
    path('mine-patterns', MinePatternsView.as_view(), name='mine-patterns'),
    path('mine-patterns/', MinePatternsView.as_view(), name='mine-patterns-slash'),
    path('insights', InsightsView.as_view(), name='insights'),
    path('insights/', InsightsView.as_view(), name='insights-slash'),
]
