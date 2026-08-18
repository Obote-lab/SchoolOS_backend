from django.db import models
from django.utils.translation import gettext_lazy as _


class DisciplineCategoryChoices(models.TextChoices):
    ACADEMIC = "academic", _("Academic")
    BEHAVIORAL = "behavioral", _("Behavioral")
    SOCIAL = "social", _("Social")
    SAFETY = "safety", _("Safety")
    PROPERTY = "property", _("Property")


class DisciplineSeverityChoices(models.TextChoices):
    MINOR = "minor", _("Minor")
    MODERATE = "moderate", _("Moderate")
    MAJOR = "major", _("Major")
    CRITICAL = "critical", _("Critical")


class DisciplineStatusChoices(models.TextChoices):
    REPORTED = "reported", _("Reported")
    INVESTIGATING = "investigating", _("Investigating")
    RESOLVED = "resolved", _("Resolved")
    ESCALATED = "escalated", _("Escalated")
    CLOSED = "closed", _("Closed")


class CounselingSessionTypeChoices(models.TextChoices):
    ACADEMIC = "academic", _("Academic")
    BEHAVIORAL = "behavioral", _("Behavioral")
    CAREER = "career", _("Career")
    EMOTIONAL = "emotional", _("Emotional")
    CRISIS = "crisis", _("Crisis")


class CounselingSessionStatusChoices(models.TextChoices):
    SCHEDULED = "scheduled", _("Scheduled")
    COMPLETED = "completed", _("Completed")
    CANCELLED = "cancelled", _("Cancelled")
    NO_SHOW = "no_show", _("No Show")


class NutritionQualityChoices(models.TextChoices):
    POOR = "poor", _("Poor")
    FAIR = "fair", _("Fair")
    GOOD = "good", _("Good")
    EXCELLENT = "excellent", _("Excellent")


class ExerciseFrequencyChoices(models.TextChoices):
    NONE = "none", _("None")
    RARE = "rare", _("Rare")
    WEEKLY = "weekly", _("Weekly")
    DAILY = "daily", _("Daily")