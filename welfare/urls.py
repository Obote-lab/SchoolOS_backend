from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import (
    CounselingSessionViewSet,
    DisciplineIncidentViewSet,
    SickBayRecordViewSet,
    StudentWelfareView,
    WelfareAlertsView,
    WelfareDashboardView,
    WelfareReportView,
    WelfareStatisticsView,
    WellnessCheckViewSet,
)

router = DefaultRouter()
router.register(r"incidents", DisciplineIncidentViewSet, basename="incident")
router.register(r"sickbay", SickBayRecordViewSet, basename="sickbay")
router.register(r"counseling", CounselingSessionViewSet, basename="counseling")
router.register(r"wellness", WellnessCheckViewSet, basename="wellness")

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/", WelfareDashboardView.as_view(), name="welfare-dashboard"),
    path("statistics/", WelfareStatisticsView.as_view(), name="welfare-statistics"),
    path("student-welfare/", StudentWelfareView.as_view(), name="student-welfare"),
    path("reports/", WelfareReportView.as_view(), name="welfare-reports"),
    path("alerts/", WelfareAlertsView.as_view(), name="welfare-alerts"),
]