from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from schools.models import School
from students.models import StudentProfile

from ..models import Announcement, Feedback, Notification, ParentTeacherMeeting
from .serializers import (
    AnnouncementSerializer,
    FeedbackSerializer,
    FeedbackStatsSerializer,
    NotificationSerializer,
    ParentTeacherMeetingSerializer,
    SimpleNotificationSerializer,
    UnreadNotificationCountSerializer,
)
from core.choices.communications import (
    AnnouncementStatusChoices,
    FeedbackStatusChoices,
    MeetingStatusChoices,
    NotificationCategoryChoices,
    NotificationPriorityChoices,
)


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Notifications.

    Supports:
    - CRUD operations for notifications
    - Mark as read/acknowledged
    - Filter by read status, category, priority
    - Get unread notifications count
    """

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["notification_category", "priority", "read_at"]
    search_fields = ["title", "message"]
    ordering_fields = ["created_at", "priority"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """
        Users can only see their own notifications.
        """
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()

        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        """Mark a notification as read."""
        notification = self.get_object()

        if notification.read_at:
            return Response(
                {"detail": "Notification is already marked as read."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        notification.read_at = timezone.now()
        notification.save()

        serializer = self.get_serializer(notification)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        """Acknowledge a notification with an action."""
        notification = self.get_object()
        action_type = request.data.get("action")

        if not action_type:
            return Response(
                {"error": "action is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        notification.acknowledgement_action = action_type
        notification.acknowledged_at = timezone.now()
        if not notification.read_at:
            notification.read_at = timezone.now()
        notification.save()

        serializer = self.get_serializer(notification)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = self.get_queryset().filter(read_at__isnull=True).count()
        high = (
            self.get_queryset()
            .filter(read_at__isnull=True, priority__in=[NotificationPriorityChoices.HIGH, NotificationPriorityChoices.CRITICAL])
            .count()
        )

        return Response({"total_unread": count, "high_priority_unread": high})

    @action(detail=False, methods=["get"])
    def unread(self, request):
        """Get all unread notifications."""
        queryset = self.get_queryset().filter(read_at__isnull=True)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SimpleNotificationSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = SimpleNotificationSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get notification statistics."""
        queryset = self.get_queryset()

        stats = {
            "count": queryset.count(),
            "high_priority": queryset.filter(priority__in=[NotificationPriorityChoices.HIGH, NotificationPriorityChoices.CRITICAL]).count(),
            "categories": dict(
                queryset.values("notification_category")
                .annotate(count=Count("id"))
                .values_list("notification_category", "count")
            ),
        }

        serializer = UnreadNotificationCountSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def mark_all_as_read(self, request):
        """Mark all notifications as read."""
        updated = (
            self.get_queryset()
            .filter(read_at__isnull=True)
            .update(read_at=timezone.now())
        )

        return Response({"detail": f"Marked {updated} notifications as read."})

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        """Get notifications grouped by category."""
        categories = {}

        for category in NotificationCategoryChoices.choices:
            category_code, category_name = category
            notifications = self.get_queryset().filter(
                notification_category=category_code
            )
            serializer = SimpleNotificationSerializer(notifications, many=True)
            categories[category_name] = serializer.data

        return Response(categories)


class FeedbackViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Feedback.

    Supports:
    - CRUD operations for feedback
    - Submit anonymous feedback
    - Assign feedback to staff
    - Resolve feedback with ratings
    - Filter by status, priority, category
    """

    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        "feedback_status",
        "priority",
        "feedback_category",
        "feedback_type",
    ]
    search_fields = ["title", "message", "resolution"]

    def get_queryset(self):
        """
        Users can see:
        - All feedback if superuser
        - Feedback they submitted
        - Feedback assigned to them
        - Feedback related to their school
        """
        user = self.request.user

        if user.is_superuser:
            return Feedback.objects.all()

        queryset = Feedback.objects.filter(Q(submitted_by=user) | Q(assigned_to=user))

        # If user is staff, include feedback from their school
        if hasattr(user, "staff_profile"):
            school = user.staff_profile.school
            queryset = queryset | Feedback.objects.filter(
                Q(related_to_student__school=school)
                | Q(related_to_staff__school=school)
            )

        # If user is a student, include feedback related to them
        if hasattr(user, "student_profile"):
            queryset = queryset | Feedback.objects.filter(
                related_to_student=user.student_profile
            )

        return queryset.distinct()

    def perform_create(self, serializer):
        """Set submitted_by to current user."""
        serializer.save(submitted_by=self.request.user)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """Assign feedback to a staff member."""
        feedback = self.get_object()
        assigned_to_id = request.data.get("assigned_to")

        if not assigned_to_id:
            return Response(
                {"error": "assigned_to is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            assigned_to = User.objects.get(id=assigned_to_id)

            # Check if user is staff
            if not hasattr(assigned_to, "staff_profile"):
                return Response(
                    {"error": "Can only assign feedback to staff members."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            feedback.assigned_to = assigned_to
            feedback.save()

            serializer = self.get_serializer(feedback)
            return Response(serializer.data)

        except User.DoesNotExist:
            return Response(
                {"error": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        """Resolve feedback with resolution text."""
        feedback = self.get_object()
        resolution = request.data.get("resolution")

        if not resolution:
            return Response(
                {"error": "resolution is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        feedback.resolution = resolution
        feedback.feedback_status = Feedback.RESOLVED
        feedback.resolved_by = request.user
        feedback.resolved_at = timezone.now()
        feedback.save()

        serializer = self.get_serializer(feedback)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def rate(self, request, pk=None):
        """Rate resolved feedback."""
        feedback = self.get_object()
        rating = request.data.get("rating")

        if feedback.feedback_status != Feedback.RESOLVED:
            return Response(
                {"error": "Only resolved feedback can be rated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if rating is None:
            return Response(
                {"error": "rating is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError
        except (ValueError, TypeError):
            return Response(
                {"error": "Rating must be an integer between 1 and 5."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        feedback.user_rating = rating
        feedback.save()

        serializer = self.get_serializer(feedback)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get feedback statistics."""
        queryset = self.get_queryset()

        # Calculate resolution time
        resolved_feedback = queryset.filter(
            feedback_status=FeedbackStatusChoices.RESOLVED, resolved_at__isnull=False
        )
        resolution_times = []

        for fb in resolved_feedback:
            if fb.created_at and fb.resolved_at:
                hours = (fb.resolved_at - fb.created_at).total_seconds() / 3600
                resolution_times.append(hours)

        avg_resolution_time = (
            sum(resolution_times) / len(resolution_times) if resolution_times else 0
        )

        stats = {
            "total": queryset.count(),
            "resolved": queryset.filter(feedback_status=FeedbackStatusChoices.RESOLVED).count(),
            "pending": queryset.exclude(feedback_status=FeedbackStatusChoices.RESOLVED).count(),
            "avg_resolution_time_hours": avg_resolution_time,
            "avg_rating": queryset.filter(user_rating__isnull=False).aggregate(
                avg=Avg("user_rating")
            )["avg"]
            or 0,
            "by_category": dict(
                queryset.values("feedback_category")
                .annotate(count=Count("id"))
                .values_list("feedback_category", "count")
            ),
            "by_type": dict(
                queryset.values("feedback_type")
                .annotate(count=Count("id"))
                .values_list("feedback_type", "count")
            ),
        }

        serializer = FeedbackStatsSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_assigned(self, request):
        """Get feedback assigned to the current user."""
        queryset = self.get_queryset().filter(assigned_to=request.user)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Announcements.

    Supports:
    - CRUD operations for announcements
    - Publish/unpublish announcements
    - Filter by school, category, status
    - Get active announcements
    """

    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "school",
        "announcement_category",
        "priority",
        "announcement_status",
    ]
    search_fields = ["title", "content"]
    ordering_fields = ["publish_date", "priority"]
    ordering = ["-publish_date"]

    def get_queryset(self):
        """
        Users can see announcements from their school.
        """
        user = self.request.user

        if user.is_superuser:
            return Announcement.objects.all()

        if hasattr(user, "staff_profile"):
            school = user.staff_profile.school
            return Announcement.objects.filter(school=school)

        if hasattr(user, "student_profile"):
            school = user.student_profile.school
            return Announcement.objects.filter(school=school)

        return Announcement.objects.none()

    def perform_create(self, serializer):
        """Set created_by to current user."""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """Publish an announcement."""
        announcement = self.get_object()

        if announcement.announcement_status == AnnouncementStatusChoices.PUBLISHED:
            return Response(
                {"detail": "Announcement is already published."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        announcement.announcement_status = AnnouncementStatusChoices.PUBLISHED
        if not announcement.publish_date:
            announcement.publish_date = timezone.now()
        announcement.save()

        serializer = self.get_serializer(announcement)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        """Acknowledge an announcement (if required)."""
        announcement = self.get_object()

        if not announcement.requires_acknowledgment:
            return Response(
                {"detail": "This announcement does not require acknowledgment."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        announcement.acknowledgment_count += 1
        announcement.save()

        # Create acknowledgment notification
        Notification.objects.create(
            user=request.user,
            sender=announcement.created_by,
            category=Notification.SYSTEM,
            priority=Notification.NORMAL,
            title=f"Acknowledged: {announcement.title}",
            message=f"You have acknowledged the announcement: {announcement.title}",
            action_url=f"/announcements/{announcement.id}/",
        )

        serializer = self.get_serializer(announcement)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get active (published and not expired) announcements."""
        now = timezone.now()
        queryset = (
            self.get_queryset()
            .filter(announcement_status=AnnouncementStatusChoices.PUBLISHED, publish_date__lte=now)
            # .exclude(Q(expiry_date__lt=now) & Q(expiry_date__isnull=False))
            .filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=now))
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        """Get upcoming announcements (scheduled for future)."""
        now = timezone.now()
        queryset = self.get_queryset().filter(
            announcement_status__in=[AnnouncementStatusChoices.PENDING, AnnouncementStatusChoices.PUBLISHED],
            publish_date__gt=now,
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ParentTeacherMeetingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Parent-Teacher Meetings.

    Supports:
    - CRUD operations for meetings
    - Add/remove invitees
    - Take attendance
    - Filter by date, status, school
    """

    queryset = ParentTeacherMeeting.objects.all()
    serializer_class = ParentTeacherMeetingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["school", "meeting_status", "date"]
    search_fields = ["title", "purpose", "venue"]
    ordering_fields = ["date", "start_time"]
    ordering = ["date", "start_time"]

    def get_queryset(self):
        """
        Users can see meetings:
        - From their school
        - Where they are organizer
        - Where they are in invitees list
        """
        user = self.request.user

        if user.is_superuser:
            return ParentTeacherMeeting.objects.all()

        queryset = ParentTeacherMeeting.objects.none()

        # If user has a school (staff/student)
        if hasattr(user, "staff_profile"):
            school = user.staff_profile.school
            queryset = ParentTeacherMeeting.objects.filter(school=school)
        elif hasattr(user, "student_profile"):
            school = user.student_profile.school
            queryset = ParentTeacherMeeting.objects.filter(school=school)

        # Also include meetings where user is organizer or invitee
        queryset = queryset | ParentTeacherMeeting.objects.filter(
            Q(organizer=user) | Q(invitees__contains=[str(user.id)])
        )

        return queryset.distinct()

    def perform_create(self, serializer):
        """Set organizer to current user."""
        serializer.save(organizer=self.request.user)

    @action(detail=True, methods=["post"])
    def add_invitee(self, request, pk=None):
        """Add a user to meeting invitees."""
        meeting = self.get_object()
        invitee_id = request.data.get("invitee_id")

        if not invitee_id:
            return Response(
                {"error": "invitee_id is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Check if already invited
        if str(invitee_id) in meeting.invitees:
            return Response(
                {"detail": "User is already invited."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        meeting.invitees.append(str(invitee_id))
        meeting.save()

        # Send notification to invitee
        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            invitee = User.objects.get(id=invitee_id)
            Notification.objects.create(
                user=invitee,
                sender=meeting.organizer,
                category=Notification.EVENT,
                priority=(
                    Notification.HIGH
                    if meeting.meeting_status == MeetingStatusChoices.IN_PROGRESS
                    else Notification.NORMAL
                ),
                title=f"Meeting Invitation: {meeting.title}",
                message=f"You are invited to: {meeting.title}\nDate: {meeting.date}\nTime: {meeting.start_time} - {meeting.end_time}",
                action_url=f"/meetings/{meeting.id}/",
            )
        except User.DoesNotExist:
            pass

        serializer = self.get_serializer(meeting)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def record_attendance(self, request, pk=None):
        """Record attendance for the meeting."""
        meeting = self.get_object()
        attendee_id = request.data.get("attendee_id")
        attended = request.data.get("attended", True)

        if not attendee_id:
            return Response(
                {"error": "attendee_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if attendee is in invitees
        if str(attendee_id) not in meeting.invitees:
            return Response(
                {"error": "User is not invited to this meeting."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update or add attendance record
        attendance_updated = False
        for i, record in enumerate(meeting.attendance):
            if record.get("user_id") == str(attendee_id):
                meeting.attendance[i]["attended"] = attended
                meeting.attendance[i]["timestamp"] = timezone.now().isoformat()
                attendance_updated = True
                break

        if not attendance_updated:
            meeting.attendance.append(
                {
                    "user_id": str(attendee_id),
                    "attended": attended,
                    "timestamp": timezone.now().isoformat(),
                }
            )

        meeting.save()

        serializer = self.get_serializer(meeting)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """Mark meeting as in progress."""
        meeting = self.get_object()

        if meeting.meeting_status == MeetingStatusChoices.IN_PROGRESS:
            return Response(
                {"detail": "Meeting is already in progress."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        meeting.meeting_status = MeetingStatusChoices.IN_PROGRESS
        meeting.save()

        serializer = self.get_serializer(meeting)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Mark meeting as completed with minutes."""
        meeting = self.get_object()
        minutes = request.data.get("minutes", "")

        meeting.meeting_status = MeetingStatusChoices.COMPLETED
        if minutes:
            meeting.minutes = minutes
        meeting.save()

        serializer = self.get_serializer(meeting)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def upcoming_meetings(self, request):
        """Get upcoming meetings."""
        today = timezone.now().date()
        queryset = (
            self.get_queryset()
            .filter(date__gte=today, meeting_status=MeetingStatusChoices.SCHEDULED)
            .order_by("date", "start_time")
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_meetings(self, request):
        """Get meetings where current user is organizer or invitee."""
        user = self.request.user
        queryset = (
            self.get_queryset()
            .filter(Q(organizer=user) | Q(invitees__contains=[str(user.id)]))
            .order_by("date", "start_time")
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
