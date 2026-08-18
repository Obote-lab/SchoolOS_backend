from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import (
    AcademicYearViewSet,
    ClassRoomViewSet,
    DepartmentViewSet,
    RegionalAdminCreateSchoolView,
    SchoolOnboardingProgressView,
    SchoolSearchView,
    SchoolViewSet,
    SystemBulkOnboardingView,
    SystemOnboardingDashboardView,
    SystemSchoolOnboardingView,
    TermViewSet,
)

router = DefaultRouter()
router.register(r"schools", SchoolViewSet, basename="school")
router.register(r"academic-years", AcademicYearViewSet, basename="academic-year")
router.register(r"terms", TermViewSet, basename="term")
router.register(r"classrooms", ClassRoomViewSet, basename="classroom")
router.register(r"departments", DepartmentViewSet, basename="department")

urlpatterns = [
    # Specific paths FIRST
    path(
        "schools/search/advanced/",
        SchoolSearchView.as_view(),
        name="school-search-advanced",
    ),
    path(
        "schools/<uuid:school_id>/onboarding/",
        SchoolOnboardingProgressView.as_view(),
        name="school-onboarding-progress",
    ),

    # System / regional
    path("system/onboard/single/", SystemSchoolOnboardingView.as_view(), name="system-onboard-single"),
    path("system/onboard/bulk/", SystemBulkOnboardingView.as_view(), name="system-onboard-bulk"),
    path("system/onboard/dashboard/", SystemOnboardingDashboardView.as_view(), name="system-onboarding-dashboard"),
    path("regional/schools/", RegionalAdminCreateSchoolView.as_view(), name="regional-create-school"),

    # Router last
    path("", include(router.urls)),
]