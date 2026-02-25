from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.viewsets import (
    SubjectViewSet,
    SubjectAssignmentViewSet,
    ExamViewSet,
    ExamResultViewSet,
    ContinuousAssessmentViewSet,
    GradingSystemViewSet,
)

router = DefaultRouter()

# Register all viewsets
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'subject-assignments', SubjectAssignmentViewSet, basename='subjectassignment')
router.register(r'exams', ExamViewSet, basename='exam')
router.register(r'exam-results', ExamResultViewSet, basename='examresult')
router.register(r'assessments', ContinuousAssessmentViewSet, basename='continuousassessment')
router.register(r'grading-systems', GradingSystemViewSet, basename='gradingsystem')

# Simple URL patterns
urlpatterns = [
    path('', include(router.urls)),
]