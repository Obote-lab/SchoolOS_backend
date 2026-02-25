from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import (
    ParentGuardianViewSet,
    StudentMedicalHistoryViewSet,
    StudentViewSet,
)

router = DefaultRouter()
router.register(r"students", StudentViewSet, basename="student")
router.register(r"parents", ParentGuardianViewSet, basename="parent-guardian")
router.register(r"medical-history", StudentMedicalHistoryViewSet, basename="medical-history")

urlpatterns = [
    path("", include(router.urls)),
]