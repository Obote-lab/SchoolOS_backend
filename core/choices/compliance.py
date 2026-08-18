from django.db import models
from django.utils.translation import gettext_lazy as _


class ExportTypeChoices(models.TextChoices):
    STUDENTS = "students", _("Students")
    FINANCE = "finance", _("Finance")
    ACADEMICS = "academics", _("Academics")
    HEALTH = "health", _("Health")
    FULL_BACKUP = "full_backup", _("Full Backup")


class ExportFormatChoices(models.TextChoices):
    EXCEL = "excel", _("Excel")
    PDF = "pdf", _("PDF")
    CSV = "csv", _("CSV")
    JSON = "json", _("JSON")


class HealthStatusChoices(models.TextChoices):
    SUCCESS = "success", _("Success")
    WARNING = "warning", _("Warning")
    FAILED = "failed", _("Failed")
    PENDING = "pending", _("Pending")


class SyncStatusChoices(models.TextChoices):
    SYNCED = "synced", _("Synced")
    PENDING = "pending", _("Pending")
    FAILED = "failed", _("Failed")


class ComplianceCheckTypeChoices(models.TextChoices):
    NEMIS = "nemis", _("NEMIS")
    TSC = "tsc", _("TSC")
    KNEC = "knec", _("KNEC")
    MINISTRY = "ministry", _("Ministry")
    SAFETY = "safety", _("Safety")
    FINANCIAL = "financial", _("Financial")


class ComplianceStatusChoices(models.TextChoices):
    COMPLIANT = "compliant", _("Compliant")
    PARTIAL = "partial", _("Partial")
    NON_COMPLIANT = "non_compliant", _("Non Compliant")
    NOT_APPLICABLE = "not_applicable", _("Not Applicable")