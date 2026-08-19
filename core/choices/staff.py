from django.db import models
from django.utils.translation import gettext_lazy as _


class StaffTypeChoices(models.TextChoices):
    TEACHER = "teacher", _("Teacher")
    PRINCIPAL = "principal", _("Principal")
    DEPUTY = "deputy", _("Deputy Principal")
    HOD = "hod", _("Head of Department")
    ADMIN = "admin", _("Administrator")
    MATRON = "matron", _("Matron")
    SECURITY = "security", _("Security Officer")
    DRIVER = "driver", _("Driver")
    COOK = "cook", _("Cook")
    NURSE = "nurse", _("Nurse")
    LIBRARIAN = "librarian", _("Librarian")
    LAB_TECH = "lab_tech", _("Lab Technician")
    OTHER = "other", _("Other Support Staff")


class EmploymentTypeChoices(models.TextChoices):
    PERMANENT = "permanent", _("Permanent")
    CONTRACT = "contract", _("Contract")
    INTERN = "intern", _("Intern")
    VOLUNTEER = "volunteer", _("Volunteer")


class StaffAttendanceStatusChoices(models.TextChoices):
    PRESENT = "present", _("Present")
    ABSENT = "absent", _("Absent")
    LATE = "late", _("Late")
    LEAVE = "leave", _("On Leave")