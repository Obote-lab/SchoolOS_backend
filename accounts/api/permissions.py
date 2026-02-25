import logging
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions
from accounts.models import PermissionMatrix, UserRole

logger = logging.getLogger(__name__)


class HasPermission(permissions.BasePermission):
    """
    Centralized RBAC permission class — MUST be used on ALL API views.

    Usage in views:
        class SomeViewSet(viewsets.ModelViewSet):
            module = "students"           # required
            required_action = "read"      # required
            required_scope = "school"     # optional, defaults to "school"
            # optional: obj_scope_field = "school"  # for has_object_permission
            # optional: owner_field = "created_by"  # for OWN scope

    Features:
    - Reads PermissionMatrix only
    - Supports scopes: own, department, school, county, national
    - Evaluates conditions (owner, time, etc.)
    - Default deny
    - System root bypass
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # System root / superuser always bypass
        if request.user.is_system_root or request.user.is_superuser:
            return True

        # Get required attributes from view
        module = getattr(view, "module", None)
        action = getattr(view, "required_action", None)
        scope = getattr(view, "required_scope", "school")

        if not module or not action:
            logger.warning(
                f"View {view.__class__.__name__} missing module or required_action → access denied"
            )
            return False

        # Current school context
        school = getattr(request, "school", None)

        # Active, non-expired roles for this user
        roles_qs = UserRole.objects.filter(
            user=request.user,
            is_active=True
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gt=timezone.now())
        )

        # Scope filtering
        if school:
            roles_qs = roles_qs.filter(
                Q(school=school) |
                Q(role__access_level__in=["county", "national"])
            )
        else:
            roles_qs = roles_qs.filter(role__access_level__in=["county", "national"])

        if not roles_qs.exists():
            logger.debug(f"Access denied: {request.user.login_id} - no active roles in context")
            return False

        # Find matching permissions (highest priority first)
        perms_qs = PermissionMatrix.objects.filter(
            role__in=roles_qs.values_list("role_id", flat=True),  # FIXED: use role_id
            module=module,
            action=action,
            is_allowed=True
        ).order_by("-priority")

        for perm in perms_qs:
            if perm.resource_scope != scope:
                continue

            if perm.check_permission(request.user, school=school):
                logger.debug(f"Access granted: {request.user.login_id} via {perm}")
                return True

        logger.debug(
            f"Access denied: {request.user.login_id} - no matching permission for {module}.{action} "
            f"(tried roles: {list(roles_qs.values_list('role__name', flat=True))})"
        )
        return False

    def has_object_permission(self, request, view, obj):
        """
        Object-level check (for retrieve/update/delete/detail actions)
        """
        if not request.user.is_authenticated:
            return False

        # System root bypass
        if request.user.is_system_root or request.user.is_superuser:
            return True

        module = getattr(view, "module", None)
        action = getattr(view, "required_action", None)
        scope_field = getattr(view, "obj_scope_field", "school")
        owner_field = getattr(view, "owner_field", "created_by")

        if not module or not action:
            return False

        school = getattr(request, "school", None)

        # Get object scope (fallback to request.school)
        obj_school = getattr(obj, scope_field, None) if hasattr(obj, scope_field) else None
        effective_school = obj_school or school

        roles_qs = UserRole.objects.filter(
            user=request.user,
            is_active=True
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gt=timezone.now())
        )

        if effective_school:
            roles_qs = roles_qs.filter(
                Q(school=effective_school) |
                Q(role__access_level__in=["county", "national"])
            )
        else:
            roles_qs = roles_qs.filter(role__access_level__in=["county", "national"])

        if not roles_qs.exists():
            return False

        perms_qs = PermissionMatrix.objects.filter(
            role__in=roles_qs.values_list("role_id", flat=True),  # FIXED
            module=module,
            action=action,
            is_allowed=True
        ).order_by("-priority")

        for perm in perms_qs:
            # OWN scope: check ownership
            if perm.resource_scope == "own":
                if hasattr(obj, owner_field) and getattr(obj, owner_field) == request.user:
                    return True
                continue

            # Other scopes: school match + conditions
            if effective_school and perm.check_permission(request.user, obj=obj, school=effective_school):
                return True

        return False


# Optional: Delete this if you don't use it anywhere
# class IsSystemRoot(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return bool(request.user and request.user.is_system_root)