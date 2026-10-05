from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .api.viewsets import (
    BrandingChangeLogViewSet,
    ResolvedBrandingView,
    SchoolBrandingViewSet,
    SystemBrandingViewSet,
    ThemePresetViewSet,
)

router = DefaultRouter()
router.register(r"system", SystemBrandingViewSet, basename="branding-system")
router.register(r"schools", SchoolBrandingViewSet, basename="branding-school")
router.register(r"presets", ThemePresetViewSet, basename="branding-preset")
router.register(r"changes", BrandingChangeLogViewSet, basename="branding-changelog")

urlpatterns = [
    path("resolved/", ResolvedBrandingView.as_view(), name="branding-resolved"),
    path("", include(router.urls)),
]