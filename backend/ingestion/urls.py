from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ingestion.views import (
    OrganizationViewSet, FacilityViewSet, IngestionJobViewSet, 
    NormalizedRecordViewSet, AuditLogViewSet, AnalyticsView
)

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'facilities', FacilityViewSet, basename='facility')
router.register(r'jobs', IngestionJobViewSet, basename='job')
router.register(r'records', NormalizedRecordViewSet, basename='record')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('', include(router.urls)),
    path('analytics/', AnalyticsView.as_view(), name='analytics'),
]
