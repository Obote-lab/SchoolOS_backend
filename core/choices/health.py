from django.utils.translation import gettext_lazy as _
from django.db import models


class RecordTypeChoices(models.TextChoices):
        VACCINATION = "vaccination", _("Vaccination")
        CHECKUP = "checkup", _("Checkup")
        ILLNESS = "illness", _("Illness / Treatment")
        ACCIDENT = "accident", _("Accident / Injury")
        ALLERGY = "allergy", _("Allergy Event")
        OTHER = "other", _("Other")