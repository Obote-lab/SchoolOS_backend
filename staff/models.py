import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from accounts.models import CustomUser


class StaffProfile(models.Model):
    """Core staff profile — identity, role, school linkage"""

    class StaffTypeChoices(models.TextChoices):
        TEACHER = "teacher", _("Teacher")
        PRINCIPAL = "principal", _("Principal")
        DEPUTY_PRINCIPAL = "deputy_principal", _("Deputy Principal")
        HOD = "hod", _("Head of Department")
        ADMIN = "admin", _("Administrative Staff")
        SUPPORT = "support", _("Support Staff (matron, nurse, security, etc.)")

    class EmploymentTypeChoices(models.TextChoices):
        PERMANENT = "permanent", _("Permanent")
        CONTRACT = "contract", _("Contract")
        PROBATION = "probation", _("Probation")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(CustomUser,on_delete=models.CASCADE,related_name="staff_profile",help_text=_("Linked user account"))
    school = models.ForeignKey( "schools.School", on_delete=models.CASCADE,related_name="staff_members",help_text=_("School this staff member belongs to"))
    # staff_id = models.CharField(max_length=50, unique_for_school=True, help_text="Unique staff ID within the school")
    staff_id = models.CharField(max_length=50, help_text=_("Unique staff ID within the school"))
    staff_type = models.CharField( max_length=20,choices=StaffTypeChoices.choices,default=StaffTypeChoices.TEACHER)
    employment_type = models.CharField(max_length=20,choices=EmploymentTypeChoices.choices, default=EmploymentTypeChoices.PERMANENT)
    tsc_number = models.CharField( max_length=50,blank=True,null=True,unique=True,help_text=_("TSC number (for teachers)"))
    id_number = models.CharField(max_length=20,blank=True,null=True,unique=True,help_text=_("National ID number"))
    phone_number = models.CharField(max_length=20,blank=True,validators=[RegexValidator(r"^\+?1?\d{9,15}$")])
    date_employed = models.DateField(default=timezone.now)
    job_title = models.CharField(max_length=200, blank=True)
    department = models.ForeignKey("schools.Department",on_delete=models.SET_NULL, null=True, blank=True,related_name="staff_members")
    # Teaching assignments (M2M)
    subjects_taught = models.ManyToManyField("academics.Subject", blank=True, related_name="teachers", help_text=_("Subjects this teacher is assigned to"))
    classes_assigned = models.ManyToManyField("schools.ClassRoom",blank=True, related_name="assigned_teachers",help_text=_("Classes this teacher teaches or supervises"))

    # Profile media
    def profile_pic_upload_path(self, filename):
        ext = filename.split('.')[-1]
        return f"staff/profile_pics/{self.staff_id}.{ext}"

    profile_pic = models.ImageField(upload_to=profile_pic_upload_path,null=True,blank=True,help_text=_("Staff profile picture"))
    # Employment status
    is_active = models.BooleanField(default=True)
    exit_date = models.DateField(null=True, blank=True)
    exit_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Staff Profile")
        verbose_name_plural = _("Staff Profiles")
        ordering = ["staff_id"]
        unique_together = [["school", "staff_id"]]
        indexes = [
            models.Index(fields=["staff_id"]),
            models.Index(fields=["school", "staff_type"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["tsc_number"]),
            models.Index(fields=["date_employed"]),
        ]

    def __str__(self):
        return f"{self.staff_id} - {self.user.get_full_name()} ({self.get_staff_type_display()})"

    def clean(self):
        super().clean()

        if self.date_employed and self.date_employed > timezone.now().date():
            raise ValidationError({"date_employed": _("Cannot be in the future")})

        if self.exit_date and self.exit_date > timezone.now().date():
            raise ValidationError({"exit_date": _("Cannot be in the future")})

        if self.exit_date and self.date_employed and self.exit_date < self.date_employed:
            raise ValidationError({"exit_date": _("Cannot be before employment date")})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def age(self):
        if not self.user.date_of_birth:
            return None
        today = timezone.now().date()
        return today.year - self.user.date_of_birth.year - (
            (today.month, today.day) < (self.user.date_of_birth.month, self.user.date_of_birth.day)
        )

    @property
    def years_of_service(self):
        if not self.date_employed:
            return None
        end = self.exit_date or timezone.now().date()
        return end.year - self.date_employed.year - ((end.month, end.day) < (self.date_employed.month, self.date_employed.day))

    def deactivate(self, exit_date=None, reason=""):
        self.is_active = False
        self.exit_date = exit_date or timezone.now().date()
        self.exit_reason = reason
        self.save(update_fields=["is_active", "exit_date", "exit_reason"])
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

    def activate(self):
        self.is_active = True
        self.exit_date = None
        self.exit_reason = ""
        self.save(update_fields=["is_active", "exit_date", "exit_reason"])
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])


class StaffAttendance(models.Model):
    """Simplified daily staff attendance tracking"""

    class StatusChoices(models.TextChoices):
        PRESENT = "present", _("Present")
        ABSENT = "absent", _("Absent")
        LATE = "late", _("Late")
        LEAVE = "leave", _("On Leave")

    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE,related_name="attendance_records")
    date = models.DateField(default=timezone.now)
    status = models.CharField( max_length=20, choices=StatusChoices.choices, default=StatusChoices.PRESENT)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(CustomUser,on_delete=models.SET_NULL,null=True,related_name="recorded_attendance",help_text=_("User who recorded this attendance"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Staff Attendance")
        verbose_name_plural = _("Staff Attendance Records")
        unique_together = [["staff", "date"]]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["staff", "date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.staff.staff_id} - {self.date} ({self.get_status_display()})"

    def clean(self):
        super().clean()
        if self.date > timezone.now().date():
            raise ValidationError({"date": _("Cannot be in the future")})