from django.db import models
from django.utils.translation import gettext_lazy as _



class SchoolTypeChoices(models.TextChoices):
        PRIMARY = "primary", "Primary School"
        SECONDARY = "secondary", "Secondary School"
        MIXED = "mixed", "Mixed (Primary & Secondary)"
        SPECIAL_NEEDS = "special_needs", "Special Needs School"
        TVET = "tvet", "TVET Institute"




class SchoolCategoryChoices(models.TextChoices):
    PUBLIC = "public", "Public School"
    PRIVATE = "private", "Private School"
    MISSION = "mission", "Mission School"
    INTERNATIONAL = "international", "International School"
    COMMUNITY = "community", "Community School"



class BoardingStatusChoices(models.TextChoices):
    DAY = "day", "Day School"
    BOARDING = "boarding", "Boarding School"
    MIXED = "mixed", "Day & Boarding"

class OnboardingStatusChoices(models.TextChoices):
    PENDING = "pending", "Pending Setup"
    PRINCIPAL_CREATED = "principal_created", "Principal Created"
    STRUCTURES_SETUP = "structures_setup", "Basic Structures Setup"
    ACTIVE = "active", "Active & Operational"
    SUSPENDED = "suspended", "Suspended"
    ARCHIVED = "archived", "Archived"