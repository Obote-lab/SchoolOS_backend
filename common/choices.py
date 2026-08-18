from django.db import models
from django.utils.translation import gettext_lazy as _


class ScoreLevelChoices(models.IntegerChoices):
    """1–10 score scale for inspections, assessments, etc."""

    ONE = 1, "1"
    TWO = 2, "2"
    THREE = 3, "3"
    FOUR = 4, "4"
    FIVE = 5, "5"
    SIX = 6, "6"
    SEVEN = 7, "7"
    EIGHT = 8, "8"
    NINE = 9, "9"
    TEN = 10, "10"


class StressLevelChoices(models.TextChoices):
    """Shared stress/wellness level scale"""

    LOW = "low", _("Low")
    MEDIUM = "medium", _("Medium")
    HIGH = "high", _("High")
    CRITICAL = "critical", _("Critical")


class AcademicStressLevelChoices(models.TextChoices):
    LOW = "low", _("Low")
    MEDIUM = "medium", _("Medium")
    HIGH = "high", _("High")
    CRITICAL = "critical", _("Critical")


class NutritionQualityChoices(models.TextChoices):
    POOR = "poor", _("Poor")
    FAIR = "fair", _("Fair")
    GOOD = "good", _("Good")
    EXCELLENT = "excellent", _("Excellent")
