from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .api.viewsets import (
    AccountActivationView,
    CreateTeacherView,
    CustomUserViewSet,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PermissionMatrixViewSet,
    RegionalAdminDashboardView,
    ResendActivationEmailView,
    RoleViewSet,
    SystemCreatePrincipalForSchoolView,
    SystemRootCreateRegionalAdminView,
    SystemRootDashboardView,
    UserRoleViewSet,
)

router = DefaultRouter()
router.register(r"users", CustomUserViewSet, basename="user")
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"user-roles", UserRoleViewSet, basename="user-role")
router.register(r"permissions", PermissionMatrixViewSet, basename="permission")

urlpatterns = [
    # Authentication
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("auth/activate/", AccountActivationView.as_view(), name="account-activate"),
    path("auth/resend-activation/", ResendActivationEmailView.as_view(), name="resend-activation"),

    # School-level creation
    path(
        "schools/<uuid:school_id>/teachers/",
        CreateTeacherView.as_view(),
        name="create-teacher",
    ),

    # System Root (Global Admin)
    path(
        "system/regional-admins/",
        SystemRootCreateRegionalAdminView.as_view(),
        name="create-regional-admin",
    ),
    path(
        "system/dashboard/",
        SystemRootDashboardView.as_view(),
        name="system-dashboard",
    ),
    path(
        "system/schools/<uuid:school_id>/principals/",
        SystemCreatePrincipalForSchoolView.as_view(),
        name="create-principal",
    ),

    # Regional Admin
    path(
        "regional/dashboard/",
        RegionalAdminDashboardView.as_view(),
        name="regional-dashboard",
    ),

    # Main API (ViewSets)
    path("", include(router.urls)),

    # Health check
    path(
        "health/",
        lambda request: JsonResponse({"status": "ok", "service": "accounts"}),
        name="health-check",
    ),
]