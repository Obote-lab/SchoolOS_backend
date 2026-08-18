from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import (
    AtRiskStudentsView,
    AttendanceExportView,
    AttendancePatternViewSet,
    AttendanceRecordViewSet,
    AttendanceReportView,
    AttendanceSessionViewSet,
    ClassDailySummaryView,
    TodayAttendanceView,
    WeeklyTrendView,
)

router = DefaultRouter()
router.register(r"sessions", AttendanceSessionViewSet, basename="attendance-session")
router.register(r"records", AttendanceRecordViewSet, basename="attendance-record")
router.register(r"patterns", AttendancePatternViewSet, basename="attendance-pattern")

urlpatterns = [
    path("", include(router.urls)),
    # Dashboard & reports
    path("today/", TodayAttendanceView.as_view(), name="today-attendance"),
    path("weekly-trend/", WeeklyTrendView.as_view(), name="weekly-trend"),
    path("at-risk/", AtRiskStudentsView.as_view(), name="at-risk-students"),
    path("class-daily/", ClassDailySummaryView.as_view(), name="class-daily-summary"),
    path("export/", AttendanceExportView.as_view(), name="attendance-export"),
    path("reports/", AttendanceReportView.as_view(), name="attendance-reports"),
]