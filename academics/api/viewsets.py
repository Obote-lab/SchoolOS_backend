import logging
from collections import Counter

from django.db.models import Avg, Max, Min, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api.permissions import HasPermission
from core.choices.academic import ExamStatusChoices, LessonPlanStatusChoices

from ..models import (
    AcademicFramework,
    Pathway,
    Level,
    GradingScheme,
    GradingSchemeVersion,
    AssessmentScheme,
    AssessmentSchemeVersion,
    LearningArea,
    Strand,
    SubStrand,
    LearningOutcome,
    CompetencyEvidence,
    Subject,
    SubjectAssignment,
    LessonPlan,
    Exam,
    ExamResult,
    ContinuousAssessment,
)
from .serializers import (
    # Framework
    AcademicFrameworkListSerializer,
    AcademicFrameworkDetailSerializer,
    AcademicFrameworkCreateSerializer,
    # Pathway
    PathwayListSerializer,
    PathwayDetailSerializer,
    PathwayCreateSerializer,
    # Level
    LevelListSerializer,
    LevelDetailSerializer,
    LevelCreateSerializer,
    # Grading
    GradingSchemeListSerializer,
    GradingSchemeDetailSerializer,
    GradingSchemeCreateSerializer,
    GradingSchemeVersionSerializer,
    GradingSchemeVersionCreateSerializer,
    # Assessment Scheme
    AssessmentSchemeListSerializer,
    AssessmentSchemeDetailSerializer,
    AssessmentSchemeCreateSerializer,
    AssessmentSchemeVersionSerializer,
    AssessmentSchemeVersionCreateSerializer,
    # Competency
    LearningAreaListSerializer,
    LearningAreaDetailSerializer,
    LearningAreaCreateSerializer,
    StrandSerializer,
    SubStrandSerializer,
    LearningOutcomeSerializer,
    CompetencyEvidenceListSerializer,
    CompetencyEvidenceCreateSerializer,
    # Subject
    SubjectListSerializer,
    SubjectDetailSerializer,
    SubjectCreateSerializer,
    # Assignment & Lesson
    SubjectAssignmentListSerializer,
    SubjectAssignmentCreateSerializer,
    LessonPlanListSerializer,
    LessonPlanDetailSerializer,
    LessonPlanCreateSerializer,
    # Exam
    ExamListSerializer,
    ExamDetailSerializer,
    ExamCreateSerializer,
    ExamResultListSerializer,
    ExamResultDetailSerializer,
    ExamResultCreateSerializer,
    ContinuousAssessmentListSerializer,
    ContinuousAssessmentCreateSerializer,
    BulkExamResultsUploadSerializer,
)

logger = logging.getLogger(__name__)


# Permission Classes
class CanManageAcademics(IsAuthenticated, HasPermission):
    """
    Teachers can read/write own assignments/lessons/exams.
    Admins / HODs / Principal can manage all in the school.
    """
    required_action = "manage_academics"
    module = "academics"

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        school = getattr(request, "school", None)
        obj_school = getattr(obj, "school", None)
        if obj_school is None and hasattr(obj, "framework"):
            obj_school = getattr(obj.framework, "school", None)
        if obj_school is None and hasattr(obj, "subject"):
            obj_school = getattr(obj.subject, "school", None)
        if obj_school is None and hasattr(obj, "student"):
            obj_school = getattr(obj.student, "school", None)

        if not school or (obj_school and obj_school != school):
            return False

        # Allow if user is the teacher on the object
        if hasattr(obj, "teacher") and getattr(obj.teacher, "user", None) == request.user:
            return True

        return request.user.user_roles.filter(
            school=school,
            role__name__in=[
                "Principal",
                "Deputy Principal",
                "Head of Department",
                "Administrator",
            ],
            is_active=True,
        ).exists()


class CanViewAcademics(IsAuthenticated):
    """Read-only access for parents / students / teachers."""

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        school = getattr(request, "school", None)
        if hasattr(obj, "school") and obj.school != school:
            return False
        if hasattr(request.user, "student_profile"):
            return hasattr(obj, "student") and obj.student == request.user.student_profile
        if hasattr(request.user, "parent_profile"):
            return (
                hasattr(obj, "student")
                and obj.student.parents.filter(user=request.user).exists()
            )
        return True


# 1. Academic Framework
@extend_schema_view(
    list=extend_schema(summary="List academic frameworks", tags=["Academic Frameworks"]),
    retrieve=extend_schema(summary="Retrieve academic framework", tags=["Academic Frameworks"]),
    create=extend_schema(summary="Create academic framework", tags=["Academic Frameworks"]),
    update=extend_schema(summary="Update academic framework", tags=["Academic Frameworks"]),
    partial_update=extend_schema(summary="Partial update academic framework", tags=["Academic Frameworks"]),
    destroy=extend_schema(summary="Delete academic framework", tags=["Academic Frameworks"]),
)
class AcademicFrameworkViewSet(viewsets.ModelViewSet):
    queryset = AcademicFramework.objects.select_related("school", "created_by")
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["template_type", "term_model", "supports_competencies", "is_active"]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "effective_from", "created_at"]
    ordering = ["-effective_from"]

    def get_serializer_class(self):
        if self.action == "list":
            return AcademicFrameworkListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return AcademicFrameworkCreateSerializer
        return AcademicFrameworkDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()

    @extend_schema(summary="Activate this framework (deactivate others)")
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        framework = self.get_object()
        school = framework.school

        # Soft-close other active frameworks
        AcademicFramework.objects.filter(
            school=school, is_active=True
        ).exclude(pk=framework.pk).update(
            is_active=False,
            effective_to=timezone.now().date(),
        )

        framework.is_active = True
        framework.effective_to = None
        framework.save(update_fields=["is_active", "effective_to"])
        return Response(AcademicFrameworkDetailSerializer(framework).data)


# 2. Pathway
@extend_schema(tags=["Pathways"])
class PathwayViewSet(viewsets.ModelViewSet):
    queryset = Pathway.objects.select_related("framework__school")
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["framework", "is_default", "is_active"]
    search_fields = ["name", "code"]
    ordering = ["sequence", "name"]

    def get_serializer_class(self):
        if self.action == "list":
            return PathwayListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return PathwayCreateSerializer
        return PathwayDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(framework__school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()


# 3. Level
@extend_schema(tags=["Levels"])
class LevelViewSet(viewsets.ModelViewSet):
    queryset = Level.objects.select_related("framework__school", "pathway")
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["framework", "pathway", "is_active", "is_graduation_level"]
    search_fields = ["name", "code"]
    ordering = ["sequence"]

    def get_serializer_class(self):
        if self.action == "list":
            return LevelListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return LevelCreateSerializer
        return LevelDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(framework__school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()


# 4. Grading Scheme + Version
@extend_schema(tags=["Grading Schemes"])
class GradingSchemeViewSet(viewsets.ModelViewSet):
    queryset = GradingScheme.objects.select_related("school", "framework", "pathway")
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["framework", "pathway", "is_default", "is_active"]
    search_fields = ["name", "code"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action == "list":
            return GradingSchemeListSerializer
        if self.action in ["create"]:
            return GradingSchemeCreateSerializer
        return GradingSchemeDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()

    @extend_schema(summary="Set as school default grading scheme")
    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        scheme = self.get_object()
        scheme.is_default = True
        scheme.is_active = True
        scheme.save()  # model save clears other defaults
        return Response(GradingSchemeDetailSerializer(scheme).data)

    @extend_schema(
        summary="Create a new version of this grading scheme",
        request=GradingSchemeVersionCreateSerializer,
        responses={201: GradingSchemeVersionSerializer},
    )
    @action(detail=True, methods=["post"], url_path="new-version")
    def new_version(self, request, pk=None):
        scheme = self.get_object()
        serializer = GradingSchemeVersionCreateSerializer(
            data={**request.data, "scheme": scheme.id},
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        version = serializer.save()
        return Response(
            GradingSchemeVersionSerializer(version).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Grading Scheme Versions"])
class GradingSchemeVersionViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list/retrieve of grading scheme versions."""
    queryset = GradingSchemeVersion.objects.select_related("scheme__school")
    serializer_class = GradingSchemeVersionSerializer
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["scheme", "is_current"]
    ordering = ["-version_number"]

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(scheme__school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()


# 5. Assessment Scheme + Version
@extend_schema(tags=["Assessment Schemes"])
class AssessmentSchemeViewSet(viewsets.ModelViewSet):
    queryset = AssessmentScheme.objects.select_related("school", "framework", "pathway")
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["framework", "pathway", "is_default", "is_active"]
    search_fields = ["name", "code"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action == "list":
            return AssessmentSchemeListSerializer
        if self.action == "create":
            return AssessmentSchemeCreateSerializer
        return AssessmentSchemeDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()

    @extend_schema(summary="Set as school default assessment scheme")
    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        scheme = self.get_object()
        scheme.is_default = True
        scheme.is_active = True
        scheme.save()
        return Response(AssessmentSchemeDetailSerializer(scheme).data)

    @extend_schema(
        summary="Create a new version of this assessment scheme",
        request=AssessmentSchemeVersionCreateSerializer,
        responses={201: AssessmentSchemeVersionSerializer},
    )
    @action(detail=True, methods=["post"], url_path="new-version")
    def new_version(self, request, pk=None):
        scheme = self.get_object()
        serializer = AssessmentSchemeVersionCreateSerializer(
            data={**request.data, "scheme": scheme.id},
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        version = serializer.save()
        return Response(
            AssessmentSchemeVersionSerializer(version).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Assessment Scheme Versions"])
class AssessmentSchemeVersionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AssessmentSchemeVersion.objects.select_related("scheme__school")
    serializer_class = AssessmentSchemeVersionSerializer
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["scheme", "is_current"]
    ordering = ["-version_number"]

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(scheme__school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()


# 6. Competency Graph
@extend_schema(tags=["Learning Areas"])
class LearningAreaViewSet(viewsets.ModelViewSet):
    queryset = LearningArea.objects.select_related("framework__school", "pathway")
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["framework", "pathway", "is_active"]
    search_fields = ["name", "code"]
    ordering = ["sequence", "name"]

    def get_serializer_class(self):
        if self.action == "list":
            return LearningAreaListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return LearningAreaCreateSerializer
        return LearningAreaDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(framework__school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()


@extend_schema(tags=["Strands"])
class StrandViewSet(viewsets.ModelViewSet):
    queryset = Strand.objects.select_related("learning_area__framework__school")
    serializer_class = StrandSerializer
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["learning_area", "is_active"]
    search_fields = ["name", "code"]
    ordering = ["sequence"]

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(learning_area__framework__school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()


@extend_schema(tags=["Sub-Strands"])
class SubStrandViewSet(viewsets.ModelViewSet):
    queryset = SubStrand.objects.select_related("strand__learning_area__framework__school")
    serializer_class = SubStrandSerializer
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["strand", "is_active"]
    search_fields = ["name", "code"]
    ordering = ["sequence"]

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(strand__learning_area__framework__school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()


@extend_schema(tags=["Learning Outcomes"])
class LearningOutcomeViewSet(viewsets.ModelViewSet):
    queryset = LearningOutcome.objects.select_related(
        "sub_strand__strand__learning_area__framework__school"
    )
    serializer_class = LearningOutcomeSerializer
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["sub_strand", "is_active", "related_subject"]
    search_fields = ["code", "statement"]
    ordering = ["sequence"]

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(
                sub_strand__strand__learning_area__framework__school=school
            )
        if self.request.user.is_superuser:
            return qs
        return qs.none()


@extend_schema(tags=["Competency Evidence"])
class CompetencyEvidenceViewSet(viewsets.ModelViewSet):
    queryset = CompetencyEvidence.objects.select_related(
        "student", "learning_outcome", "term", "academic_year", "recorded_by"
    )
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["student", "learning_outcome", "term", "academic_year", "competency_level"]
    search_fields = ["student__admission_number", "learning_outcome__code"]
    ordering = ["-recorded_at"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CompetencyEvidenceCreateSerializer
        return CompetencyEvidenceListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(student__school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()


# 7. Subject (evolved)
@extend_schema_view(
    list=extend_schema(summary="List subjects", tags=["Subjects"]),
    retrieve=extend_schema(summary="Retrieve subject", tags=["Subjects"]),
    create=extend_schema(summary="Create subject", tags=["Subjects"]),
    update=extend_schema(summary="Update subject", tags=["Subjects"]),
    partial_update=extend_schema(summary="Partial update subject", tags=["Subjects"]),
    destroy=extend_schema(summary="Delete subject", tags=["Subjects"]),
)
class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.select_related(
        "school", "department", "framework", "pathway", "level", "created_by"
    )
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "category", "framework", "pathway", "level",
        "legacy_level", "stream", "is_active", "department",
    ]
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
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()

    @extend_schema(summary="Toggle subject active status")
    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        subject = self.get_object()
        subject.is_active = not subject.is_active
        subject.save(update_fields=["is_active"])
        return Response(SubjectDetailSerializer(subject).data)


# 8. Subject Assignment
@extend_schema(tags=["Subject Assignments"])
class SubjectAssignmentViewSet(viewsets.ModelViewSet):
    queryset = SubjectAssignment.objects.select_related(
        "subject", "teacher__user", "class_room", "academic_year", "term"
    )
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["teacher", "class_room", "academic_year", "term", "is_primary"]
    search_fields = ["subject__name", "subject__code", "teacher__user__first_name"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SubjectAssignmentCreateSerializer
        return SubjectAssignmentListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(subject__school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()


# 9. Lesson Plan
@extend_schema(tags=["Lesson Plans"])
class LessonPlanViewSet(viewsets.ModelViewSet):
    queryset = LessonPlan.objects.select_related(
        "subject_assignment__subject",
        "subject_assignment__teacher__user",
        "subject_assignment__class_room",
    )
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["subject_assignment", "lesson_plan_status", "week_number"]
    search_fields = ["topic", "sub_topic"]
    ordering = ["week_number", "date"]

    def get_serializer_class(self):
        if self.action == "list":
            return LessonPlanListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return LessonPlanCreateSerializer
        return LessonPlanDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
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


# 10. Exam
@extend_schema(tags=["Exams"])
class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.select_related(
        "term", "academic_year", "subject", "class_room", "supervisor__user"
    )
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "exam_status", "term", "academic_year", "subject", "class_room", "is_compulsory"
    ]
    search_fields = ["name"]
    ordering = ["-exam_date"]

    def get_serializer_class(self):
        if self.action == "list":
            return ExamListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return ExamCreateSerializer
        return ExamDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(
                Q(subject__school=school) | Q(class_room__school=school)
            )
        if self.request.user.is_superuser:
            return qs
        return qs.none()

    @extend_schema(summary="Publish exam results")
    @action(detail=True, methods=["post"])
    def publish_results(self, request, pk=None):
        exam = self.get_object()
        if not ExamResult.objects.filter(exam=exam).exists():
            return Response({"detail": "No results to publish."}, status=400)
        if exam.exam_status == ExamStatusChoices.DRAFT:
            return Response(
                {"detail": "Schedule/complete exam before publishing."}, status=400
            )
        exam.exam_status = ExamStatusChoices.PUBLISHED
        exam.publish_date = timezone.now().date()
        exam.save(update_fields=["exam_status", "publish_date"])
        return Response(ExamDetailSerializer(exam).data)

    @extend_schema(summary="Mark exam as completed")
    @action(detail=True, methods=["post"])
    def mark_completed(self, request, pk=None):
        exam = self.get_object()
        exam.exam_status = ExamStatusChoices.COMPLETED
        exam.save(update_fields=["exam_status"])
        return Response(ExamDetailSerializer(exam).data)

    @extend_schema(summary="Get detailed results summary")
    @action(detail=True, methods=["get"])
    def results_summary(self, request, pk=None):
        exam = self.get_object()
        results = ExamResult.objects.filter(exam=exam)
        if not results.exists():
            return Response({"message": "No results entered yet"})

        avg = results.aggregate(avg=Avg("marks"))["avg"] or 0
        pass_threshold = exam.passing_marks or (exam.total_marks * 0.4)
        pass_count = results.filter(marks__gte=pass_threshold).count()
        total = results.count()
        grades = results.values_list("grade", flat=True)
        grade_dist = dict(Counter(g for g in grades if g))

        return Response({
            "total_students": total,
            "average_marks": round(avg, 2),
            "highest": results.aggregate(max=Max("marks"))["max"],
            "lowest": results.aggregate(min=Min("marks"))["min"],
            "pass_rate": round((pass_count / total * 100), 1) if total else 0,
            "pass_count": pass_count,
            "grade_distribution": grade_dist,
        })


# 11. Exam Result
@extend_schema(tags=["Exam Results"])
class ExamResultViewSet(viewsets.ModelViewSet):
    queryset = ExamResult.objects.select_related(
        "student", "subject", "exam", "marked_by", "verified_by",
        "grading_scheme_version", "assessment_scheme_version",
    )
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["student", "exam", "subject"]
    search_fields = [
        "student__admission_number",
        "student__user__first_name",
        "student__user__last_name",
    ]
    ordering = ["-marks"]

    def get_serializer_class(self):
        if self.action == "list":
            return ExamResultListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return ExamResultCreateSerializer
        return ExamResultDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(student__school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()

    @extend_schema(
        summary="Bulk upload results",
        request=BulkExamResultsUploadSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(detail=False, methods=["post"], url_path="bulk-upload")
    def bulk_upload(self, request):
        serializer = BulkExamResultsUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result)


# 12. Continuous Assessment
@extend_schema(tags=["Continuous Assessments"])
class ContinuousAssessmentViewSet(viewsets.ModelViewSet):
    queryset = ContinuousAssessment.objects.select_related(
        "student", "subject", "term", "marked_by",
        "grading_scheme_version", "assessment_scheme_version",
    )
    permission_classes = [CanManageAcademics]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["assessment_type", "subject", "term", "student"]
    search_fields = ["title", "student__admission_number"]
    ordering = ["-date_assigned"]

    def get_serializer_class(self):
        if self.action == "list":
            return ContinuousAssessmentListSerializer
        return ContinuousAssessmentCreateSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        school = getattr(self.request, "school", None)
        if school:
            return qs.filter(student__school=school)
        if self.request.user.is_superuser:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(marked_by=self.request.user)