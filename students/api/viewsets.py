import logging
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.permissions import HasPermission  
from ..models import ParentGuardian, Student, StudentMedicalHistory
from .serializers import (
    MedicalHistoryCreateSerializer,
    ParentGuardianCreateSerializer,
    ParentGuardianSerializer,
    ParentGuardianSimpleSerializer,
    StudentCreateSerializer,
    StudentSerializer,
    StudentSimpleSerializer,
    StudentStatusUpdateSerializer,
    StudentUpdateSerializer,
    StudentSearchSerializer,
    StudentMedicalHistorySerializer,
)

logger = logging.getLogger(__name__)


#   Permissions (reused across viewsets)
class IsSchoolStaffOrPrincipal(IsAuthenticated, HasPermission):
    required_action = "manage_students"


class IsParentOfStudent(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Student):
            return ParentGuardian.objects.filter(user=request.user, student=obj).exists()
        if hasattr(obj, "student"):
            return ParentGuardian.objects.filter(user=request.user, student=obj.student).exists()
        return False


class IsStudentOwner(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user



#   Student ViewSet
@extend_schema_view(
    list=extend_schema(
        summary="List students",
        description="Paginated list of students (filtered by school/class/status for staff)",
        parameters=[
            OpenApiParameter(name="school", type=OpenApiTypes.UUID, description="School ID filter"),
            OpenApiParameter(name="current_class", type=OpenApiTypes.UUID, description="Class ID filter"),
            OpenApiParameter(name="student_status", type=OpenApiTypes.STR, description="Status filter"),
            OpenApiParameter(name="student_category", type=OpenApiTypes.STR, description="Category filter"),
            OpenApiParameter(name="search", type=OpenApiTypes.STR, description="Search by name/admission"),
        ]
    ),
    retrieve=extend_schema(summary="Get student detail", description="Full student profile including parents"),
    create=extend_schema(summary="Create student", description="Create student + linked user account"),
    update=extend_schema(summary="Update student", description="Update student details"),
)
@extend_schema(tags=["Students"])
class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related(
        "user", "school", "current_class", "boarding_house",
        "current_academic_year", "current_term"
    ).prefetch_related("guardians__user")
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["school", "current_class", "student_status", "student_category", "gender"]
    search_fields = ["admission_number", "user__first_name", "user__last_name", "user__phone"]
    ordering_fields = ["admission_number", "date_of_birth", "admission_date", "student_status"]
    ordering = ["admission_number"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]  # + read-only for parents/students
        if self.action in ["create", "update", "partial_update", "destroy", "update_status"]:
            return [IsSchoolStaffOrPrincipal()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Students see only themselves
        if hasattr(user, "student_profile"):
            return qs.filter(user=user)

        # Parents see only their children
        if ParentGuardian.objects.filter(user=user).exists():
            student_ids = ParentGuardian.objects.filter(user=user).values_list("student_id", flat=True)
            return qs.filter(id__in=student_ids)

        # Staff / Principal see only their school
        if user.school:
            return qs.filter(school=user.school)

        return qs.none()

    def get_serializer_class(self):
        if self.action == "create":
            return StudentCreateSerializer
        if self.action in ["update", "partial_update"]:
            return StudentUpdateSerializer
        if self.action == "list":
            return StudentSimpleSerializer
        return StudentSerializer

    @extend_schema(
        summary="Update student status",
        request=StudentStatusUpdateSerializer,
        responses={200: StudentSerializer}
    )
    @action(detail=True, methods=["post"], url_path="status")
    def update_status(self, request, pk=None):
        student = self.get_object()
        serializer = StudentStatusUpdateSerializer(
            data=request.data, context={"student": student}
        )
        serializer.is_valid(raise_exception=True)

        try:
            student.update_status(
                serializer.validated_data["student_status"],
                serializer.validated_data.get("reason", "")
            )
            if "exit_date" in serializer.validated_data:
                student.exit_date = serializer.validated_data["exit_date"]
                student.save(update_fields=["exit_date"])

            return Response(StudentSerializer(student).data)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Search students",
        request=StudentSearchSerializer,
        responses={200: StudentSimpleSerializer(many=True)}
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        serializer = StudentSearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        qs = self.get_queryset()

        if q := filters.get("q"):
            qs = qs.filter(
                Q(admission_number__icontains=q) |
                Q(user__first_name__icontains=q) |
                Q(user__last_name__icontains=q) |
                Q(user__phone__icontains=q)
            )

        if filters.get("school"):
            qs = qs.filter(school_id=filters["school"])
        if filters.get("current_class"):
            qs = qs.filter(current_class_id=filters["current_class"])
        if filters.get("student_status"):
            qs = qs.filter(student_status=filters["student_status"])
        if filters.get("student_category"):
            qs = qs.filter(student_category=filters["student_category"])
        if filters.get("gender"):
            qs = qs.filter(gender=filters["gender"])

        serializer = StudentSimpleSerializer(qs, many=True)
        return Response(serializer.data)



#   ParentGuardian ViewSet
@extend_schema_view(
    list=extend_schema(summary="List parents/guardians"),
    retrieve=extend_schema(summary="Get parent/guardian detail"),
    create=extend_schema(summary="Create parent/guardian + user account"),
)
@extend_schema(tags=["Parents/Guardians"])
class ParentGuardianViewSet(viewsets.ModelViewSet):
    queryset = ParentGuardian.objects.select_related("user", "student__user", "student__school")
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["student", "relationship", "is_primary"]
    search_fields = ["user__first_name", "user__last_name", "user__phone", "student__admission_number"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        if self.action == "create":
            return [IsSchoolStaffOrPrincipal()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsSchoolStaffOrPrincipal()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if ParentGuardian.objects.filter(user=user).exists():
            return qs.filter(user=user)

        if user.school:
            return qs.filter(student__school=user.school)

        return qs.none()

    def get_serializer_class(self):
        if self.action == "create":
            return ParentGuardianCreateSerializer
        return ParentGuardianSerializer



#   StudentMedicalHistory ViewSet
@extend_schema_view(
    list=extend_schema(summary="List medical records"),
    retrieve=extend_schema(summary="Get medical record detail"),
    create=extend_schema(summary="Add medical record"),
)
@extend_schema(tags=["Medical History"])
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
            return [IsAuthenticated()]  # staff + parents of student
        if self.action == "create":
            return [IsSchoolStaffOrPrincipal()]
        return [IsSchoolStaffOrPrincipal()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Parents see only their children's records
        if ParentGuardian.objects.filter(user=user).exists():
            student_ids = ParentGuardian.objects.filter(user=user).values_list("student_id", flat=True)
            return qs.filter(student__id__in=student_ids)

        # Staff see only their school
        if user.school:
            return qs.filter(student__school=user.school)

        return qs.none()

    def get_serializer_class(self):
        if self.action == "create":
            return MedicalHistoryCreateSerializer
        return StudentMedicalHistorySerializer

    def perform_create(self, serializer):
        serializer.save(logged_by=self.request.user)