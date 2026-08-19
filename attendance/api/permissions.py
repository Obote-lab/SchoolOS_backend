"""
Attendance permissions.

ViewSets should still use:
    permission_classes = [IsAuthenticated, HasPermission, ...]
    module = "attendance"
    required_action = "read" | "create" | "update" | "delete"  (via get_permissions)

These classes add school / role / ownership rules on top.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.choices.staff import StaffTypeChoices


# Staff types that can open/close sessions, bulk-mark, see whole-school dashboards
ATTENDANCE_MANAGER_TYPES = {
    StaffTypeChoices.PRINCIPAL,
    StaffTypeChoices.DEPUTY,
    StaffTypeChoices.HOD,
    StaffTypeChoices.ADMIN,
    StaffTypeChoices.TEACHER
}


def _request_school(request):
    return getattr(request, "school", None) or getattr(request.user, "school", None)


def _user_staff(request):
    return getattr(request.user, "staff_profile", None)


class IsSchoolStaff(BasePermission):
    """
    Authenticated user with a staff profile in the current school context.
    Superusers always allowed.
    """

    message = "School staff access required."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        staff = _user_staff(request)
        if not staff or not staff.is_active:
            return False

        school = _request_school(request)
        if school and staff.school_id != school.id:
            return False
        return True


class IsAttendanceManager(BasePermission):
    """
    Principal / Deputy / HOD / Admin (by StaffTypeChoices values).
    Superusers always allowed.
    """

    message = "Attendance manager role required."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        staff = _user_staff(request)
        if not staff or not staff.is_active:
            return False
        if staff.staff_type not in ATTENDANCE_MANAGER_TYPES:
            return False

        school = _request_school(request)
        if school and staff.school_id != school.id:
            return False
        return True


class IsTeacherOrAttendanceManager(BasePermission):
    """
    Any active school staff (teachers included) — for marking class sessions.
    Managers subset is not required.
    """

    message = "Teaching or attendance staff access required."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        staff = _user_staff(request)
        if not staff or not staff.is_active:
            return False

        school = _request_school(request)
        if school and staff.school_id != school.id:
            return False
        return True


class IsStudentSelf(BasePermission):
    """Authenticated user with a student_profile (for check-in / own history)."""

    message = "Student profile required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and hasattr(user, "student_profile")
            and user.student_profile is not None
        )


class IsParentUser(BasePermission):
    """Authenticated parent/guardian."""

    message = "Parent profile required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and hasattr(user, "parent_profile")
            and user.parent_profile is not None
        )


class CanAccessAttendanceSession(BasePermission):
    """
    Object-level: session must belong to request.school (or superuser).
    Staff only for writes; read allowed for staff in school.
    """

    message = "You cannot access this attendance session."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True

        school = _request_school(request)
        if not school or obj.school_id != school.id:
            return False

        # Students/parents do not manage sessions
        if request.method not in SAFE_METHODS:
            return _user_staff(request) is not None

        return _user_staff(request) is not None


class CanAccessAttendanceRecord(BasePermission):
    """
    Object-level for AttendanceRecord:
    - Superuser: all
    - Staff in same school: read/write (further limited by HasPermission)
    - Student: read own only
    - Parent: read linked children only
    """

    message = "You cannot access this attendance record."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True

        school = _request_school(request)
        record_school_id = obj.session.school_id if obj.session_id else None
        if school and record_school_id and record_school_id != school.id:
            return False

        staff = _user_staff(request)
        if staff and staff.is_active:
            if school and staff.school_id != school.id:
                return False
            return True

        # Student: own records, read-only unless you allow self check-in via dedicated action
        student = getattr(user, "student_profile", None)
        if student is not None:
            if obj.student_id != student.pk:
                return False
            if request.method in SAFE_METHODS:
                return True
            # Writes only via check-in/out actions (still object-owned)
            return view.action in {"check_in", "check_out", "create"}

        # Parent: linked children, read-only
        parent = getattr(user, "parent_profile", None)
        if parent is not None:
            if request.method not in SAFE_METHODS:
                return False
            return parent.students.filter(pk=obj.student_id).exists()

        return False


class CanAccessAttendancePattern(BasePermission):
    """
    Patterns: staff (school), student (self), parent (children). Read-heavy.
    """

    message = "You cannot access this attendance pattern."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True

        if request.method not in SAFE_METHODS:
            # Patterns are system-maintained; block direct writes except staff managers
            return IsAttendanceManager().has_permission(request, view)

        staff = _user_staff(request)
        if staff and staff.is_active:
            school = _request_school(request)
            if school and obj.student.school_id != school.id:
                return False
            return True

        student = getattr(user, "student_profile", None)
        if student is not None:
            return obj.student_id == student.pk

        parent = getattr(user, "parent_profile", None)
        if parent is not None:
            return parent.students.filter(pk=obj.student_id).exists()

        return False


class ReadOnly(BasePermission):
    """Force safe methods only (compose with other classes)."""

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS