from django.db import models
from django.utils.translation import gettext_lazy as _


class NotificationCategoryChoices(models.TextChoices):
    ACADEMIC = "academic", _("Academic")
    FINANCIAL = "financial", _("Financial")
    ATTENDANCE = "attendance", _("Attendance")
    HEALTH = "health", _("Health")
    EVENT = "event", _("Event")
    EMERGENCY = "emergency", _("Emergency")
    SYSTEM = "system", _("System")


class NotificationPriorityChoices(models.TextChoices):
    LOW = "low", _("Low")
    NORMAL = "normal", _("Normal")
    HIGH = "high", _("High")
    CRITICAL = "critical", _("Critical")


class FeedbackTypeChoices(models.TextChoices):
    COMPLAINT = "complaint", _("Complaint")
    SUGGESTION = "suggestion", _("Suggestion")
    COMPLIMENT = "compliment", _("Compliment")
    QUERY = "query", _("Query")
    REPORT = "report", _("Report")


class FeedbackCategoryChoices(models.TextChoices):
    ACADEMIC = "academic", _("Academic")
    ADMINISTRATIVE = "administrative", _("Administrative")
    FACILITIES = "facilities", _("Facilities")
    SAFETY = "safety", _("Safety")
    OTHER = "other", _("Other")


class FeedbackPriorityChoices(models.TextChoices):
    LOW = "low", _("Low")
    NORMAL = "normal", _("Normal")
    HIGH = "high", _("High")
    URGENT = "urgent", _("Urgent")


class FeedbackStatusChoices(models.TextChoices):
    SUBMITTED = "submitted", _("Submitted")
    UNDER_REVIEW = "under_review", _("Under Review")
    RESOLVED = "resolved", _("Resolved")
    ESCALATED = "escalated", _("Escalated")
    CLOSED = "closed", _("Closed")


class AnnouncementCategoryChoices(models.TextChoices):
    EVENT = "event", _("Event")
    HOLIDAY = "holiday", _("Holiday")
    EXAM = "exam", _("Exam")
    MEETING = "meeting", _("Meeting")
    GENERAL = "general", _("General")


class AnnouncementPriorityChoices(models.TextChoices):
    NORMAL = "normal", _("Normal")
    IMPORTANT = "important", _("Important")
    EMERGENCY = "emergency", _("Emergency")


class AnnouncementStatusChoices(models.TextChoices):
    DRAFT = "draft", _("Draft")
    PENDING = "pending", _("Pending")
    PUBLISHED = "published", _("Published")
    EXPIRED = "expired", _("Expired")
    ARCHIVED = "archived", _("Archived")


class MeetingStatusChoices(models.TextChoices):
    SCHEDULED = "scheduled", _("Scheduled")
    IN_PROGRESS = "in_progress", _("In Progress")
    COMPLETED = "completed", _("Completed")
    CANCELLED = "cancelled", _("Cancelled")