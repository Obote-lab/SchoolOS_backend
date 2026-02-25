from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin


class SchoolContextMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Skip static, admin, and public auth routes
        if any(request.path.startswith(p) for p in ["/static/", "/admin/", "/api/accounts/auth/"]):
            request.school = None
            return None

        # Try URL param first (e.g. /schools/<uuid>/...)
        if request.resolver_match:
            school_id = request.resolver_match.kwargs.get("school_id")
            if school_id:
                from schools.models import School
                try:
                    request.school = School.objects.get(id=school_id)
                    return None
                except School.DoesNotExist:
                    request.school = None
                    return None

        # Authenticated user → attach their school (if any)
        if request.user.is_authenticated and not request.user.is_superuser:
            if hasattr(request.user, "school") and request.user.school:
                request.school = request.user.school
                return None

        # Regional admins → no single school, but can have county context later
        request.school = None