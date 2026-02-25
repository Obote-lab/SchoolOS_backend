from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.viewsets import (
    AuditLogViewSet,
    DataExportLogViewSet,
    SystemHealthViewSet,
    ComplianceCheckViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'audit-logs', AuditLogViewSet, basename='auditlog')
router.register(r'data-exports', DataExportLogViewSet, basename='dataexport')
router.register(r'system-health', SystemHealthViewSet, basename='systemhealth')
router.register(r'compliance-checks', ComplianceCheckViewSet, basename='compliancecheck')

urlpatterns = [
    path('', include(router.urls)),
]

app_name = 'compliance'