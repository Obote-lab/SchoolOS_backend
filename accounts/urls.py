from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .api.viewsets import (
    CustomUserViewSet,
    RoleViewSet,
    UserRoleViewSet,
    PermissionMatrixViewSet,
    LoginView,
    LogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    CreateTeacherView,
    SystemRootCreateRegionalAdminView,
    SystemRootDashboardView,
    SystemCreatePrincipalForSchoolView,
    RegionalAdminDashboardView,
)

# Create router for standard ViewSet CRUD
router = DefaultRouter()
router.register(r"users", CustomUserViewSet, basename="user")
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"user-roles", UserRoleViewSet, basename="user-role")
router.register(r"permissions", PermissionMatrixViewSet, basename="permission")

urlpatterns = [
    #  Authentication Endpoints 
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),

    #  School-level Operations 
    # Create teacher in a specific school (principal/deputy scoped)
    path("schools/<uuid:school_id>/teachers/", CreateTeacherView.as_view(), name="create_teacher"),

    #  System Root (Global Admin) Endpoints 
    path("system/regional-admins/", SystemRootCreateRegionalAdminView.as_view(), name="create_regional_admin"),
    path("system/dashboard/", SystemRootDashboardView.as_view(), name="system_dashboard"),
    path("system/schools/<uuid:school_id>/principals/", SystemCreatePrincipalForSchoolView.as_view(), name="create_principal"),

    #  Regional Admin Endpoints 
    path("regional/dashboard/", RegionalAdminDashboardView.as_view(), name="regional_dashboard"),

    #  Standard API CRUD Endpoints (v1 prefix) 
    path("v1/", include(router.urls)),

    #  Health Check (always useful) 
    path("health/", lambda request: JsonResponse({"status": "ok"}), name="health_check"),
]