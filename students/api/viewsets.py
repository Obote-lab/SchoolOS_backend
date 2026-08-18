import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.permissions import HasPermission

from ..models import ParentGuardian, StudentMedicalHistory, StudentProfile
from .serializers import (
    MedicalHistoryCreateSerializer,
    ParentGuardianCreateSerializer,
    ParentGuardianSerializer,
    ParentGuardianSimpleSerializer,
    StudentCreateSerializer,
    StudentMedicalHistorySerializer,
    StudentSearchSerializer,
    StudentSerializer,
    StudentSimpleSerializer,
    StudentStatusUpdateSerializer,
    StudentUpdateSerializer,
)

logger = logging.getLogger(__name__)


#  PERMISSIONS
class IsSchoolStaffOrPrincipal(IsAuthenticated):
    """
    Allows school staff (teachers, HODs, deputies, principal)
    or superusers to manage students.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        # Check if user has any active school-level role
        return request.user.user_roles.filter(
            is_active=True,
            role__access_level="school",
        ).exists()


class IsParentOfStudent(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        user = request.user
        if isinstance(obj, StudentProfile):
            return ParentGuardian.objects.filter(user=user, students=obj).exists()
        if hasattr(obj, "student"):
            return ParentGuardian.objects.filter(user=user, students=obj.student).exists()
        return False


class IsStudentOwner(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        return getattr(obj, "user", None) == request.user


# STUDENT VIEWSET
@extend_schema_view(
    list=extend_schema(
        summary="List students",
        parameters=[
            OpenApiParameter(name="school", type=OpenApiTypes.UUID),
            OpenApiParameter(name="current_class", type=OpenApiTypes.UUID),
            OpenApiParameter(name="student_status", type=OpenApiTypes.STR),
            OpenApiParameter(name="student_category", type=OpenApiTypes.STR),
        ],
    ),
    retrieve=extend_schema(summary="Get full student profile"),
    create=extend_schema(summary="Create new student + user account"),
)
class StudentViewSet(viewsets.ModelViewSet):
    queryset = StudentProfile.objects.select_related("user", "school", "current_class", "boarding_house").prefetch_related("parents__user")
    module = "students"
    permission_classes = [IsAuthenticated, HasPermission]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["school", "current_class", "student_status", "student_category", "gender"]
    search_fields = ["admission_number", "user__first_name", "user__last_name", "user__phone"]
    ordering_fields = ["admission_number", "admission_date", "date_of_birth"]
    ordering = ["admission_number"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            self.required_action = "read"
        elif self.action == "create":
            self.required_action = "create"
        elif self.action in ["update", "partial_update", "update_status"]:
            self.required_action = "update"
        elif self.action == "destroy":
            self.required_action = "delete"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Student sees only themselves
        if hasattr(user, "student_profile"):
            return qs.filter(user=user)

        # Parent sees only their children
        if ParentGuardian.objects.filter(user=user).exists():
            student_ids = ParentGuardian.objects.filter(user=user).values_list("students__id", flat=True)
            return qs.filter(id__in=student_ids)

        # Staff sees only their school
        school = getattr(self.request, "school", None) or user.school
        if school:
            return qs.filter(school=school)

        return qs.none()

    def get_serializer_class(self):
        if self.action == "create":
            return StudentCreateSerializer
        if self.action in ["update", "partial_update"]:
            return StudentUpdateSerializer
        if self.action == "list":
            return StudentSimpleSerializer
        return StudentSerializer

    @action(detail=True, methods=["post"], url_path="status")
    def update_status(self, request, pk=None):
        student = self.get_object()
        serializer = StudentStatusUpdateSerializer(
            data=request.data, context={"student": student}
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        student.student_status = data["student_status"]
        student.status_reason = data.get("reason", "")
        if "exit_date" in data:
            student.exit_date = data["exit_date"]

        student.save(update_fields=["student_status", "status_reason", "exit_date", "updated_at"])
        return Response(StudentSerializer(student).data)



# PARENT GUARDIAN VIEWSET
@extend_schema_view(
    list=extend_schema(summary="List parents/guardians"),
    create=extend_schema(summary="Create parent + user account"),
)
class ParentGuardianViewSet(viewsets.ModelViewSet):
    queryset = ParentGuardian.objects.select_related("user").prefetch_related("students")
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["relationship", "is_primary"]
    search_fields = ["user__first_name", "user__last_name", "user__phone"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            self.required_action = "read"
        elif self.action == "create":
            self.required_action = "create"
        elif self.action in ["update", "partial_update", "update_status"]:
            self.required_action = "update"
        elif self.action == "destroy":
            self.required_action = "delete"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if ParentGuardian.objects.filter(user=user).exists():
            return qs.filter(user=user)

        if user.school:
            return qs.filter(students__school=user.school)

        return qs.none()

    def get_serializer_class(self):
        if self.action == "create":
            return ParentGuardianCreateSerializer
        return ParentGuardianSerializer


#  MEDICAL HISTORY VIEWSET
@extend_schema_view(
    list=extend_schema(summary="List medical records"),
    create=extend_schema(summary="Add medical record"),
)
class StudentMedicalHistoryViewSet(viewsets.ModelViewSet):
    queryset = StudentMedicalHistory.objects.select_related(
        "student__user", "student__school", "logged_by"
    )
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["student", "record_type"]
    ordering_fields = ["date", "created_at"]
    ordering = ["-date"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            self.required_action = "read"
        elif self.action == "create":
            self.required_action = "create"
        elif self.action in ["update", "partial_update", "update_status"]:
            self.required_action = "update"
        elif self.action == "destroy":
            self.required_action = "delete"
        else:
            self.required_action = "read"
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Parents see only their children's records
        if ParentGuardian.objects.filter(user=user).exists():
            student_ids = ParentGuardian.objects.filter(user=user).values_list("students__id", flat=True)
            return qs.filter(student__id__in=student_ids)

        if user.school:
            return qs.filter(student__school=user.school)

        return qs.none()

    def get_serializer_class(self):
        if self.action == "create":
            return MedicalHistoryCreateSerializer
        return StudentMedicalHistorySerializer

    def perform_create(self, serializer):
        serializer.save(logged_by=self.request.user)