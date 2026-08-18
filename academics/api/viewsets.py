import logging
from collections import Counter

from django.db.models import Avg, Max, Min, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import request, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.permissions import HasPermission

from ..models import (
    ContinuousAssessment,
    Exam,
    ExamResult,
    GradingSystem,
    LessonPlan,
    Subject,
    SubjectAssignment,
)
from .serializers import (
    BulkExamResultsUploadSerializer,
    ContinuousAssessmentCreateSerializer,
    ContinuousAssessmentListSerializer,
    ExamCreateSerializer,
    ExamDetailSerializer,
    ExamListSerializer,
    ExamResultCreateSerializer,
    ExamResultDetailSerializer,
    ExamResultListSerializer,
    GradingSystemListSerializer,
    GradingSystemSerializer,
    LessonPlanCreateSerializer,
    LessonPlanDetailSerializer,
    LessonPlanListSerializer,
    SubjectAssignmentListSerializer,
    SubjectCreateSerializer,
    SubjectDetailSerializer,
    SubjectListSerializer,
)
from core.choices.academic import ExamStatusChoices, LessonPlanStatusChoices

logger = logging.getLogger(__name__)


# Permission Classes
class CanManageAcademics(IsAuthenticated, HasPermission):
    """
    Teachers can read/write own assignments/lessons/exams
    Admins/HODs can manage all in school
    """
    required_action = "manage_academics"

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        school = getattr(request, 'school', None)
        if not school or getattr(obj, 'school', None) != school:
            return False

        # Allow if user is the teacher (for assignments, lesson plans)
        if hasattr(obj, 'teacher') and obj.teacher.user == request.user:
            return True

        # Allow school admins / HODs / Principal
        return request.user.user_roles.filter(
            school=school,
            role__name__in=["Principal", "Deputy Principal", "Head of Department", "Administrator"],
            is_active=True
        ).exists()


class CanViewAcademics(IsAuthenticated):
    """Read-only access for parents/students/teachers"""

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "school") and obj.school != request.school:
            return False
        if hasattr(request.user, "student_profile"):
            return (
                hasattr(obj, "student") and obj.student == request.user.student_profile
            )
        if hasattr(request.user, "parent_profile"):
            return (
                hasattr(obj, "student")
                and obj.student.parents.filter(user=request.user).exists()
            )
        return True


#  Subject ViewSet
@extend_schema(tags=["Subjects"])
class SubjectViewSet(viewsets.ModelViewSet):
    """
    Manage subjects (CRUD + activation toggle).
    Scoped to current school via middleware.
    """

    queryset = Subject.objects.select_related("school", "department", "created_by")
    permission_classes = [CanManageAcademics]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["category", "level", "stream", "is_active", "department"]
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]

    def get_serializer_class(self):
        if self.action == "list":
            return SubjectListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return SubjectCreateSerializer
        return SubjectDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(self.request, "school") and self.request.school:
            return qs.filter(school=self.request.school)
        return qs.none()

    @extend_schema(summary="Toggle subject active/inactive status")
    @action(detail=True, methods=["post"], url_path="toggle_active")
    def toggle_active(self, request, pk=None):
        subject = self.get_object()
        subject.is_active = not subject.is_active
        subject.save(update_fields=["is_active"])
        return Response(SubjectDetailSerializer(subject).data)


#  SubjectAssignment ViewSet
@extend_schema(tags=["Subject Assignments"])
class SubjectAssignmentViewSet(viewsets.ModelViewSet):
    """
    Assign teachers to subjects/classes (CRUD).
    """

    queryset = SubjectAssignment.objects.select_related(
        "subject",
        "teacher__user",
        "class_room",
        "academic_year",
        "term"
    )
    permission_classes = [CanManageAcademics]
    serializer_class = SubjectAssignmentListSerializer

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["teacher", "class_room", "academic_year", "term", "is_primary"]
    search_fields = ["subject__name", "subject__code", "teacher__user__first_name"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, 'school', None)
        if school:
            return qs.filter(subject__school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()


#  LessonPlan ViewSet
@extend_schema(tags=["Lesson Plans"])
class LessonPlanViewSet(viewsets.ModelViewSet):
    """
    Manage weekly/daily lesson plans per subject assignment.
    """

    queryset = LessonPlan.objects.select_related("subject_assignment__subject")
    permission_classes = [CanManageAcademics]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["subject_assignment", "lesson_plan_status", "week_number"]
    search_fields = ["topic", "sub_topic"]
    ordering_fields = ["week_number", "date", "created_at"]
    ordering = ["week_number", "date"]

    def get_serializer_class(self):
        if self.action == "list":
            return LessonPlanListSerializer
        return LessonPlanDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            "subject_assignment__subject",
            "subject_assignment__teacher__user",
            "subject_assignment__class_room",
        )

        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(subject_assignment__subject__school=school)

        if self.request.user.is_superuser:
            return qs

        return qs.none()

    @extend_schema(summary="Mark lesson as taught today")
    @action(detail=True, methods=["post"])
    def mark_taught(self, request, pk=None):
        plan = self.get_object()
        plan.actual_date_taught = timezone.now().date()
        plan.lesson_plan_status = LessonPlanStatusChoices.TAUGHT
        plan.save(update_fields=["actual_date_taught", "lesson_plan_status"])
        return Response(LessonPlanDetailSerializer(plan).data)


#  Exam ViewSet
@extend_schema(tags=["Exams"])
class ExamViewSet(viewsets.ModelViewSet):
    """
    Manage exams/tests (scheduling, lifecycle, results summary).
    """

    queryset = Exam.objects.select_related(
        "term",
        "academic_year",
        "subject",
        "class_room",
        "supervisor__user",
    )
    permission_classes = [CanManageAcademics]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "exam_status",
        "term",
        "academic_year",
        "subject",
        "class_room",
        "is_compulsory",
    ]
    search_fields = ["name"]
    ordering_fields = ["exam_date", "created_at"]
    ordering = ["-exam_date"]

    def get_serializer_class(self):
        if self.action == "list":
            return ExamListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return ExamCreateSerializer
        return ExamDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, 'school', None)

        if school:
            return qs.filter(
                Q(subject__school=school) |
                Q(class_room__school=school)
            )
        
        # System root / superuser sees everything
        if self.request.user.is_superuser:
            return qs
            
        return qs.none()

    @extend_schema(summary="Publish results (marks visible to students/parents)")
    @action(detail=True, methods=["post"])
    def publish_results(self, request, pk=None):
        exam = self.get_object()
        if exam.exam_status != ExamStatusChoices.COMPLETED:
            return Response(
                {"detail": "Exam must be completed before publishing"},
                status=400,
            )

        exam.exam_status = ExamStatusChoices.PUBLISHED
        exam.publish_date = timezone.now().date()
        exam.save(update_fields=["exam_status", "publish_date"])

        return Response(ExamDetailSerializer(exam).data)



    @extend_schema(summary="Get detailed results summary (pass rate, grade distribution)")
    @action(detail=True, methods=["get"])
    def results_summary(self, request, pk=None):
        exam = self.get_object()
        results = ExamResult.objects.filter(exam=exam)

        if not results.exists():
            return Response({"message": "No results entered yet"}, status=200)

        avg = results.aggregate(avg=Avg("marks"))["avg"] or 0
        pass_threshold = exam.passing_marks or (exam.total_marks * 0.4)
        pass_count = results.filter(marks__gte=pass_threshold).count()
        total = results.count()

        # Simple grade distribution
        grades = results.values_list("grade", flat=True)
        grade_dist = dict(Counter(grade for grade in grades if grade))

        return Response(
            {
                "total_students": total,
                "average_marks": round(avg, 2),
                "highest": results.aggregate(max=Max("marks"))["max"],
                "lowest": results.aggregate(min=Min("marks"))["min"],
                "pass_rate": round((pass_count / total * 100), 1) if total else 0,
                "pass_count": pass_count,
                "grade_distribution": grade_dist,
            }
        )


#  ExamResult ViewSet
@extend_schema(tags=["Exam Results"])
class ExamResultViewSet(viewsets.ModelViewSet):
    """
    Manage individual/bulk exam results.
    """

    queryset = ExamResult.objects.select_related(
        "student", "subject", "exam", "marked_by", "verified_by"
    )
    permission_classes = [CanManageAcademics]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["student", "exam", "subject"]
    search_fields = [
        "student__admission_number",
        "student__user__first_name",
        "student__user__last_name",
    ]
    ordering_fields = ["marks", "created_at"]
    ordering = ["-marks"]

    def get_serializer_class(self):
        if self.action == "list":
            return ExamResultListSerializer
        return ExamResultCreateSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(self.request, "school") and self.request.school:
            return qs.filter(student__school=self.request.school)
        return qs.none()

    @extend_schema(summary="Bulk upload results via admission numbers")
    @action(detail=False, methods=["post"])
    def bulk_upload(self, request):
        serializer = BulkExamResultsUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result)


# ContinuousAssessment ViewSet
@extend_schema(tags=["Continuous Assessments"])
class ContinuousAssessmentViewSet(viewsets.ModelViewSet):
    """
    Manage ongoing assessments (CATs, homework, projects).
    """

    queryset = ContinuousAssessment.objects.select_related(
        "student", "subject", "term", "marked_by"
    )
    permission_classes = [CanManageAcademics]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["assessment_type", "subject", "term", "student"]
    search_fields = ["title", "student__admission_number"]
    ordering_fields = ["date_assigned", "marks_obtained"]
    ordering = ["-date_assigned"]

    def get_serializer_class(self):
        if self.action == "list":
            return ContinuousAssessmentListSerializer
        return ContinuousAssessmentCreateSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(self.request, "school") and self.request.school:
            return qs.filter(student__school=self.request.school)
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(marked_by=self.request.user)


#  GradingSystem ViewSet
@extend_schema(tags=["Grading Systems"])
class GradingSystemViewSet(viewsets.ModelViewSet):
    """
    Manage school-specific grading configurations.
    """

    queryset = GradingSystem.objects.select_related("school")
    serializer_class = GradingSystemSerializer
    permission_classes = [CanManageAcademics]

    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["system_type", "is_active"]
    search_fields = ["name"]

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(self.request, "school") and self.request.school:
            return qs.filter(school=self.request.school)
        return qs.none()

    @extend_schema(summary="Mark this grading system as the school's default")
    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        grading = self.get_object()
        if hasattr(request, "school") and grading.school != request.school:
            return Response({"detail": "Not authorized for this school"}, status=403)
        return Response(GradingSystemSerializer(grading).data)
