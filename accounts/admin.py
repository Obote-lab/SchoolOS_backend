from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, PermissionMatrix, Role, UserRole


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """Admin interface for the CustomUser model."""

    model = CustomUser
    list_display = (
        "login_id",
        "email",
        "first_name",
        "last_name",
        "school",
        "is_active",
        "is_verified",
        "can_login",
    )
    list_filter = (
        "is_active",
        "is_verified",
        "can_login",
        "school",
        "user_gender",
        "preferred_language",
    )
    search_fields = (
        "login_id",
        "email",
        "first_name",
        "last_name",
        "phone",
        "permanent_id",
    )
    ordering = ("-date_joined",)
    readonly_fields = (
        "id",
        "permanent_id",
        "date_joined",
        "last_login",
        "created_at",
        "updated_at",
        "last_password_change",
        "failed_login_attempts",
        "locked_until",
        "last_locked_at",
    )

    fieldsets = (
        (None, {
            "fields": ("login_id", "password", "permanent_id")
        }),
        (_("Personal Info"), {
            "fields": (
                "first_name",
                "middle_name",
                "last_name",
                "email",
                "phone",
                "date_of_birth",
                "user_gender",
                "profile_picture",
            )
        }),
        (_("School & Location"), {
            "fields": (
                "school",
                "county",
                "sub_county",
                "ward",
                "address",
            )
        }),
        (_("Preferences"), {
            "fields": (
                "preferred_language",
                "notification_prefs",
                "recovery_email",
            )
        }),
        (_("Security"), {
            "fields": (
                "is_active",
                "is_verified",
                "can_login",
                "failed_login_attempts",
                "locked_until",
                "last_locked_at",
                "last_password_change",
            )
        }),
        (_("Permissions"), {
            "fields": (
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        (_("Important dates"), {
            "fields": ("date_joined", "last_login", "created_at", "updated_at")
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "login_id",
                "password1",
                "password2",
                "first_name",
                "last_name",
                "email",
                "phone",
                "school",
            ),
        }),
    )

    filter_horizontal = ("groups", "user_permissions")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        # Non-superusers only see users from their own school
        if getattr(request.user, "school", None):
            return qs.filter(school=request.user.school)

        return qs.none()


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "role_category", "permissions_tier", "access_level", "created_at")
    list_filter = ("role_category", "access_level", "permissions_tier")
    search_fields = ("name", "description")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("permissions_tier", "name")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "school",
        "is_primary_role",
        "is_active",
        "assigned_date",
    )
    list_filter = ("is_active", "is_primary_role", "role", "school")
    search_fields = (
        "user__login_id",
        "user__first_name",
        "user__last_name",
        "role__name",
    )
    readonly_fields = ("id", "assigned_date", "created_at", "updated_at")
    raw_id_fields = ("user", "role", "school", "assigned_by")
    ordering = ("-assigned_date",)


@admin.register(PermissionMatrix)
class PermissionMatrixAdmin(admin.ModelAdmin):
    list_display = (
        "role",
        "module",
        "action",
        "resource_scope",
        "is_allowed",
        "priority",
    )
    list_filter = ("module", "action", "is_allowed", "resource_scope")
    search_fields = ("role__name", "module")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("role", "created_by")
    ordering = ("role", "module", "action")