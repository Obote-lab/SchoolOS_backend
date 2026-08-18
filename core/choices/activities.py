from django.db import models
from django.utils.translation import gettext_lazy as _


class ActivityCategoryChoices(models.TextChoices):
    SPORT = "sport", _("Sport")
    CLUB = "club", _("Club")
    ARTS = "arts", _("Arts")
    LEADERSHIP = "leadership", _("Leadership")
    COMMUNITY = "community", _("Community")
    ACADEMIC = "academic", _("Academic")


class ActivityStatusChoices(models.TextChoices):
    ACTIVE = "active", _("Active")
    INACTIVE = "inactive", _("Inactive")
    SEASONAL = "seasonal", _("Seasonal")


class ActivitySeasonChoices(models.TextChoices):
    TERM1 = "term1", _("Term 1")
    TERM2 = "term2", _("Term 2")
    TERM3 = "term3", _("Term 3")
    ANNUAL = "annual", _("Annual")


class ActivityRoleChoices(models.TextChoices):
    CAPTAIN = "captain", _("Captain")
    MEMBER = "member", _("Member")
    RESERVE = "reserve", _("Reserve")
    COORDINATOR = "coordinator", _("Coordinator")


class StudentActivityStatusChoices(models.TextChoices):
    ACTIVE = "active", _("Active")
    INACTIVE = "inactive", _("Inactive")
    GRADUATED = "graduated", _("Graduated")
    REMOVED = "removed", _("Removed")


class PerformanceLevelChoices(models.TextChoices):
    BEGINNER = "beginner", _("Beginner")
    INTERMEDIATE = "intermediate", _("Intermediate")
    ADVANCED = "advanced", _("Advanced")
    ELITE = "elite", _("Elite")


class PotentialLevelChoices(models.TextChoices):
    SCHOOL = "school", _("School")
    COUNTY = "county", _("County")
    NATIONAL = "national", _("National")
    INTERNATIONAL = "international", _("International")


class CompetitionLevelChoices(models.TextChoices):
    INTERCLASS = "interclass", _("Interclass")
    INTERSCHOOL = "interschool", _("Interschool")
    COUNTY = "county", _("County")
    NATIONAL = "national", _("National")
    INTERNATIONAL = "international", _("International")