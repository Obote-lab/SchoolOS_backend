import re
from decimal import Decimal
import shortuuid
import uuid
from django.conf import settings
from django.contrib.gis.db.models import PointField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import CustomUser, UserRole
from core.choices.academic import (
    SubjectSpecializationChoices,
    TermNameChoices,
    TermStatusChoices,
)
from core.choices.schools import (
    BoardingStatusChoices,
    OnboardingStatusChoices,
    SchoolCategoryChoices,
    SchoolTypeChoices,
)
from core.utils.phone import validate_kenyan_phone


class School(models.Model):
    """Core school entity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_name = models.CharField(max_length=255, null=True, blank=True)
    school_code = models.CharField(max_length=50, null=True, blank=True, unique=True,help_text="Ministry-assigned school code")
    school_type = models.CharField(max_length=20,choices=SchoolTypeChoices.choices,default=SchoolTypeChoices.SECONDARY,)
    onboarding_status = models.CharField(max_length=20,choices=OnboardingStatusChoices.choices,default=OnboardingStatusChoices.PENDING,)
    onboarding_progress = models.IntegerField( default=0,validators=[MinValueValidator(0), MaxValueValidator(100)],)
    onboarded_by = models.ForeignKey( "accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True, related_name="onboarded_schools",)
    onboarded_date = models.DateTimeField(null=True, blank=True)
    first_principal = models.ForeignKey( "accounts.CustomUser", on_delete=models.SET_NULL,null=True, blank=True,related_name="first_principal_of",)
    trial_start_date = models.DateField(null=True, blank=True)
    trial_end_date = models.DateField(null=True, blank=True)

    subscription_tier = models.CharField( max_length=50, default="FREE_TRIAL",
        choices=[
            ("FREE_TRIAL", "Free Trial"),
            ("BASIC", "Basic"),
            ("STANDARD", "Standard"),
            ("PREMIUM", "Premium"),
            ("ENTERPRISE", "Enterprise"),
        ],
    )

    country_code = models.CharField(max_length=2, default="KE")
    county_code = models.CharField(max_length=3, blank=True)
    system_school_code = models.CharField(max_length=20, unique=True, blank=True)
    school_category = models.CharField(max_length=20,choices=SchoolCategoryChoices.choices,default=SchoolCategoryChoices.PUBLIC,)
    county = models.CharField(max_length=100, null=True, blank=True)
    sub_county = models.CharField(max_length=100, null=True, blank=True)
    ward = models.CharField(max_length=100, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    gps_coordinates = PointField(null=True, blank=True)
    phone = models.CharField( max_length=20, null=True, blank=True,validators=[validate_kenyan_phone], )
    email = models.EmailField(null=True, blank=True)
    # Leadership
    principal = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True, related_name="principal_of",)
    deputy_academic = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL, null=True, blank=True, related_name="deputy_academic_of",)
    deputy_admin = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL,null=True, blank=True,related_name="deputy_admin_of",)
    boarding_status = models.CharField(max_length=20,choices=BoardingStatusChoices.choices,default=BoardingStatusChoices.DAY,)
    capacity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    current_enrollment = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    establishment_year = models.IntegerField( null=True, blank=True, validators=[MinValueValidator(1900), MaxValueValidator(timezone.now().year)],)
    # Government codes
    registration_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    nemis_code = models.CharField(max_length=100, unique=True, null=True, blank=True)
    tsc_code = models.CharField(max_length=100, null=True, blank=True)
    knec_center_number = models.CharField(max_length=100, null=True, blank=True)
    bank_account = models.JSONField(default=dict, null=True, blank=True)
    school_motto = models.TextField(blank=True, null=True)
    vision = models.TextField(blank=True, null=True)
    mission = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to="schools/logos/", null=True, blank=True)
    banner = models.ImageField(upload_to="schools/banners/", null=True, blank=True)
    registration_date = models.DateField(null=True, blank=True)
    current_term = models.ForeignKey( "Term", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    current_academic_year = models.ForeignKey( "AcademicYear", null=True, blank=True, on_delete=models.SET_NULL, related_name="+" )

    last_modified_by = models.ForeignKey("accounts.CustomUser", null=True, blank=True,on_delete=models.SET_NULL,related_name="modified_schools",)
    last_modified_at = models.DateTimeField(auto_now=True)

    cdf_eligible = models.BooleanField(default=False)
    bursary_eligible_count = models.IntegerField(default=0)
    school_settings = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL, null=True,related_name="created_schools",)

    class Meta:
        verbose_name = "School"
        verbose_name_plural = "Schools"
        ordering = ["school_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["principal"],
                condition=Q(principal__isnull=False),
                name="unique_principal_assignment",
            ),
            models.UniqueConstraint(
                fields=["school_code"],
                condition=Q(school_code__isnull=False),
                name="unique_school_code",
            ),
        ]
        indexes = [
            models.Index(fields=["school_code"]),
            models.Index(fields=["nemis_code"]),
            models.Index(fields=["county", "sub_county"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["school_type", "school_category"]),
            models.Index(fields=["onboarding_status", "onboarding_progress"]),
            models.Index(fields=["trial_end_date", "subscription_tier"]),
            models.Index(fields=["current_academic_year", "current_term"]),
        ]

    def __str__(self):
        return f"{self.school_name or 'Unnamed'} ({self.school_code or self.system_school_code})"

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)

        if not self.system_school_code:
            country = self.country_code or "KE"
            self.system_school_code = (
                f"SCH-{country}-{shortuuid.ShortUUID().random(length=6).upper()}"
            )
            while School.objects.filter(system_school_code=self.system_school_code).exists():
                self.system_school_code = (
                    f"SCH-{country}-{shortuuid.ShortUUID().random(length=6).upper()}"
                )

        progress_map = {
            OnboardingStatusChoices.PENDING: 0,
            OnboardingStatusChoices.PRINCIPAL_CREATED: 30,
            OnboardingStatusChoices.STRUCTURES_SETUP: 70,
            OnboardingStatusChoices.ACTIVE: 100,
        }
        self.onboarding_progress = progress_map.get(self.onboarding_status, self.onboarding_progress)

        if validate:
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.principal:
            has_role = UserRole.objects.filter(
                user=self.principal,
                school=self,
                role__name__iexact="Principal",
                is_active=True,
            ).exists()
            if not has_role:
                raise ValidationError({"principal": "Assigned user must have the Principal role."})

        for field_name, deputy in [("deputy_academic", self.deputy_academic), ("deputy_admin", self.deputy_admin)]:
            if deputy:
                allowed = UserRole.objects.filter(
                    user=deputy,
                    school=self,
                    role__name__in=["Principal", "Deputy Principal"],
                    is_active=True,
                ).exists()
                if not allowed:
                    raise ValidationError({field_name: "Deputy must have Principal or Deputy Principal role."})

        if self.current_enrollment > self.capacity:
            raise ValidationError(
                f"Enrollment ({self.current_enrollment}) exceeds capacity ({self.capacity})"
            )

    # Helpers
    @property
    def enrollment_percentage(self):
        if self.capacity == 0:
            return 0
        return round((self.current_enrollment / self.capacity) * 100, 2)

    @property
    def vacancy_count(self):
        return max(0, self.capacity - self.current_enrollment)

    def update_enrollment(self, change: int):
        new_enrollment = self.current_enrollment + change
        if new_enrollment < 0:
            raise ValidationError("Enrollment cannot be negative")
        if new_enrollment > self.capacity:
            raise ValidationError(f"Enrollment cannot exceed capacity of {self.capacity}")
        self.current_enrollment = new_enrollment
        self.save(update_fields=["current_enrollment"])

    def get_staff_by_role(self, role_name: str):
        return UserRole.objects.filter(school=self, role__name__iexact=role_name, is_active=True).select_related("user", "role")

    def get_deputies(self):
        deputies = []
        if self.deputy_academic:
            deputies.append(self.deputy_academic)
        if self.deputy_admin:
            deputies.append(self.deputy_admin)
        return deputies

    def get_hods(self):
        return CustomUser.objects.filter(
            user_roles__school=self,
            user_roles__role__name__iexact="Head of Department",
            user_roles__is_active=True,
        ).distinct()

    def get_teachers(self):
        return CustomUser.objects.filter(
            user_roles__school=self,
            user_roles__role__name__iexact="Teacher",
            user_roles__is_active=True,
        ).distinct()

    def get_students_count(self):
        return CustomUser.objects.filter(
            user_roles__school=self,
            user_roles__role__name__iexact="Student",
            user_roles__is_active=True,
        ).count()

    def can_user_manage_school(self, user) -> bool:
        if not user:
            return False
        if user.is_superuser or user == self.principal:
            return True
        if user in self.get_deputies():
            return True
        return UserRole.objects.filter(
            user=user,
            school=self,
            role__permissions_tier__lte=5,
            is_active=True,
        ).exists()

    @property
    def is_in_trial(self) -> bool:
        if not self.trial_start_date or not self.trial_end_date:
            return False
        today = timezone.now().date()
        return self.trial_start_date <= today <= self.trial_end_date

    @property
    def trial_days_remaining(self) -> int:
        if not self.is_in_trial:
            return 0
        return (self.trial_end_date - timezone.now().date()).days

    @property
    def needs_onboarding_attention(self) -> bool:
        if self.onboarding_status in [
            OnboardingStatusChoices.PENDING,
            OnboardingStatusChoices.PRINCIPAL_CREATED,
        ] and self.created_at < timezone.now() - timezone.timedelta(days=3):
            return True
        return False

    @property
    def has_principal(self) -> bool:
        return self.principal is not None


class SchoolLeadership(models.Model):
    """Flexible leadership assignments."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="leadership_assignments")
    user_role = models.ForeignKey("accounts.UserRole", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    position_title = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = [["school", "user_role"]]
        ordering = ["-is_active", "position_title"]

    def __str__(self):
        return f"{self.user_role.user.get_full_name()} - {self.position_title or self.user_role.role.name}"


class AcademicYear(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_years")
    year = models.CharField(max_length=9, help_text="Format: YYYY-YYYY")
    label = models.CharField(max_length=100, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    terms_count = models.IntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(4)])
    holidays = models.JSONField(default=list)
    important_dates = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey( settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_academic_years",)

    class Meta:
        verbose_name = "Academic Year"
        verbose_name_plural = "Academic Years"
        ordering = ["-start_date"]
        unique_together = [["school", "year"]]
        indexes = [
            models.Index(fields=["year"]),
            models.Index(fields=["is_current"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.year} ({'Current' if self.is_current else 'Past'})"

    def clean(self):
        super().clean()
        if len(self.year) != 9 or "-" not in self.year:
            raise ValidationError({"year": "Year must be in format YYYY-YYYY (e.g. 2025-2026)"})
        if self.start_date >= self.end_date:
            raise ValidationError({"start_date": "Start date must be before end date"})

        expected = f"{self.start_date.year}-{self.end_date.year}"
        if self.year != expected:
            raise ValidationError({"year": f"Year should be {expected} based on the dates"})

        if self.is_current:
            qs = AcademicYear.objects.filter(school=self.school, is_current=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({"is_current": "Only one academic year can be current per school"})

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if not self.label:
            self.label = f"{self.year} Academic Year"
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_active(self) -> bool:
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date


class Term(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="terms")
    name = models.CharField(max_length=20, choices=TermNameChoices.choices, default=TermNameChoices.TERM_1)
    sequence = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])
    start_date = models.DateField()
    end_date = models.DateField()
    midterm_break_start = models.DateField(null=True, blank=True)
    midterm_break_end = models.DateField(null=True, blank=True)
    fee_due_date = models.DateField(null=True, blank=True)
    exam_start_date = models.DateField(null=True, blank=True)
    exam_end_date = models.DateField(null=True, blank=True)
    term_status = models.CharField(max_length=20, choices=TermStatusChoices.choices,default=TermStatusChoices.UPCOMING,)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Term"
        verbose_name_plural = "Terms"
        ordering = ["academic_year", "sequence"]
        unique_together = [["academic_year", "sequence"], ["academic_year", "name"]]
        indexes = [
            models.Index(fields=["academic_year", "sequence"]),
            models.Index(fields=["term_status"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.academic_year.year} - {self.get_name_display()}"

    def clean(self):
        super().clean()
        if self.start_date >= self.end_date:
            raise ValidationError({"start_date": "Start date must be before end date"})

        if self.start_date < self.academic_year.start_date or self.end_date > self.academic_year.end_date:
            raise ValidationError("Term must fall within the academic year dates")

        if self.midterm_break_start and self.midterm_break_end:
            if self.midterm_break_start >= self.midterm_break_end:
                raise ValidationError({"midterm_break_start": "Midterm break start must be before end"})
            if self.midterm_break_start < self.start_date or self.midterm_break_end > self.end_date:
                raise ValidationError("Midterm break must be within the term dates")

        if self.exam_start_date and self.exam_end_date:
            if self.exam_start_date >= self.exam_end_date:
                raise ValidationError({"exam_start_date": "Exam start must be before end"})
            if self.exam_start_date < self.start_date or self.exam_end_date > self.end_date:
                raise ValidationError("Exam dates must be within the term dates")

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        today = timezone.now().date()
        if today < self.start_date:
            self.term_status = TermStatusChoices.UPCOMING
        elif self.start_date <= today <= self.end_date:
            self.term_status = TermStatusChoices.ACTIVE
        else:
            self.term_status = TermStatusChoices.COMPLETED
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)

    @property
    def duration_days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    @property
    def days_remaining(self) -> int:
        today = timezone.now().date()
        if today < self.start_date:
            return self.duration_days
        if today > self.end_date:
            return 0
        return (self.end_date - today).days

    @property
    def is_current(self) -> bool:
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date


class ClassRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="classrooms")
    level = models.CharField(max_length=50, help_text='e.g. "Form 2", "Grade 5"')
    stream = models.CharField(max_length=50, help_text='e.g. "East", "A"')
    classroom_name = models.CharField(max_length=100, blank=True)

    class_teacher = models.ForeignKey( settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="class_teacher_of",)
    assistant_teacher = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL, null=True, blank=True, related_name="assistant_teacher_of",)

    capacity = models.IntegerField(default=40, validators=[MinValueValidator(1), MaxValueValidator(100)])
    current_enrollment = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    room_number = models.CharField(max_length=50, blank=True)
    building = models.CharField(max_length=100, blank=True)
    floor = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    has_smart_board = models.BooleanField(default=False)
    has_projector = models.BooleanField(default=False)

    subject_specialization = models.CharField(max_length=20, choices=SubjectSpecializationChoices.choices,null=True, blank=True,)
    year_group = models.IntegerField(null=True, blank=True)
    average_performance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Classroom"
        verbose_name_plural = "Classrooms"
        ordering = ["school", "level", "stream"]
        unique_together = [["school", "level", "stream"]]
        indexes = [
            models.Index(fields=["school", "level"]),
            models.Index(fields=["class_teacher"]),
            models.Index(fields=["subject_specialization"]),
        ]

    def __str__(self):
        return f"{self.classroom_name or f'{self.level} {self.stream}'} - {self.school.school_name}"

    def clean(self):
        super().clean()
        if not self.classroom_name:
            self.classroom_name = f"{self.level} {self.stream}"
        if self.current_enrollment > self.capacity:
            raise ValidationError({
                "current_enrollment": f"Current count ({self.current_enrollment}) cannot exceed capacity ({self.capacity})"
            })

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)

    @property
    def vacancy_count(self) -> int:
        return max(0, self.capacity - self.current_enrollment)

    @property
    def occupancy_percentage(self) -> float:
        if self.capacity == 0:
            return 0
        return round((self.current_enrollment / self.capacity) * 100, 2)

    def update_student_count(self, change: int):
        new_count = self.current_enrollment + change
        if new_count < 0:
            raise ValidationError("Student count cannot be negative")
        if new_count > self.capacity:
            raise ValidationError(f"Student count cannot exceed capacity of {self.capacity}")
        self.current_enrollment = new_count
        self.save(update_fields=["current_enrollment"])


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="departments")
    department_name = models.CharField(max_length=100)
    department_code = models.CharField(max_length=20)

    head_of_department = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name="headed_departments",)
    assistant_hod = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,null=True, blank=True, related_name="assistant_departments",)

    department_type = models.CharField(  max_length=30, choices=[("core", "Core"), ("elective", "Elective")], default="core", )
    description = models.TextField(blank=True)
    color_code = models.CharField(max_length=7, default="#3B82F6")
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    member_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ["school", "department_name"]
        unique_together = [["school", "department_code"], ["school", "department_name"]]
        indexes = [
            models.Index(fields=["school", "department_code"]),
            models.Index(fields=["head_of_department"]),
        ]

    def __str__(self):
        return f"{self.department_name} - {self.school.school_name}"

    def clean(self):
        super().clean()
        if not re.match(r"^#[0-9A-Fa-f]{6}$", self.color_code):
            raise ValidationError({"color_code": "Color code must be a valid hex value (e.g. #3B82F6)"})

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)