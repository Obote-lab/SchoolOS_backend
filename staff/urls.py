from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .api.viewsets import StaffAttendanceViewSet, StaffProfileViewSet

router = DefaultRouter()
router.register(r"profiles", StaffProfileViewSet, basename="staff-profile")
router.register(r"attendance", StaffAttendanceViewSet, basename="staff-attendance")

urlpatterns = [
    path("", include(router.urls)),
]