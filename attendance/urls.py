from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.viewsets import (
    AttendanceSessionViewSet,
    AttendanceRecordViewSet,
    AttendancePatternViewSet,
    TodayStatsView,
    WeeklyTrendView,
    AtRiskStudentsView,
    ClassDailySummaryView,
    AttendanceExportView,
    AttendanceReportView,
)

router = DefaultRouter()
router.register(r'sessions', AttendanceSessionViewSet, basename='session')
router.register(r'records', AttendanceRecordViewSet, basename='record')
router.register(r'patterns', AttendancePatternViewSet, basename='pattern')

urlpatterns = [
    path('', include(router.urls)),

    # Dashboard & quick stats
    path('today-stats/', TodayStatsView.as_view(), name='today_attendance_stats'),
    path('weekly-trend/', WeeklyTrendView.as_view(), name='weekly_attendance_trend'),
    path('at-risk-students/', AtRiskStudentsView.as_view(), name='at_risk_students'),

    # Class & reports
    path('class-daily/', ClassDailySummaryView.as_view(), name='class_daily_summary'),
    path('export/', AttendanceExportView.as_view(), name='attendance_export'),
    path('reports/', AttendanceReportView.as_view(), name='attendance_reports'),

    # Custom actions
    # path('sessions/today/', AttendanceSessionViewSet.as_view({'get': 'today'}), name='sessions_today'),
    # path('sessions/upcoming/', AttendanceSessionViewSet.as_view({'get': 'upcoming'}), name='sessions_upcoming'),
    path('records/bulk/', AttendanceRecordViewSet.as_view({'post': 'bulk_mark'}), name='bulk_mark_records'),
    path('records/check-in/', AttendanceRecordViewSet.as_view({'post': 'check_in'}), name='check_in'),
    path('records/check-out/', AttendanceRecordViewSet.as_view({'post': 'check_out'}), name='check_out'),

    # Student-facing
    path('patterns/student-summary/', AttendancePatternViewSet.as_view({'get': 'student_summary'}), name='student_summary_patterns'),
]