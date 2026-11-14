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

    Scope hierarchy (higher scope can satisfy lower scope requests):
        national > county > school > own
    """

    message = "You do not have permission to perform this action."

    # Higher number = broader scope
    SCOPE_RANK = {
        "own": 1,
        "school": 2,
        "county": 3,
        "national": 4,
    }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_system_user(user: CustomUser) -> bool:
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
            # School-level request → allow school-specific roles + county/national
            roles = roles.filter(
                Q(school=school)
                | Q(role__access_level__in=[
                    AccessLevelChoices.COUNTY,
                    AccessLevelChoices.NATIONAL,
                ])
            )
        else:
            # No school context → only county / national roles
            roles = roles.filter(
                role__access_level__in=[
                    AccessLevelChoices.COUNTY,
                    AccessLevelChoices.NATIONAL,
                ]
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

    def _scope_is_sufficient(self, permission_scope: str, required_scope: str) -> bool:
        """
        Return True if the permission's scope is equal to or broader
        than what the view requires.
        """
        perm_rank = self.SCOPE_RANK.get(permission_scope, 0)
        required_rank = self.SCOPE_RANK.get(required_scope, 2)  # default school
        return perm_rank >= required_rank

    # ------------------------------------------------------------------
    # Global Permission
    # ------------------------------------------------------------------

    def has_permission(self, request, view) -> bool:
        user = request.user

        if not user.is_authenticated or not user.is_active:
            return False

        if user.locked_until and user.locked_until > timezone.now():
            return False

        if self._is_system_user(user):
            return True

        module, action, required_scope = self._get_view_requirements(view)
        if not module or not action:
            logger.warning(
                "%s is missing module or required_action", view.__class__.__name__
            )
            return False

        school = getattr(request, "school", None)
        roles = self._get_active_roles(user, school)

        if not roles.exists():
            return False

        role_ids = list(roles.values_list("role_id", flat=True))
        permissions_qs = self._get_permissions(role_ids, module, action)

        for permission in permissions_qs:
            # KEY CHANGE: higher scope can satisfy lower scope
            if not self._scope_is_sufficient(permission.resource_scope, required_scope):
                continue

            if permission.check_permission(user, school=school):
                return True

        return False

    # ------------------------------------------------------------------
    # Object-level Permission
    # ------------------------------------------------------------------

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user

        if not user.is_authenticated:
            return False

        if self._is_system_user(user):
            return True

        module, action, required_scope = self._get_view_requirements(view)
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
            # Special case for "own"
            if permission.resource_scope == "own":
                if owner == user:
                    return True
                continue

            if not self._scope_is_sufficient(permission.resource_scope, required_scope):
                continue

            if permission.check_permission(user, obj=obj, school=school):
                return True

        return False