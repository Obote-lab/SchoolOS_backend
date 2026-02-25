from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.viewsets import ActivityViewSet, StudentActivityViewSet, CompetitionViewSet

router = DefaultRouter()
router.register(r'activities', ActivityViewSet, basename='activity')
router.register(r'student_activities', StudentActivityViewSet, basename='student_activity')
router.register(r'competitions', CompetitionViewSet, basename='competition')

urlpatterns = [
    path('', include(router.urls)),
    
    path('student_activities/<uuid:id>/update_attendance/', StudentActivityViewSet.as_view({'patch': 'update_attendance'}),name='student_activity_update_attendance'),
    path('competitions/<uuid:competition_id>/add_participant/', CompetitionViewSet.as_view({'post': 'add_participant'}),  name='competition_add_participant'),
    path('reports/talent/', StudentActivityViewSet.as_view({'get': 'talent_report'}),   name='talent_report'),
    path('competitions/upcoming/', CompetitionViewSet.as_view({'get': 'upcoming'}), name='upcoming_competitions'),
]

app_name = 'activities'