import logging
from django.db.models import Q, Avg, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from accounts.api.permissions import HasPermission 
from .serializers import (
    SubjectListSerializer,
    SubjectDetailSerializer,
    SubjectCreateSerializer,
    SubjectAssignmentListSerializer,
    ExamListSerializer,
    ExamDetailSerializer,
    ExamCreateSerializer,
    ExamResultDetailSerializer,
    ExamResultCreateSerializer,
    ContinuousAssessmentSerializer,
    BulkExamResultsUploadSerializer,
    GradingSystemSerializer,
    SubjectAssignmentDetailSerializer
)
from ..models import (
    Subject,
    SubjectAssignment,
    Exam,
    ExamResult,
    ContinuousAssessment,
    GradingSystem,
)

logger = logging.getLogger(__name__)


#   Permissions (reused)
class IsSchoolAdmin(IsAuthenticated, HasPermission):
    """School admins can manage academic data"""
    required_action = "manage_academics"



#   Subject ViewSet
@extend_schema(tags=["Subjects"])
class SubjectViewSet(viewsets.ModelViewSet):
    """
    Manage subjects (list, create, update, toggle active).
    Filtered by school context.
    """
    queryset = Subject.objects.all()
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["category", "level", "is_active"]
    search_fields = ["subject_code", "subject_name"]
    ordering_fields = ["subject_code", "subject_name", "created_at"]
    ordering = ["subject_code"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy", "toggle_active"]:
            return [IsSchoolAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = self.request.headers.get("X-School-ID") or getattr(self.request.user, "school_id", None)
        if school_id:
            return qs.filter(school_id=school_id)
        return qs.none()

    def get_serializer_class(self):
        if self.action == "list":
            return SubjectListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return SubjectCreateSerializer
        return SubjectDetailSerializer

    @extend_schema(summary="Toggle subject active status")
    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None):
        subject = self.get_object()
        subject.is_active = not subject.is_active
        subject.save(update_fields=["is_active"])
        serializer = self.get_serializer(subject)
        return Response(serializer.data)



#   SubjectAssignment ViewSet
@extend_schema(tags=["Subject Assignments"])
class SubjectAssignmentViewSet(viewsets.ModelViewSet):
    """
    Manage subject-teacher-class assignments.
    """
    queryset = SubjectAssignment.objects.select_related("subject")
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["teacher_id", "class_room_id", "academic_year_id", "term_id", "is_primary"]
    search_fields = ["subject__subject_name", "subject__subject_code"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSchoolAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = self.request.headers.get("X-School-ID") or getattr(self.request.user, "school_id", None)
        if school_id:
            qs = qs.filter(subject__school_id=school_id)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return SubjectAssignmentListSerializer
        return SubjectAssignmentDetailSerializer  


#   Exam ViewSet
@extend_schema(tags=["Exams"])
class ExamViewSet(viewsets.ModelViewSet):
    """
    Manage exams/tests (scheduling, summary).
    """
    queryset = Exam.objects.all()
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["exam_status", "term_id", "academic_year_id"]
    search_fields = ["name"]
    ordering_fields = ["exam_date", "created_at"]
    ordering = ["-exam_date"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSchoolAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = self.request.headers.get("X-School-ID") or getattr(self.request.user, "school_id", None)
        if school_id:
            qs = qs.filter(subject__school_id=school_id)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ExamListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return ExamCreateSerializer
        return ExamDetailSerializer

    @extend_schema(summary="Get results summary for this exam")
    @action(detail=True, methods=["get"])
    def results_summary(self, request, pk=None):
        exam = self.get_object()
        results = ExamResult.objects.filter(exam=exam)

        if not results.exists():
            return Response({"message": "No results yet"}, status=200)

        summary = {
            "total_students": results.count(),
            "average_marks": round(results.aggregate(Avg("marks"))["marks__avg"] or 0, 2),
            "highest_marks": results.aggregate(Max("marks"))["marks__max"],
            "lowest_marks": results.aggregate(Min("marks"))["marks__min"],
            "pass_count": results.filter(marks__gte=exam.total_marks * 0.4).count(), 
        }

        return Response(summary)



#   ExamResult ViewSet
@extend_schema(tags=["Exam Results"])
class ExamResultViewSet(viewsets.ModelViewSet):
    """
    Manage exam results (individual + bulk upload).
    """
    queryset = ExamResult.objects.select_related("exam", "subject")
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["student_id", "exam", "subject"]
    search_fields = ["student_id"]
    ordering_fields = ["marks", "created_at"]
    ordering = ["-marks"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "bulk_upload"]:
            return [IsSchoolAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = self.request.headers.get("X-School-ID") or getattr(self.request.user, "school_id", None)
        if school_id:
            qs = qs.filter(subject__school_id=school_id)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ExamResultDetailSerializer
        return ExamResultCreateSerializer

    @extend_schema(summary="Bulk upload exam results")
    @action(detail=False, methods=["post"])
    def bulk_upload(self, request):
        serializer = BulkExamResultsUploadSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result)


#   ContinuousAssessment ViewSet
@extend_schema(tags=["Continuous Assessments"])
class ContinuousAssessmentViewSet(viewsets.ModelViewSet):
    """
    Manage continuous assessments (CATs, homework, projects).
    """
    queryset = ContinuousAssessment.objects.select_related("subject")
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["assessment_type", "subject", "term_id"]
    search_fields = ["title", "student_id"]
    ordering_fields = ["date_assigned", "marks_obtained"]
    ordering = ["-date_assigned"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSchoolAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = self.request.headers.get("X-School-ID") or getattr(self.request.user, "school_id", None)
        if school_id:
            qs = qs.filter(subject__school_id=school_id)
        return qs

    def get_serializer_class(self):
        return ContinuousAssessmentSerializer

    def perform_create(self, serializer):
        serializer.save(marked_by_id=self.request.user.id)



#   GradingSystem ViewSet
@extend_schema(tags=["Grading Systems"])
class GradingSystemViewSet(viewsets.ModelViewSet):
    """
    Manage school grading systems (KCSE, custom, etc.).
    """
    queryset = GradingSystem.objects.all()
    serializer_class = GradingSystemSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["system_type", "is_active"]
    search_fields = ["name"]

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = self.request.headers.get("X-School-ID") or getattr(self.request.user, "school_id", None)
        if school_id:
            return qs.filter(school_id=school_id)
        return qs.none()

    @extend_schema(summary="Set grading system as default for school")
    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        grading = self.get_object()
        school_id = request.headers.get("X-School-ID")

        if not school_id or grading.school_id != school_id:
            return Response({"detail": "Not authorized"}, status=403)

        GradingSystem.objects.filter(school_id=school_id, is_default=True).update(is_default=False)
        grading.is_default = True
        grading.save(update_fields=["is_default"])

        return Response(self.get_serializer(grading).data)