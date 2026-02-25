from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.viewsets import (
    DisciplineIncidentViewSet,
    SickBayRecordViewSet,
    CounselingSessionViewSet,
    WellnessCheckViewSet,
    WelfareDashboardView,
    WelfareStatisticsView,
    StudentWelfareView,
    WelfareReportView,
    WelfareAlertsView
)

router = DefaultRouter()
router.register(r'incidents', DisciplineIncidentViewSet, basename='incident')
router.register(r'sickbay', SickBayRecordViewSet, basename='sickbay')
router.register(r'counseling', CounselingSessionViewSet, basename='counseling')
router.register(r'wellness', WellnessCheckViewSet, basename='wellness')

urlpatterns = [
    path('', include(router.urls)),
    
    # Dashboard & Statistics
    path('dashboard/', WelfareDashboardView.as_view(), name='welfare_dashboard'),
    path('statistics/', WelfareStatisticsView.as_view(), name='welfare_statistics'),
    path('student-welfare/', StudentWelfareView.as_view(), name='student_welfare'),

    path('reports/', WelfareReportView.as_view(), name='welfare_reports'),
    path('alerts/', WelfareAlertsView.as_view(), name='welfare_alerts'),
    path('incidents/recent/', DisciplineIncidentViewSet.as_view({'get': 'recent'}), name='recent_incidents'),
    path('incidents/pending/', DisciplineIncidentViewSet.as_view({'get': 'pending'}), name='pending_incidents'),

    path('sickbay/today/', SickBayRecordViewSet.as_view({'get': 'today'}), name='today_sickbay'),
    path('sickbay/contagious/', SickBayRecordViewSet.as_view({'get': 'contagious'}), name='contagious_cases'),
    
    path('counseling/upcoming/', CounselingSessionViewSet.as_view({'get': 'upcoming'}), name='upcoming_sessions'),
    path('counseling/my_sessions/', CounselingSessionViewSet.as_view({'get': 'my_sessions'}), name='my_sessions'),
    
    path('wellness/recent/', WellnessCheckViewSet.as_view({'get': 'recent'}), name='recent_wellness'),
    path('wellness/critical/', WellnessCheckViewSet.as_view({'get': 'critical'}), name='critical_wellness'),
]