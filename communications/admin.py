from django.contrib import admin

from .models import Announcement, Feedback, Notification, ParentTeacherMeeting


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "notification_id",
        "title",
        "user",
        "notification_category",
        "priority",
        "read_at",
        "created_at",
    )
    list_filter = ("notification_category", "priority", "read_at")
    search_fields = ("title", "message", "user__username", "notification_id")
    raw_id_fields = ("user", "sender")


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "feedback_type",
        "feedback_category",
        "submitted_by",
        "priority",
        "feedback_status",
        "created_at",
    )
    list_filter = (
        "feedback_type",
        "feedback_category",
        "priority",
        "feedback_status",
        "anonymous",
    )
    search_fields = ("title", "message", "submitted_by__username")
    raw_id_fields = (
        "submitted_by",
        "related_to_student",
        "related_to_staff",
        "assigned_to",
    )


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "school",
        "announcement_category",
        "priority",
        "announcement_status",
        "publish_date",
        "created_by",
    )
    list_filter = ("announcement_category", "priority", "announcement_status", "school")
    search_fields = ("title", "content", "school__school_name")
    raw_id_fields = ("school", "created_by", "approved_by")


@admin.register(ParentTeacherMeeting)
class ParentTeacherMeetingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "school",
        "date",
        "start_time",
        "end_time",
        "meeting_status",
        "organizer",
    )
    list_filter = ("meeting_status", "school", "date")
    search_fields = ("title", "purpose", "venue", "school__school_name")
    raw_id_fields = ("school", "organizer")
