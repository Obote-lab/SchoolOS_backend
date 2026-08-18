from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import (
    SystemAuditEventViewSet,
    ComplianceCheckViewSet,
    DataExportLogViewSet,
    SystemHealthViewSet,
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r"audit_logs", SystemAuditEventViewSet, basename="auditlog")
router.register(r"data_exports", DataExportLogViewSet, basename="dataexport")
router.register(r"system_health", SystemHealthViewSet, basename="systemhealth")
router.register(
    r"compliance_checks", ComplianceCheckViewSet, basename="compliancecheck"
)

urlpatterns = [
    path("", include(router.urls)),
]

app_name = "compliance"
