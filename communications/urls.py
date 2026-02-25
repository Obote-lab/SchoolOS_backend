from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.viewsets import (
    NotificationViewSet,
    FeedbackViewSet,
    AnnouncementViewSet,
    ParentTeacherMeetingViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'feedback', FeedbackViewSet, basename='feedback')
router.register(r'announcements', AnnouncementViewSet, basename='announcement')
router.register(r'meetings', ParentTeacherMeetingViewSet, basename='meeting')

urlpatterns = [
    path('', include(router.urls)),
]

app_name = 'communications'