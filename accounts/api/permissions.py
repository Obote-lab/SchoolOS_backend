import logging
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions
from core.choices import AccessLevelChoices
from ..models import CustomUser, PermissionMatrix, UserRole

logger = logging.getLogger(__name__)


class HasPermission(permissions.BasePermission):
    """
    Centralized RBAC permission class.

    Usage example:

        class StudentViewSet(ModelViewSet):
            permission_classes = [HasPermission]
            module = "students"
            required_action = "read"
            required_scope = "school"
    """

    message = "You do not have permission to perform this action."

    # Helpers
    @staticmethod
    def _is_system_user(user: CustomUser) -> bool:
        """Superusers always bypass permission checks."""
        return user.is_superuser

    @staticmethod
    def _get_view_requirements(view):
        return (
            getattr(view, "module", None),
            getattr(view, "required_action", None),
            getattr(view, "required_scope", "school"),
        )

    @staticmethod
    def _get_active_roles(user: CustomUser, school=None):
        """Return active, non-expired roles for the user."""
        roles = (
            UserRole.objects.filter(user=user, is_active=True)
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=timezone.now()))
            .select_related("role")
        )

        if school:
            roles = roles.filter(
                Q(school=school)
                | Q(role__access_level__in=[AccessLevelChoices.COUNTY, AccessLevelChoices.NATIONAL])
            )
        else:
            roles = roles.filter(
                role__access_level__in=[AccessLevelChoices.COUNTY, AccessLevelChoices.NATIONAL]
            )

        return roles

    @staticmethod
    def _get_permissions(role_ids, module: str, action: str):
        return (
            PermissionMatrix.objects.filter(
                role_id__in=role_ids,
                module=module,
                action=action,
                is_allowed=True,
            )
            .select_related("role")
            .order_by("-priority")
        )

    # Global Permission

    def has_permission(self, request, view) -> bool:
        user = request.user

        if not user.is_authenticated or not user.is_active:
            return False

        if user.locked_until and user.locked_until > timezone.now():
            return False

        if self._is_system_user(user):
            return True

        module, action, scope = self._get_view_requirements(view)
        if not module or not action:
            logger.warning("%s is missing module or required_action", view.__class__.__name__)
            return False

        school = getattr(request, "school", None)
        roles = self._get_active_roles(user, school)

        if not roles.exists():
            return False

        role_ids = list(roles.values_list("role_id", flat=True))
        permissions_qs = self._get_permissions(role_ids, module, action)

        for permission in permissions_qs:
            if permission.resource_scope != scope:
                continue
            if permission.check_permission(user, school=school):
                return True

        return False

    # Object-level Permission
    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user

        if not user.is_authenticated:
            return False

        if self._is_system_user(user):
            return True

        module, action, _ = self._get_view_requirements(view)
        if not module or not action:
            return False

        scope_field = getattr(view, "obj_scope_field", "school")
        owner_field = getattr(view, "owner_field", "created_by")

        object_school = getattr(obj, scope_field, None)
        school = object_school or getattr(request, "school", None)

        roles = self._get_active_roles(user, school)
        if not roles.exists():
            return False

        role_ids = list(roles.values_list("role_id", flat=True))
        permissions_qs = self._get_permissions(role_ids, module, action)
        owner = getattr(obj, owner_field, None)

        for permission in permissions_qs:
            if permission.resource_scope == "own":
                if owner == user:
                    return True
                continue

            if permission.check_permission(user, obj=obj, school=school):
                return True

        return False


class IsSystemUser(permissions.BasePermission):
    """
    Allows access only to superusers / system-level accounts.
    """

    message = "Only system users can perform this action."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_superuser


class HasAnyRole(permissions.BasePermission):
    """
    Allows access if the user has at least one of the required role names.
    Usage:
        class SomeViewSet(...):
            permission_classes = [IsAuthenticated, HasAnyRole]
            required_roles = ["Principal", "Deputy Principal", "Registrar"]
    """

    message = "You do not have the required role."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        required_roles = getattr(view, "required_roles", [])
        if not required_roles:
            return False

        return UserRole.objects.filter(
            user=request.user,
            is_active=True,
            role__name__in=required_roles,
        ).exists()


class HasRole(permissions.BasePermission):
    """
    Restricts access to users who currently hold a specific role name.
    Usage:
        class ComplianceViewSet(...):
            permission_classes = [IsAuthenticated, HasRole]
            required_role = "Compliance Officer"
    """

    message = "You do not have the required role."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        required_role = getattr(view, "required_role", None)
        if not required_role:
            return False

        return request.user.user_roles.filter(
            is_active=True,
            role__name=required_role,
        ).exists()