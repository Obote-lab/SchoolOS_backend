import logging
import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.gis.db.models import PointField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.choices.attendance import (
    AttendanceDeviceChoices,
    AttendanceRecordStatusChoices,
    AttendanceRiskLevelChoices,
    AttendanceSessionStatusChoices,
    SessionTypeChoices,
)

CustomUser = get_user_model()
logger = logging.getLogger(__name__)


class AttendanceSession(models.Model):
    """A single attendance-taking event (assembly, lesson, meal, dorm check-in, etc.)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School",on_delete=models.CASCADE,related_name="attendance_sessions")
    session_type = models.CharField(max_length=30, choices=SessionTypeChoices.choices)
    reference_id = models.UUIDField(null=True, blank=True, help_text=_("Link to ClassRoom, Dormitory, Event, etc.") )
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.CASCADE)
    term = models.ForeignKey("schools.Term",on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    expected_count = models.PositiveIntegerField(default=0, help_text=_("Expected number of participants"))
    actual_count = models.PositiveIntegerField(default=0, editable=False)
    conducted_by = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL,null=True,related_name="conducted_sessions",)
    verified_by = models.ForeignKey( "accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_sessions", )
    notes = models.TextField(blank=True)
    attendance_session_status = models.CharField(max_length=20,choices=AttendanceSessionStatusChoices.choices,default=AttendanceSessionStatusChoices.SCHEDULED,)
    is_automated = models.BooleanField(default=False, help_text=_("Triggered by biometric/QR/RFID device"))
    device_id = models.CharField( max_length=100, blank=True, help_text=_("Device identifier for automated sessions"), )
    location = PointField(null=True, blank=True, help_text=_("GPS coordinates if outdoor/mobile") )
    venue_name = models.CharField( max_length=200, blank=True, help_text=_("Room/building name"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Attendance Session")
        verbose_name_plural = _("Attendance Sessions")
        ordering = ["-date", "-start_time"]
        indexes = [
            models.Index(fields=["school", "date", "session_type"]),
            models.Index(fields=["attendance_session_status"]),
            models.Index(fields=["conducted_by"]),
            models.Index(fields=["reference_id"]),
        ]

    def __str__(self):
        return f"{self.get_session_type_display()} - {self.date} {self.start_time} ({self.school})"

    def clean(self):
        if self.end_time and self.start_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": _("End time must be after start time")})
        if self.actual_count > self.expected_count and self.expected_count > 0:
            raise ValidationError({"actual_count": _("Cannot exceed expected count")})

    def save(self, *args, **kwargs):
        if not self.pk:
            # Auto-fill current year/term if missing
            if not self.academic_year:
                self.academic_year = self.school.current_academic_year
            if not self.term:
                self.term = self.school.current_term
        super().save(*args, **kwargs)

    def update_actual_count(self):
        """Recalculate actual_count from records"""
        from .models import AttendanceRecord

        self.actual_count = AttendanceRecord.objects.filter(
            session=self,
            attendance_record_status__in=[
                AttendanceRecordStatusChoices.PRESENT,
                AttendanceRecordStatusChoices.LATE,
            ],
        ).count()
        self.save(update_fields=["actual_count"])


class AttendanceRecord(models.Model):
    """Individual attendance entry for a student in a session"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="records" )
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="attendance_records")
    attendance_record_status = models.CharField( max_length=20,choices=AttendanceRecordStatusChoices.choices,default=AttendanceRecordStatusChoices.PRESENT, )
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    doctor_note = models.BooleanField(default=False)
    parent_notified = models.BooleanField(default=False)
    verified_by = models.ForeignKey( "accounts.CustomUser",on_delete=models.SET_NULL, null=True,blank=True,related_name="verified_records",)
    device_used = models.CharField( max_length=20, choices=AttendanceDeviceChoices.choices, default=AttendanceDeviceChoices.MANUAL)
    location = PointField( null=True, blank=True, help_text=_("Exact GPS if device used"))
    photo_evidence = models.ImageField( upload_to="attendance/photos/%Y/%m/%d/", null=True, blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Attendance Record")
        verbose_name_plural = _("Attendance Records")
        unique_together = [["session", "student"]]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["session", "student"]),
            models.Index(fields=["attendance_record_status"]),
            models.Index(fields=["student", "created_at"]),
        ]

    def __str__(self):
        return f"{self.student.admission_number} - {self.get_attendance_record_status_display()} ({self.session.date})"

    def clean(self):
        if (
            self.check_out_time
            and self.check_in_time
            and self.check_out_time <= self.check_in_time
        ):
            raise ValidationError(
                {"check_out_time": _("Check-out must be after check-in")}
            )

        # Auto-detect late if check-in after session start + grace
        if self.check_in_time and self.session:
            session_start = timezone.make_aware(
                timezone.datetime.combine(self.session.date, self.session.start_time)
            )
            grace = timezone.timedelta(minutes=15)
            if self.check_in_time > session_start + grace:
                self.attendance_record_status = AttendanceRecordStatusChoices.LATE

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        # Update session count
        self.session.update_actual_count()


class AttendancePattern(models.Model):
    """Aggregated attendance statistics per student per term"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey( "students.StudentProfile", on_delete=models.CASCADE, related_name="attendance_patterns" )
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.CASCADE)
    term = models.ForeignKey("schools.Term", on_delete=models.CASCADE)
    total_sessions = models.PositiveIntegerField(default=0)
    present_count = models.PositiveIntegerField(default=0)
    late_count = models.PositiveIntegerField(default=0)
    absent_count = models.PositiveIntegerField(default=0)
    excused_count = models.PositiveIntegerField(default=0)
    attendance_rate = models.DecimalField(max_digits=5,decimal_places=2,default=Decimal("0"), validators=[MinValueValidator(Decimal("0")), MaxValueValidator(100)],)
    tardiness_rate = models.DecimalField( max_digits=5,decimal_places=2,default=Decimal("0"), validators=[MinValueValidator(Decimal("0")), MaxValueValidator(100)], )
    consecutive_absent_days = models.PositiveIntegerField(default=0)
    absent_pattern = models.JSONField(default=dict, blank=True, help_text=_("Day/time patterns of absences"))
    risk_level = models.CharField( max_length=20,choices=AttendanceRiskLevelChoices.choices,default=AttendanceRiskLevelChoices.LOW,)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Attendance Pattern")
        verbose_name_plural = _("Attendance Patterns")
        unique_together = [["student", "academic_year", "term"]]
        ordering = ["-attendance_rate"]
        indexes = [
            models.Index(fields=["student", "academic_year", "term"]),
            models.Index(fields=["attendance_rate"]),
            models.Index(fields=["risk_level"]),
        ]

    def __str__(self):
        return f"{self.student.admission_number} - {self.attendance_rate}% ({self.risk_level})"

    def recalculate(self):
        """Recompute all stats from raw records"""
        records = AttendanceRecord.objects.filter(
            student=self.student,
            session__academic_year=self.academic_year,
            session__term=self.term,
        )

        self.total_sessions = records.count()
        self.present_count = records.filter(
            attendance_record_status=AttendanceRecordStatusChoices.PRESENT
        ).count()
        self.late_count = records.filter(
            attendance_record_status=AttendanceRecordStatusChoices.LATE
        ).count()
        self.absent_count = records.filter(
            attendance_record_status=AttendanceRecordStatusChoices.ABSENT
        ).count()
        self.excused_count = records.filter(
            attendance_record_status=AttendanceRecordStatusChoices.EXCUSED
        ).count()

        if self.total_sessions > 0:
            self.attendance_rate = (
                (self.present_count + self.late_count) / self.total_sessions * 100
            )
            self.tardiness_rate = self.late_count / self.total_sessions * 100

        # Consecutive absences (simple last streak)
        sorted_dates = (
            records.filter(attendance_record_status=AttendanceRecordStatusChoices.ABSENT)
            .values_list("session__date", flat=True)
            .order_by("-session__date")
        )
        streak = 0
        for d in sorted_dates:
            if d == timezone.now().date() - timezone.timedelta(days=streak):
                streak += 1
            else:
                break
        self.consecutive_absent_days = streak

        # Risk level
        if self.attendance_rate < 60 or self.consecutive_absent_days >= 5:
            self.risk_level = AttendanceRiskLevelChoices.CRITICAL
        elif self.attendance_rate < 75 or self.consecutive_absent_days >= 3:
            self.risk_level = AttendanceRiskLevelChoices.HIGH
        elif self.attendance_rate < 85:
            self.risk_level = AttendanceRiskLevelChoices.MEDIUM
        else:
            self.risk_level = AttendanceRiskLevelChoices.LOW

        self.save()
