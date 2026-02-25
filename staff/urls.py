from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import (
    StaffProfileViewSet,
    StaffAttendanceViewSet,
)

router = DefaultRouter()
router.register(r"staff", StaffProfileViewSet, basename="staff")
router.register(r"attendance", StaffAttendanceViewSet, basename="attendance")

urlpatterns = [
    path("", include(router.urls)),
]