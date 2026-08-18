from django.db import models
from django.utils.translation import gettext_lazy as _


class ReligionChoices(models.TextChoices):
        CHRISTIAN = "christian", _("Christian")
        MUSLIM = "muslim", _("Muslim")
        HINDU = "hindu", _("Hindu")
        OTHER = "other", _("Other")
        NONE = "none", _("None")


class DisabilityChoices(models.TextChoices):
        NONE = "NONE", _("None")
        PHYSICAL = "PHY", _("Physical")
        VISUAL = "VIS", _("Visual")
        HEARING = "HEA", _("Hearing")
        LEARNING = "LEA", _("Learning")
        MULTIPLE = "MUL", _("Multiple")



class BloodGroupChoices(models.TextChoices):
        A_POS = "A+", _("A+")
        A_NEG = "A-", _("A-")
        B_POS = "B+", _("B+")
        B_NEG = "B-", _("B-")
        AB_POS = "AB+", _("AB+")
        AB_NEG = "AB-", _("AB-")
        O_POS = "O+", _("O+")
        O_NEG = "O-", _("O-")



class RelationshipChoices(models.TextChoices):
        FATHER = "FATHER", _("Father")
        MOTHER = "MOTHER", _("Mother")
        GUARDIAN = "GUARDIAN", _("Guardian")
        SIBLING = "SIBLING", _("Sibling")
        OTHER = "OTHER", _("Other")