from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import (
    # Core flexible layer
    AcademicFrameworkViewSet,
    PathwayViewSet,
    LevelViewSet,
    GradingSchemeViewSet,
    GradingSchemeVersionViewSet,
    AssessmentSchemeViewSet,
    AssessmentSchemeVersionViewSet,
    # Competency graph
    LearningAreaViewSet,
    StrandViewSet,
    SubStrandViewSet,
    LearningOutcomeViewSet,
    CompetencyEvidenceViewSet,
    # Existing evolved
    SubjectViewSet,
    SubjectAssignmentViewSet,
    LessonPlanViewSet,
    ExamViewSet,
    ExamResultViewSet,
    ContinuousAssessmentViewSet,
)

router = DefaultRouter()

# Flexible academic system
router.register(r"frameworks", AcademicFrameworkViewSet, basename="academic-framework")
router.register(r"pathways", PathwayViewSet, basename="pathway")
router.register(r"levels", LevelViewSet, basename="level")

# Grading & Assessment schemes (versioned)
router.register(r"grading-schemes", GradingSchemeViewSet, basename="grading-scheme")
router.register(r"grading-scheme-versions", GradingSchemeVersionViewSet, basename="grading-scheme-version")
router.register(r"assessment-schemes", AssessmentSchemeViewSet, basename="assessment-scheme")
router.register(r"assessment-scheme-versions", AssessmentSchemeVersionViewSet, basename="assessment-scheme-version")

# Competency graph (CBC / hybrid)
router.register(r"learning-areas", LearningAreaViewSet, basename="learning-area")
router.register(r"strands", StrandViewSet, basename="strand")
router.register(r"sub-strands", SubStrandViewSet, basename="sub-strand")
router.register(r"learning-outcomes", LearningOutcomeViewSet, basename="learning-outcome")
router.register(r"competency-evidence", CompetencyEvidenceViewSet, basename="competency-evidence")

# Classic academic operations
router.register(r"subjects", SubjectViewSet, basename="subject")
router.register(r"subject-assignments", SubjectAssignmentViewSet, basename="subject-assignment")
router.register(r"lesson-plans", LessonPlanViewSet, basename="lesson-plan")
router.register(r"exams", ExamViewSet, basename="exam")
router.register(r"exam-results", ExamResultViewSet, basename="exam-result")
router.register(r"continuous-assessments", ContinuousAssessmentViewSet, basename="continuous-assessment")

urlpatterns = [
    path("", include(router.urls)),
]