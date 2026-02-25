from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsSchoolStaff(BasePermission):
    """
    Allows access only to authenticated staff of the same school
    """
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, 'staff_profile')
        )


class IsAttendanceManager(BasePermission):
    """
    HODs, Deputies, Principals
    """
    ALLOWED_TYPES = ['principal', 'deputy', 'hod']

    def has_permission(self, request, view):
        staff = getattr(request.user, 'staff_profile', None)
        if not staff:
            return False
        return staff.staff_type in self.ALLOWED_TYPES


class IsOwnerOrReadOnly(BasePermission):
    """
    Students can read their own attendance
    """
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return hasattr(request.user, 'staff_profile')
