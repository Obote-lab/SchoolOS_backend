from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.viewsets import (
    ContinuousAssessmentViewSet,
    ExamResultViewSet,
    ExamViewSet,
    GradingSystemViewSet,
    LessonPlanViewSet,
    SubjectAssignmentViewSet,
    SubjectViewSet,
)

router = DefaultRouter()
router.register(r"subjects", SubjectViewSet, basename="subject")
router.register(r"subject-assignments", SubjectAssignmentViewSet, basename="subject-assignment")
router.register(r"lesson-plans", LessonPlanViewSet, basename="lesson-plan")
router.register(r"exams", ExamViewSet, basename="exam")
router.register(r"exam-results", ExamResultViewSet, basename="exam-result")
router.register(r"continuous-assessments", ContinuousAssessmentViewSet, basename="continuous-assessment")
router.register(r"grading-systems", GradingSystemViewSet, basename="grading-system")

urlpatterns = [
    path("", include(router.urls)),
]