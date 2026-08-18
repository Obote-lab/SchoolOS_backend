from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import ActivityViewSet, CompetitionViewSet, StudentActivityViewSet

router = DefaultRouter()
router.register(r"activities", ActivityViewSet, basename="activity")
router.register(r"student-activities", StudentActivityViewSet, basename="student-activity")
router.register(r"competitions", CompetitionViewSet, basename="competition")

urlpatterns = [
    path("", include(router.urls)),
]

app_name = "activities"