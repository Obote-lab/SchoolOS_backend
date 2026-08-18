import logging
from django.http import Http404
from django.utils.deprecation import MiddlewareMixin
from core.choices import AccessLevelChoices
logger = logging.getLogger(__name__)


class SchoolContextMiddleware(MiddlewareMixin):
    """
    Attaches the most appropriate school context to the request.

    Priority order:
    1. Explicit URL parameter (school_id, school_pk, school, etc.)
    2. Primary school-level role (is_primary_role=True)
    3. Most recently assigned active school-level role
    4. None (for regional / national / system users or public views)
    """

    SKIP_PATH_PREFIXES = [
        "/static/",
        "/media/",
        "/admin/",
        "/api/v1/accounts/auth/",
        "/api/schema/",
        "/api/docs/",
        "/api/redoc/",
        "/health/",
    ]

    SCHOOL_ID_KWARG_NAMES = {"school_id", "school_pk", "school"}

    def process_request(self, request):
        # Skip static / public routes
        if any(request.path.startswith(prefix) for prefix in self.SKIP_PATH_PREFIXES):
            request.school = None
            request.county_context = None
            return None

        # Anonymous users have no school context
        if not request.user.is_authenticated:
            request.school = None
            request.county_context = None
            return None

        # Superusers see everything – no forced school context
        if request.user.is_superuser:
            request.school = None
            request.county_context = None
            return None

        # 1. Highest priority – school from URL
        school = self._get_school_from_url(request)
        if school:
            request.school = school
            request.county_context = None
            return None

        # 2. Active roles
        active_roles = (
            request.user.user_roles.filter(is_active=True)
            .select_related("school", "role")
            .order_by("-is_primary_role", "-assigned_date")
        )

        school_level_roles = [
            ur for ur in active_roles
            if ur.school_id and ur.role.access_level == AccessLevelChoices.SCHOOL
        ]

        if not school_level_roles:
            # No school-level role → regional / national user
            request.school = None

            # Placeholder for future county context
            # (will be improved once RegionalAdminProfile exists)
            has_county_role = any(
                ur.role.access_level == AccessLevelChoices.COUNTY
                for ur in active_roles
            )
            request.county_context = {"has_county_access": has_county_role} if has_county_role else None
            return None

        # 3. Prefer primary role
        primary = next((r for r in school_level_roles if r.is_primary_role), None)
        if primary:
            request.school = primary.school
            request.county_context = None
            logger.debug(
                "Attached primary school context: %s for %s",
                request.school,
                request.user.login_id,
            )
            return None

        # 4. Fallback – most recent school role
        most_recent = school_level_roles[0]
        request.school = most_recent.school
        request.county_context = None
        logger.debug(
            "Attached fallback school context: %s for %s",
            request.school,
            request.user.login_id,
        )
        return None

    def _get_school_from_url(self, request):
        """Try to extract school from URL kwargs."""
        if not getattr(request, "resolver_match", None):
            return None

        kwargs = request.resolver_match.kwargs or {}

        for key in self.SCHOOL_ID_KWARG_NAMES:
            school_id = kwargs.get(key)
            if not school_id:
                continue

            from schools.models import School

            try:
                school = School.objects.get(id=school_id)
                logger.debug("School context taken from URL param '%s': %s", key, school)
                return school
            except School.DoesNotExist:
                logger.warning("Invalid school_id in URL: %s", school_id)
                raise Http404(f"School with ID {school_id} not found")
            except Exception as e:
                logger.error("Error resolving school from URL: %s", e)
                return None

        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Ensure request.school always exists."""
        if not hasattr(request, "school"):
            request.school = None
        if not hasattr(request, "county_context"):
            request.county_context = None
        return None