from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.choices.staff import (
    EmploymentTypeChoices,
    StaffAttendanceStatusChoices,
    StaffTypeChoices,
)
from core.utils.phone import validate_kenyan_phone
from .utils import generate_staff_id, validate_id_number


class StaffProfile(models.Model):
    """
    Extended profile for all staff members.
    Linked 1-to-1 with CustomUser.
    """

    user = models.OneToOneField("accounts.CustomUser",on_delete=models.CASCADE,related_name="staff_profile",primary_key=True,help_text=_("Link to the user account for this staff member"),)
    school = models.ForeignKey("schools.School",on_delete=models.CASCADE,related_name="staff_members",help_text=_("School this staff member belongs to"),)

    # Identification
    staff_id = models.CharField( max_length=50,help_text=_("Unique staff ID within the school"),)
    staff_type = models.CharField(max_length=20,choices=StaffTypeChoices.choices,default=StaffTypeChoices.TEACHER,help_text=_("Role of the staff member within the school"),)
    national_id = models.CharField(max_length=20, blank=True, null=True, unique=True)
    tsc_number = models.CharField(max_length=20, blank=True, null=True, unique=True)
    kra_pin = models.CharField(max_length=20, blank=True, null=True)
    nssf_number = models.CharField(max_length=20, blank=True, null=True)
    nhif_number = models.CharField(max_length=20, blank=True, null=True)

    # Employment
    employment_type = models.CharField(max_length=20,choices=EmploymentTypeChoices.choices,default=EmploymentTypeChoices.PERMANENT,)
    job_title = models.CharField(max_length=100)
    department = models.ForeignKey( "schools.Department",on_delete=models.SET_NULL,null=True,blank=True,related_name="staff_members",)
    date_employed = models.DateField(null=True, blank=True)
    employment_terms = models.TextField(blank=True)

    # Academic / Teaching
    qualifications = models.JSONField(default=dict, blank=True)
    subjects_specialized = models.JSONField(default=list, blank=True)
    teaching_experience = models.PositiveIntegerField(default=0)

    # Financial & HR
    bank_details = models.JSONField(default=dict, blank=True)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    allowances = models.JSONField(default=dict, blank=True)
    deductions = models.JSONField(default=dict, blank=True)
    net_salary = models.DecimalField( max_digits=12, decimal_places=2, null=True, blank=True)
    last_promotion = models.DateField(null=True, blank=True)
    next_review = models.DateField(null=True, blank=True)
    # Emergency & Medical
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True,validators=[validate_kenyan_phone],)
    medical_conditions = models.TextField(blank=True)
    allergies = models.TextField(blank=True)
    # Performance (cached)
    performance_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    # Media & Status
    signature = models.ImageField(upload_to="staff/signatures/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    exit_date = models.DateField(null=True, blank=True)
    exit_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Staff Profile")
        verbose_name_plural = _("Staff Profiles")
        ordering = ["staff_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "staff_id"],
                name="unique_staff_id_per_school",
            )
        ]
        indexes = [
            models.Index(fields=["staff_type"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["department"]),
            models.Index(fields=["school", "is_active"]),
        ]

    def __str__(self):
        return f"{self.staff_id} – {self.user.get_full_name()}"


    def clean(self):
        super().clean()
        if self.date_employed and self.date_employed > timezone.now().date():
            raise ValidationError(
                {"date_employed": _("Employment date cannot be in the future.")}
            )
        if self.department and self.school:
            if self.department.school_id != self.school:
                raise ValidationError(
                    {"department": _("Department must belong to the same school.")}
                )
        if self.national_id:
            self.national_id = validate_id_number(self.national_id)
        if self.exit_date and self.date_employed and self.exit_date < self.date_employed:
            raise ValidationError(
                {"exit_date": _("Exit date cannot be before employment date.")}
            )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if not self.staff_id and self.school:
            self.staff_id = generate_staff_id(self.school, self.staff_type)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)

    # Helpers
    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def is_teacher(self) -> bool:
        """Return True if this staff member has a teaching role."""
        return self.staff_type in {
            StaffTypeChoices.TEACHER,
            StaffTypeChoices.HOD,
            StaffTypeChoices.PRINCIPAL,
            StaffTypeChoices.DEPUTY,
        }

    def deactivate(self, exit_date=None, reason: str = ""):
        self.is_active = False
        if exit_date:
            self.exit_date = exit_date
        if reason:
            self.exit_reason = reason
        self.save(update_fields=["is_active", "exit_date", "exit_reason", "updated_at"])

    def activate(self):
        self.is_active = True
        self.exit_date = None
        self.exit_reason = ""
        self.save(update_fields=["is_active", "exit_date", "exit_reason", "updated_at"])


class StaffAttendance(models.Model):
    """Daily attendance record for a staff member."""

    staff = models.ForeignKey(StaffProfile,on_delete=models.CASCADE,related_name="attendance_records",)
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=StaffAttendanceStatusChoices.choices, default=StaffAttendanceStatusChoices.PRESENT,)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL,null=True,blank=True,related_name="recorded_staff_attendance",)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Staff Attendance")
        verbose_name_plural = _("Staff Attendance Records")
        unique_together = [["staff", "date"]]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["staff", "date"]),
            models.Index(fields=["date", "status"]),
        ]

    def __str__(self):
        return f"{self.staff.staff_id} – {self.date} ({self.get_status_display()})"