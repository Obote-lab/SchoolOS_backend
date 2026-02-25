from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import (
    AcademicYearViewSet,
    ClassRoomViewSet,
    DepartmentViewSet,
    SchoolViewSet,
    TermViewSet,
    # ── Onboarding / system endpoints ──
    SystemSchoolOnboardingView,
    SystemBulkOnboardingView,
    SchoolOnboardingProgressView,
    SystemOnboardingDashboardView,

    SchoolSearchView,
    RegionalAdminCreateSchoolView,

)

# ── Main API router for standard CRUD 
router = DefaultRouter()
router.register(r"schools", SchoolViewSet, basename="school")
router.register(r"academic-years", AcademicYearViewSet, basename="academic-year")
router.register(r"terms", TermViewSet, basename="term")
router.register(r"classrooms", ClassRoomViewSet, basename="classroom")
router.register(r"departments", DepartmentViewSet, basename="department")

# ── URL patterns 
urlpatterns = [
    path("v1/", include(router.urls)),
    path("v1/system/onboard/single/",SystemSchoolOnboardingView.as_view(),name="system-onboard-single-school",),
    path("v1/system/onboard/bulk/",SystemBulkOnboardingView.as_view(),name="system-onboard-bulk-schools",),
    path("v1/system/onboard/dashboard/",SystemOnboardingDashboardView.as_view(),name="system-onboarding-dashboard",),
    path("v1/schools/<uuid:school_id>/onboarding/",SchoolOnboardingProgressView.as_view(),name="school-onboarding-progress",),

    path("v1/schools/search/advanced/",SchoolSearchView.as_view(), name="school-search-advanced",),
    path("v1/regional/schools/", RegionalAdminCreateSchoolView.as_view(), name="regional-create-school",),
]