import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.utils import timezone
from schools.models import School
from core.choices.communications import (
    NotificationCategoryChoices,
    NotificationPriorityChoices,
    FeedbackTypeChoices,
    FeedbackCategoryChoices,
    FeedbackPriorityChoices,
    FeedbackStatusChoices,
    AnnouncementCategoryChoices,
    AnnouncementPriorityChoices,
    AnnouncementStatusChoices,
    MeetingStatusChoices
)

class Notification(models.Model):
    """Model representing notifications sent to users."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification_id = models.CharField(max_length=50, unique=True)  # NOT/2025/001
    user = models.ForeignKey("accounts.CustomUser",on_delete=models.CASCADE,related_name="notifications_received",)
    sender = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL, null=True,blank=True,related_name="notifications_sent",)
    notification_category = models.CharField(max_length=20, choices=NotificationCategoryChoices.choices)
    priority = models.CharField(max_length=10, choices=NotificationPriorityChoices.choices, default=NotificationPriorityChoices.NORMAL)
    title = models.CharField(max_length=200)
    message = models.TextField()
    action_url = models.URLField(blank=True)
    channels = models.JSONField(default=list, blank=True)  # SMS, Email, App, WhatsApp
    delivery_status = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_action = models.CharField(max_length=50, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    related_object = GenericForeignKey("content_type", "object_id")

    # Optional: shortcut properties
    @property
    def related_title(self):
        if self.related_object:
            return str(self.related_object)
        return None

    class Meta:
        ordering = ["-created_at", "-priority"]

    def __str__(self):
        return f"{self.notification_id}: {self.title}"

    def save(self, *args, **kwargs):
        if not self.notification_id:
            with transaction.atomic():
                year = timezone.now().year
                last = (
                    Notification.objects.select_for_update()
                    .filter(notification_id__startswith=f"NOT/{year}/")
                    .order_by("-notification_id")
                    .first()
                )
                number = int(last.notification_id.split("/")[-1]) + 1 if last else 1
                self.notification_id = f"NOT/{year}/{number:03d}"
        super().save(*args, **kwargs)


class Feedback(models.Model):
    """Model representing feedback from users."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feedback_type = models.CharField(max_length=15, choices=FeedbackTypeChoices.choices)
    feedback_category = models.CharField(max_length=20, choices=FeedbackCategoryChoices.choices)
    submitted_by = models.ForeignKey("accounts.CustomUser",on_delete=models.CASCADE,related_name="feedback_submitted", )
    related_to_student = models.ForeignKey("students.StudentProfile", on_delete=models.SET_NULL, null=True, blank=True)
    related_to_staff = models.ForeignKey( "staff.StaffProfile", on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    anonymous = models.BooleanField(default=False)
    contact_allowed = models.BooleanField(default=True)
    priority = models.CharField(max_length=10, choices=FeedbackPriorityChoices.choices, default=FeedbackPriorityChoices.NORMAL)
    assigned_to = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL,null=True, blank=True,related_name="feedback_assigned",)
    feedback_status = models.CharField(max_length=20, choices=FeedbackStatusChoices.choices, default=FeedbackStatusChoices.SUBMITTED)
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL, null=True,blank=True,related_name="feedback_resolved",)
    resolved_at = models.DateTimeField(null=True, blank=True)
    user_rating = models.IntegerField(null=True, blank=True)
    user_followup_feedback = models.TextField(blank=True)
    escalation_path = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-priority"]

    def __str__(self):
        if self.anonymous:
            return f"Anonymous {self.feedback_type}: {self.title}"
        return f"{self.submitted_by} - {self.feedback_type}: {self.title}"


class Announcement(models.Model):
    """Model representing school announcements."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="announcements")
    title = models.CharField(max_length=200)
    content = models.TextField()
    announcement_category = models.CharField(max_length=20, choices=AnnouncementCategoryChoices.choices)
    priority = models.CharField(max_length=10, choices=AnnouncementPriorityChoices.choices, default=AnnouncementPriorityChoices.NORMAL)
    target_audience = models.JSONField(default=dict, blank=True)
    publish_date = models.DateTimeField()
    expiry_date = models.DateTimeField(null=True, blank=True)
    requires_acknowledgment = models.BooleanField(default=False)
    acknowledgment_count = models.IntegerField(default=0)
    created_by = models.ForeignKey( "accounts.CustomUser", on_delete=models.CASCADE,related_name="announcements_created",)
    approved_by = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL,null=True,blank=True,related_name="announcements_approved",)
    attachments = models.JSONField(default=list, blank=True)
    channels = models.JSONField(default=list, blank=True)
    announcement_status = models.CharField(max_length=20,choices=AnnouncementStatusChoices.choices,default=AnnouncementStatusChoices.DRAFT,)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-publish_date", "-priority"]

    def __str__(self):
        return f"{self.title} ({self.school.code})"


class ParentTeacherMeeting(models.Model):
    """Model representing parent-teacher meetings."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="parent_teacher_meetings")
    title = models.CharField(max_length=200)
    purpose = models.TextField()
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    venue = models.CharField(max_length=200)
    organizer = models.ForeignKey( "accounts.CustomUser", on_delete=models.CASCADE, related_name="meetings_organized",)
    invitees = models.JSONField(default=list, blank=True)
    agenda = models.JSONField(default=list, blank=True)
    minutes = models.TextField(blank=True)
    decisions = models.JSONField(default=list, blank=True)
    action_items = models.JSONField(default=list, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    meeting_status = models.CharField( max_length=15, choices=MeetingStatusChoices.choices, default=MeetingStatusChoices.SCHEDULED)
    attendance = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.title} on {self.date}"
