from django.db import models
from django.utils.translation import gettext_lazy as _


class GenderChoices(models.TextChoices):
    MALE = "male", _("Male")
    FEMALE = "female", _("Female")
    OTHER = "other", _("Other")
    PREFER_NOT_TO_SAY = "prefer_not_to_say", _("Prefer not to say")


class LanguageChoices(models.TextChoices):
    ENGLISH = "en", _("English")
    SWAHILI = "sw", _("Swahili")
    KIKUYU = "ki", _("Kikuyu")
    LUHYA = "lu", _("Luhya")
    KALENJIN = "ka", _("Kalenjin")
    LUO = "lo", _("Luo")
    KAMBA = "kb", _("Kamba")
    KISII = "ks", _("Kisii")
    MERU = "me", _("Meru")
    MAASAI = "ma", _("Maasai")
    FRENCH = "fr", _("French")
    ARABIC = "ar", _("Arabic")
    PORTUGUESE = "pt", _("Portuguese")
    OTHER = "other", _("Other")


class NotificationChannelChoices(models.TextChoices):
    SMS = "sms", _("SMS")
    EMAIL = "email", _("Email")
    PUSH = "push", _("Push Notification")
    WHATSAPP = "whatsapp", _("WhatsApp")
    IN_APP = "in_app", _("In-App")


class PriorityChoices(models.TextChoices):
    LOW = "low", _("Low")
    NORMAL = "normal", _("Normal")
    HIGH = "high", _("High")
    CRITICAL = "critical", _("Critical")
    URGENT = "urgent", _("Urgent")


class StatusChoices(models.TextChoices):
    DRAFT = "draft", _("Draft")
    ACTIVE = "active", _("Active")
    INACTIVE = "inactive", _("Inactive")
    ARCHIVED = "archived", _("Archived")
    PENDING = "pending", _("Pending")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")
    COMPLETED = "completed", _("Completed")
    CANCELLED = "cancelled", _("Cancelled")


class SeverityChoices(models.TextChoices):
    LOW = "low", _("Low")
    MEDIUM = "medium", _("Medium")
    HIGH = "high", _("High")
    CRITICAL = "critical", _("Critical")


class StressLevelChoices(models.TextChoices):
    LOW = "low", _("Low")
    MODERATE = "moderate", _("Moderate")
    HIGH = "high", _("High")
    CRITICAL = "critical", _("Critical")
    SEVERE = "severe", _("Severe")