from django.db import models
from django.utils.translation import gettext_lazy as _


class SessionTypeChoices(models.TextChoices):
    MORNING_ASSEMBLY = "morning_assembly", _("Morning Assembly")
    CLASS_LESSON = "class", _("Class Lesson")
    DORMITORY_CHECK = "dormitory", _("Dormitory Check")
    MEAL = "meal", _("Meal Time")
    ACTIVITY = "activity", _("Co-curricular Activity")
    STUDY_HALL = "study", _("Supervised Study")
    CHAPEL = "chapel", _("Chapel/Religious")
    SPORTS = "sports", _("Sports/PE")
    LAB = "lab", _("Practical/Lab Session")
    OTHER = "other", _("Other")


class AttendanceSessionStatusChoices(models.TextChoices):
    SCHEDULED = "scheduled", _("Scheduled")
    ONGOING = "ongoing", _("Ongoing")
    COMPLETED = "completed", _("Completed")
    CANCELLED = "cancelled", _("Cancelled")


class AttendanceRecordStatusChoices(models.TextChoices):
    PRESENT = "present", _("Present")
    LATE = "late", _("Late")
    ABSENT = "absent", _("Absent")
    EXCUSED = "excused", _("Excused")
    SICK = "sick", _("Sick")
    SUSPENDED = "suspended", _("Suspended")


class AttendanceDeviceChoices(models.TextChoices):
    MANUAL = "manual", _("Manual Entry")
    BIOMETRIC = "biometric", _("Fingerprint/Face")
    QR_CODE = "qr", _("QR Scan")
    RFID = "rfid", _("RFID Card")
    MOBILE_APP = "mobile_app", _("Student/Parent App")
    GPS = "gps", _("GPS Check-in")


class AttendanceRiskLevelChoices(models.TextChoices):
    LOW = "low", _("Low")
    MEDIUM = "medium", _("Medium")
    HIGH = "high", _("High")
    CRITICAL = "critical", _("Critical")