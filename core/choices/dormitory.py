from django.db import models
from django.utils.translation import gettext_lazy as _


class DormTypeChoices(models.TextChoices):
    BOYS = "boys", _("Boys")
    GIRLS = "girls", _("Girls")
    MIXED = "mixed", _("Mixed")
    STAFF_QUARTERS = "staff", _("Staff Quarters")


class DormStatusChoices(models.TextChoices):
    OPEN = "open", _("Open")
    CLOSED = "closed", _("Closed")
    UNDER_RENOVATION = "under_renovation", _("Under Renovation")
    QUARANTINE = "quarantine", _("Quarantine")