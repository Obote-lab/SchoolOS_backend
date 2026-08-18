from django.utils.translation import gettext_lazy as _
from django.db import models


class StudentCategoryChoices(models.TextChoices):
        REGULAR = "REG", _("Regular")
        BURSARY = "BUR", _("Bursary")
        SCHOLARSHIP = "SCH", _("Scholarship")
        SPECIAL_NEEDS = "SPN", _("Special Needs")
        SPONSORED = "SPON", _("Sponsored")


class StudentStatusChoices(models.TextChoices):
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")
        TRANSFERRED = "transferred", _("Transferred")
        GRADUATED = "graduated", _("Graduated")
        WITHDRAWN = "withdrawn", _("Withdrawn")
        EXPELLED = "expelled", _("Expelled")
        DECEASED = "deceased", _("Deceased")