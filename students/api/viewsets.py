import logging
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (OpenApiParameter, extend_schema,extend_schema_view,)
from drf_spectacular.types import OpenApiTypes
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
    AssignClassSerializer,LinkParentSerializer
)
from core.choices.students import StudentStatusChoices


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
        description="Scoped by role: student→self, parent→children, staff→school.",
        parameters=[
            OpenApiParameter("school", OpenApiTypes.UUID, required=False),
            OpenApiParameter("current_class", OpenApiTypes.UUID, required=False),
            OpenApiParameter("student_status", OpenApiTypes.STR, required=False),
            OpenApiParameter("student_category", OpenApiTypes.STR, required=False),
            OpenApiParameter("gender", OpenApiTypes.STR, required=False),
            OpenApiParameter("search", OpenApiTypes.STR, required=False),
        ],
        responses={200: StudentSimpleSerializer(many=True)},
        tags=["Students"],
    ),
    retrieve=extend_schema(
        summary="Get student profile",
        responses={200: StudentSerializer},
        tags=["Students"],
    ),
    create=extend_schema(
        summary="Admit student (creates user + profile)",
        request=StudentCreateSerializer,
        responses={201: StudentSerializer},
        tags=["Students"],
    ),
    update=extend_schema(
        summary="Update student",
        request=StudentUpdateSerializer,
        responses={200: StudentSerializer},
        tags=["Students"],
    ),
    partial_update=extend_schema(
        summary="Partial update student",
        request=StudentUpdateSerializer,
        responses={200: StudentSerializer},
        tags=["Students"],
    ),
    destroy=extend_schema(
        summary="Withdraw student (soft)",
        responses={200: OpenApiTypes.OBJECT},
        tags=["Students"],
    ),
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
        # if self.action in ["list", "retrieve"]:
        #     self.required_action = "read"

        if self.action in ["update", "partial_update", "update_status", "assign_class", "link_parent"]:
            self.required_action = "update"
        elif self.action in ["statistics", "at_risk", "parents", "medical_history"]:
            self.required_action = "read"

        elif self.action == "create":
            self.required_action = "create"
        # elif self.action in ["update", "partial_update", "update_status"]:
        #     self.required_action = "update"
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



    @extend_schema(
        summary="Update student status",
        request=StudentStatusUpdateSerializer,
        responses={200: StudentSerializer, 400: OpenApiTypes.OBJECT},
        tags=["Students"],
    )
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


    @extend_schema(
    summary="Assign student to classroom",
    request=AssignClassSerializer,
    responses={200: StudentSerializer},
    tags=["Students"],
    )
    @action(detail=True, methods=["post"], url_path="assign-class")
    def assign_class(self, request, pk=None):
        student = self.get_object()
        ser = AssignClassSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        from schools.models import ClassRoom
        classroom = get_object_or_404(ClassRoom, pk=ser.validated_data["classroom_id"])
        if classroom.school_id != student.school_id:
            return Response({"error": "Classroom must be in the same school."}, status=400)
        student.current_class = classroom
        student.save(update_fields=["current_class", "updated_at"])
        return Response(StudentSerializer(student).data)


@extend_schema(
    summary="List parents for this student",
    responses={200: ParentGuardianSimpleSerializer(many=True)},
    tags=["Students"],
)
@action(detail=True, methods=["get"], url_path="parents")
def parents(self, request, pk=None):
    student = self.get_object()
    qs = student.parents.select_related("user")
    return Response(ParentGuardianSimpleSerializer(qs, many=True).data)


@extend_schema(
    summary="List medical history for this student",
    responses={200: StudentMedicalHistorySerializer(many=True)},
    tags=["Students"],
)
@action(detail=True, methods=["get"], url_path="medical-history")
def medical_history(self, request, pk=None):
    student = self.get_object()
    qs = student.medical_history.select_related("logged_by")
    return Response(StudentMedicalHistorySerializer(qs, many=True).data)


@extend_schema(
    summary="Link existing parent to student",
    request=LinkParentSerializer,
    responses={200: StudentSerializer},
    tags=["Students"],
)
@action(detail=True, methods=["post"], url_path="link-parent")
def link_parent(self, request, pk=None):
    student = self.get_object()
    ser = LinkParentSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    parent = get_object_or_404(ParentGuardian, pk=ser.validated_data["parent_id"])
    parent.students.add(student)
    if ser.validated_data.get("is_primary"):
        parent.is_primary = True
        parent.save(update_fields=["is_primary"])
    return Response(StudentSerializer(student).data)


@extend_schema(
    summary="School student statistics",
    responses={200: OpenApiTypes.OBJECT},
    tags=["Students"],
)
@action(detail=False, methods=["get"], url_path="statistics")
def statistics(self, request):
    qs = self.get_queryset()
    from django.db.models import Count, Avg
    return Response({
        "total": qs.count(),
        "active": qs.filter(student_status=StudentStatusChoices.ACTIVE).count(),
        "by_status": list(qs.values("student_status").annotate(c=Count("id"))),
        "by_category": list(qs.values("student_category").annotate(c=Count("id"))),
        "by_class": list(
            qs.filter(current_class__isnull=False)
            .values("current_class__classroom_name")
            .annotate(c=Count("id"))
        ),
        "avg_risk_score": qs.aggregate(a=Avg("risk_score"))["a"],
    })


@extend_schema(
    summary="Students above risk threshold",
    parameters=[OpenApiParameter("min_score", OpenApiTypes.NUMBER, required=False)],
    responses={200: StudentSimpleSerializer(many=True)},
    tags=["Students"],
)
@action(detail=False, methods=["get"], url_path="at-risk")
def at_risk(self, request):
    min_score = float(request.query_params.get("min_score", 50))
    qs = self.get_queryset().filter(risk_score__gte=min_score).order_by("-risk_score")
    page = self.paginate_queryset(qs)
    ser = StudentSimpleSerializer(page or qs, many=True)
    if page is not None:
        return self.get_paginated_response(ser.data)
    return Response(ser.data)


def destroy(self, request, *args, **kwargs):
    student = self.get_object()
    from django.utils import timezone
    student.student_status = StudentStatusChoices.WITHDRAWN
    student.exit_date = timezone.now().date()
    student.status_reason = request.data.get("reason", "Withdrawn via API")
    student.save(update_fields=["student_status", "exit_date", "status_reason", "updated_at"])
    return Response({"message": "Student withdrawn.", "admission_number": student.admission_number})



# PARENT GUARDIAN VIEWSET
@extend_schema_view(
    list=extend_schema(summary="List parents", responses={200: ParentGuardianSerializer(many=True)}, tags=["Parents"]),
    retrieve=extend_schema(responses={200: ParentGuardianSerializer}, tags=["Parents"]),
    create=extend_schema(request=ParentGuardianCreateSerializer, responses={201: ParentGuardianSerializer}, tags=["Parents"]),
    update=extend_schema(responses={200: ParentGuardianSerializer}, tags=["Parents"]),
    partial_update=extend_schema(responses={200: ParentGuardianSerializer}, tags=["Parents"]),
    destroy=extend_schema(tags=["Parents"]),
)
class ParentGuardianViewSet(viewsets.ModelViewSet):
    queryset = ParentGuardian.objects.select_related("user").prefetch_related("students")
    module = "parents"
    permission_classes = [IsAuthenticated, HasPermission]

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


    @extend_schema(
        summary="List children for this parent",
        responses={200: StudentSimpleSerializer(many=True)},
        tags=["Parents"],
    )
    @action(detail=True, methods=["get"], url_path="children")
    def children(self, request, pk=None):
        parent = self.get_object()
        return Response(StudentSimpleSerializer(parent.students.all(), many=True).data)

    @extend_schema(
        summary="Set as primary guardian",
        responses={200: ParentGuardianSerializer},
        tags=["Parents"],
    )
    @action(detail=True, methods=["post"], url_path="set-primary")
    def set_primary(self, request, pk=None):
        parent = self.get_object()
        parent.is_primary = True
        parent.save(update_fields=["is_primary"])
        return Response(ParentGuardianSerializer(parent).data)


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



    