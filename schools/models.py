import re,uuid
from decimal import Decimal
from django.conf import settings
from django.contrib.gis.db.models import PointField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from django.db.models import UniqueConstraint
from django.db.models import Q
from accounts.models import UserRole


class School(models.Model):
    """School model - core entity for the system"""

    class SchoolTypeChoices(models.TextChoices):
        PRIMARY = "primary", "Primary School"
        SECONDARY = "secondary", "Secondary School"
        MIXED = "mixed", "Mixed (Primary & Secondary)"
        SPECIAL_NEEDS = "special_needs", "Special Needs School"
        TVET = "tvet", "TVET Institute"

    class SchoolCategoryChoices(models.TextChoices):
        PUBLIC = "public", "Public School"
        PRIVATE = "private", "Private School"
        MISSION = "mission", "Mission School"
        INTERNATIONAL = "international", "International School"
        COMMUNITY = "community", "Community School"

    class BoardingStatusChoices(models.TextChoices):
        DAY = "day", "Day School"
        BOARDING = "boarding", "Boarding School"
        MIXED = "mixed", "Day & Boarding"

    class OnboardingStatusChoices(models.TextChoices):
        PENDING = 'pending', 'Pending Setup'
        PRINCIPAL_CREATED = 'principal_created', 'Principal Created'
        STRUCTURES_SETUP = 'structures_setup', 'Basic Structures Setup'
        ACTIVE = 'active', 'Active & Operational'
        SUSPENDED = 'suspended', 'Suspended'
        ARCHIVED = 'archived', 'Archived'


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_name = models.CharField( max_length=255, null=True, blank=True, help_text="Official school name")
    school_code = models.CharField(max_length=50,null=True,blank=True, unique=True, help_text="Ministry-assigned school code (unique)",)
    type = models.CharField(max_length=20,choices=SchoolTypeChoices.choices, default=SchoolTypeChoices.SECONDARY,help_text="Type of school", )
    onboarding_status = models.CharField( max_length=20,choices=OnboardingStatusChoices.choices, default=OnboardingStatusChoices.PENDING,help_text="School onboarding progress status")
    onboarding_progress = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Onboarding completion percentage (0-100)")
    onboarded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,null=True, blank=True,related_name='onboarded_schools', help_text="System/Root admin who initiated onboarding" )
    onboarded_date = models.DateTimeField(null=True, blank=True,help_text="Date when school was fully onboarded")
    first_principal = models.ForeignKey( settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='first_principal_of',help_text="Initial principal assigned during onboarding")
    trial_start_date = models.DateField(null=True,blank=True,help_text="Start date of free trial period") 
    trial_end_date = models.DateField( null=True, blank=True, help_text="End date of free trial period")
    subscription_tier = models.CharField(max_length=50,default='FREE_TRIAL',
        choices=[
            ('FREE_TRIAL', 'Free Trial'),
            ('BASIC', 'Basic'),
            ('STANDARD', 'Standard'),
            ('PREMIUM', 'Premium'),
            ('ENTERPRISE', 'Enterprise')
        ],
        help_text="Current subscription tier"
    )
    country_code = models.CharField(max_length=2, default="KE")
    county_code = models.CharField(max_length=3)
    system_school_code = models.CharField(max_length=10, unique=True)
    school_category = models.CharField(max_length=20,choices=SchoolCategoryChoices.choices, default=SchoolCategoryChoices.PUBLIC,help_text="School category",)
    county = models.CharField(max_length=100, null=True, blank=True, help_text="County")
    sub_county = models.CharField( max_length=100, null=True, blank=True, help_text="Sub-county" )
    ward = models.CharField(max_length=100, null=True, blank=True, help_text="Ward")
    address = models.TextField(help_text="Physical address", null=True, blank=True)
    gps_coordinates = PointField(  null=True, blank=True, help_text="GPS coordinates (latitude, longitude)" )
    phone = models.CharField(max_length=20, null=True,blank=True, validators=[RegexValidator(r"^\+?1?\d{9,15}$")],help_text="School phone number",)
    email = models.EmailField(null=True, blank=True, help_text="School email address")
    # Leadership
    principal = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,null=True,blank=True,related_name="principal_of", limit_choices_to={"user_type": "PRN"},help_text="School principal")
    deputy_academic = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL, null=True,blank=True,related_name="deputy_academic_of",help_text="Deputy principal (academic)",limit_choices_to={"user_type": "DEP"},)
    deputy_admin = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL, null=True,blank=True, related_name="deputy_admin_of", help_text="Deputy principal (administration)", limit_choices_to={"user_type": "DEP"},)
    # School Details
    boarding_status = models.CharField( max_length=20,choices=BoardingStatusChoices.choices,default=BoardingStatusChoices.DAY,help_text="Boarding status", )
    capacity = models.IntegerField(default=0, validators=[MinValueValidator(Decimal("0"))], help_text="Maximum student capacity",)
    current_enrollment = models.IntegerField( default=0, validators=[MinValueValidator(Decimal("0"))], help_text="Current number of enrolled students",)
    establishment_year = models.IntegerField( null=True, blank=True,
        validators=[
            MinValueValidator(Decimal("1900")),
            MaxValueValidator(timezone.now().year),
        ],help_text="Year school was established",
    )
    # Government Registration
    registration_number = models.CharField( max_length=100, unique=True, null=True, blank=True, help_text="Government registration number",)
    nemis_code = models.CharField(max_length=100, unique=True, null=True, blank=True, help_text="NEMIS code")
    tsc_code = models.CharField(max_length=100,null=True, blank=True, help_text="Teachers Service Commission code",)
    knec_center_number = models.CharField(max_length=100,null=True,blank=True,help_text="KNEC examination center number",)
    bank_account = models.JSONField( default=dict, null=True,blank=True,help_text="Bank account details in JSON format",)
    # School Identity
    school_motto = models.TextField(blank=True, null=True, help_text="School motto")
    vision = models.TextField(blank=True, null=True, help_text="School vision")
    mission = models.TextField(blank=True, null=True, help_text="School mission")
    logo = models.ImageField(upload_to="schools/logos/", null=True, blank=True, help_text="School logo")
    banner = models.ImageField( upload_to="schools/banners/", null=True, blank=True, help_text="School banner" )
    # Settings and Status
    registration_date       = models.DateField(null=True, blank=True, help_text="Date school was registered")
    current_term            = models.ForeignKey('Term', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    current_academic_year   = models.ForeignKey('AcademicYear', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    # For audit trail (blueprint p.23–24)
    last_modified_by        = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='modified_schools')
    last_modified_at        = models.DateTimeField(auto_now=True)
    cdf_eligible            = models.BooleanField(default=False, help_text="Eligible for CDF funding")
    bursary_eligible_count  = models.IntegerField(default=0, help_text="Number of bursary-eligible students")
    school_settings = models.JSONField(default=dict, help_text="School-specific configuration settings")
    is_active = models.BooleanField(default=True, help_text="Is school active?")
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True, related_name="created_schools", help_text="User who created this school record", )

    class Meta:
        verbose_name = "School"
        verbose_name_plural = "Schools"
        ordering = ["school_name"]
        indexes = [
            models.Index(fields=["school_code"]),
            models.Index(fields=["nemis_code"]),
            models.Index(fields=["county", "sub_county"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=['county', 'sub_county', 'ward']),
            models.Index(fields=['type', 'school_category']),
            models.Index(fields=['current_enrollment', 'capacity']),
            models.Index(fields=['onboarding_status', 'onboarding_progress']),
            models.Index(fields=['onboarded_date']),
            models.Index(fields=['trial_end_date', 'subscription_tier']),
            models.Index(fields=['created_by', 'onboarded_by']),
            models.Index(fields=['nemis_code', 'tsc_code', 'knec_center_number']),
            models.Index(fields=['current_academic_year', 'current_term']),
        ]

    def __str__(self):
        return f"{self.school_name} ({self.school_code})"

    def save(self, *args, **kwargs):
        if not self.pk and not self.system_school_code:
            # Generate unique code: SCH-YYYY-XXXX (random 4 chars)
            year = timezone.now().year
            random_part = uuid.uuid4().hex[:4].upper()
            self.system_school_code = f"SCH-{year}-{random_part}"

            # Ensure uniqueness (rare collision)
            while School.objects.filter(system_school_code=self.system_school_code).exists():
                random_part = uuid.uuid4().hex[:4].upper()
                self.system_school_code = f"SCH-{year}-{random_part}"

        # Auto-update onboarding progress
        if self.onboarding_status == self.OnboardingStatusChoices.PENDING:
            self.onboarding_progress = 0
        elif self.onboarding_status == self.OnboardingStatusChoices.PRINCIPAL_CREATED:
            self.onboarding_progress = 30
        elif self.onboarding_status == self.OnboardingStatusChoices.STRUCTURES_SETUP:
            self.onboarding_progress = 70
        elif self.onboarding_status == self.OnboardingStatusChoices.ACTIVE:
            self.onboarding_progress = 100

        super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        # Principal must be PRN type
        if self.principal and self.principal.user_type != "PRN":
            raise ValidationError({"principal": "Principal must have user_type 'PRN'"})

        # Deputies must be PRN or DEP
        for deputy in [self.deputy_academic, self.deputy_admin]:
            if deputy and deputy.user_type not in ["PRN", "DEP"]:
                raise ValidationError({"deputy": "Deputy must have user_type 'PRN' or 'DEP'"})

        # Enrollment check
        if self.current_enrollment > self.capacity:
            raise ValidationError(
                f"Enrollment ({self.current_enrollment}) exceeds capacity ({self.capacity})"
            )

    @property
    def enrollment_percentage(self):
        """Calculate enrollment percentage"""
        if self.capacity == 0:
            return 0
        return (self.current_enrollment / self.capacity) * 100

    @property
    def vacancy_count(self):
        """Calculate available vacancies"""
        return max(0, self.capacity - self.current_enrollment)

    def update_enrollment(self, change):
        """Update enrollment count with validation"""
        new_enrollment = self.current_enrollment + change
        if new_enrollment < 0:
            raise ValidationError("Enrollment cannot be negative")
        if new_enrollment > self.capacity:
            raise ValidationError(
                f"Enrollment cannot exceed capacity of {self.capacity}"
            )

        self.current_enrollment = new_enrollment
        self.save(update_fields=["current_enrollment"])

    def get_staff_by_role(self, role_name):
        """Get all staff with a specific role in this school"""
        from accounts.models import UserRole

        return UserRole.objects.filter(
            school=self, role__name=role_name, is_active=True
        ).select_related("user")

    def get_principal(self):
        """Get the principal user"""
        return self.principal

    def get_deputies(self):
        """Get all deputy principals"""
        deputies = []
        if self.deputy_academic:
            deputies.append(self.deputy_academic)
        if self.deputy_admin:
            deputies.append(self.deputy_admin)
        return deputies

    def get_hods(self):
        """Get all Heads of Department"""
        from accounts.models import CustomUser

        return CustomUser.objects.filter(school=self, user_type="HOD", is_active=True)

    def get_teachers(self):
        """Get all teachers"""
        from accounts.models import CustomUser

        return CustomUser.objects.filter(school=self, user_type="TCH", is_active=True)

    def get_students(self):
        """Get all students"""
        from accounts.models import CustomUser

        return CustomUser.objects.filter(
            school=self, user_type="STU", is_active=True
        ).count()

    def can_user_manage_school(self, user):
        """
        Check if a user can manage this school
        Based on hierarchy: Principal > Deputies > HODs > Teachers
        """
        if not user.school == self:
            return False
        if user.is_superuser:
            return True
        if user == self.principal:
            return True
        if user in [self.deputy_academic, self.deputy_admin]:
            return True
        admin_roles = ["Principal", "Deputy Principal", "ICT Admin"]
        return UserRole.objects.filter(
            user=user, school=self, role__name__in=admin_roles, is_active=True
        ).exists()
    

    @property
    def is_in_trial(self):
        if not self.trial_start_date or not self.trial_end_date:
            return False
        today = timezone.now().date()
        return self.trial_start_date <= today <= self.trial_end_date

    @property
    def trial_days_remaining(self):
        """Calculate days remaining in trial"""
        if not self.is_in_trial:
            return 0
        today = timezone.now().date()
        return (self.trial_end_date - today).days

    @property
    def needs_onboarding_attention(self):
        """Check if school needs onboarding follow-up"""
        if self.onboarding_status in [
            self.OnboardingStatusChoices.PENDING,
            self.OnboardingStatusChoices.PRINCIPAL_CREATED
        ] and self.created_at < timezone.now() - timezone.timedelta(days=3):
            return True
        return False


class AcademicYear(models.Model):
    """Academic year model"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey( School,on_delete=models.CASCADE,related_name="academic_years",help_text="School this academic year belongs to",)
    year = models.CharField(max_length=9, help_text="Academic year in format YYYY-YYYY")
    label = models.CharField( max_length=100, help_text='Display label (e.g., "2023 Academic Year")')
    start_date = models.DateField(help_text="Start date of academic year")
    end_date = models.DateField(help_text="End date of academic year")
    is_current = models.BooleanField( default=False, help_text="Is this the current academic year?")
    terms_count = models.IntegerField( default=3, validators=[MinValueValidator(Decimal("1")), MaxValueValidator(Decimal("4"))], help_text="Number of terms in this academic year",)
    holidays = models.JSONField(default=list, help_text="List of holiday periods")
    important_dates = models.JSONField( default=dict, help_text="Important dates (opening, closing, exams, etc.)")
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,null=True,related_name="created_academic_years",help_text="User who created this academic year",)
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
        """Validate academic year dates"""
        super().clean()
        if len(self.year) != 9 or "-" not in self.year:
            raise ValidationError(
                {"year": "Year must be in format YYYY-YYYY (e.g., 2023-2024)"}
            )
        if self.start_date >= self.end_date:
            raise ValidationError({"start_date": "Start date must be before end date"})

        start_year = self.start_date.year
        end_year = self.end_date.year
        expected_year_format = f"{start_year}-{end_year}"

        if self.year != expected_year_format:
            raise ValidationError(
                {"year": f"Year should be {expected_year_format} based on dates"}
            )
        if self.is_current:
            # current_years = AcademicYear.objects.filter(is_current=True)
            current_years = AcademicYear.objects.filter(
                school=self.school, is_current=True
            )
            if self.pk:
                current_years = current_years.exclude(pk=self.pk)
            if current_years.exists():
                raise ValidationError(
                    {"is_current": "Only one academic year can be marked as current"}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.label:
            self.label = f"{self.year} Academic Year"

        super().save(*args, **kwargs)

    @property
    def is_active(self):
        """Check if academic year is currently active"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date


class Term(models.Model):
    """Term model within an academic year"""

    class TermNameChoices(models.TextChoices):
        TERM_1 = "term_1", "Term 1"
        TERM_2 = "term_2", "Term 2"
        TERM_3 = "term_3", "Term 3"
        TERM_4 = "term_4", "Term 4"  # For some schools

    class TermStatusChoices(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.ForeignKey( AcademicYear, on_delete=models.CASCADE,related_name="terms",help_text="Academic year this term belongs to",)
    name = models.CharField( max_length=20,choices=TermNameChoices.choices, default=TermNameChoices.TERM_1, help_text="Term name",)
    sequence = models.IntegerField(validators=[MinValueValidator(Decimal("1")), MaxValueValidator(Decimal("4"))],help_text="Term sequence (1, 2, 3, 4)", )
    start_date = models.DateField(help_text="Term start date")
    end_date = models.DateField(help_text="Term end date")
    midterm_break_start = models.DateField( null=True, blank=True, help_text="Midterm break start date")
    midterm_break_end = models.DateField( null=True, blank=True, help_text="Midterm break end date" )
    fee_due_date = models.DateField(null=True, blank=True, help_text="Fee due date")
    exam_start_date = models.DateField( null=True, blank=True, help_text="Examination start date")
    exam_end_date = models.DateField(null=True, blank=True, help_text="Examination end date")
    term_status = models.CharField( max_length=20, choices=TermStatusChoices.choices, default=TermStatusChoices.UPCOMING,help_text="Term status", )
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
        """Validate term data"""
        super().clean()

        if self.start_date >= self.end_date:
            raise ValidationError({"start_date": "Start date must be before end date"})

        if (
            self.start_date < self.academic_year.start_date
            or self.end_date > self.academic_year.end_date
        ):
            raise ValidationError(
                {"start_date": "Term must be within the academic year dates"}
            )

        # Validate midterm break dates
        if self.midterm_break_start and self.midterm_break_end:
            if self.midterm_break_start >= self.midterm_break_end:
                raise ValidationError(
                    {"midterm_break_start": "Midterm break start must be before end"}
                )
            if (
                self.midterm_break_start < self.start_date
                or self.midterm_break_end > self.end_date
            ):
                raise ValidationError(
                    {"midterm_break_start": "Midterm break must be within term dates"}
                )

        # Validate exam dates
        if self.exam_start_date and self.exam_end_date:
            if self.exam_start_date >= self.exam_end_date:
                raise ValidationError(
                    {"exam_start_date": "Exam start must be before end"}
                )
            if (
                self.exam_start_date < self.start_date
                or self.exam_end_date > self.end_date
            ):
                raise ValidationError(
                    {"exam_start_date": "Exam dates must be within term dates"}
                )

    def save(self, *args, **kwargs):
        self.full_clean()

        # Auto-update status based on dates
        today = timezone.now().date()
        if today < self.start_date:
            self.term_status = self.TermStatusChoices.UPCOMING
        elif self.start_date <= today <= self.end_date:
            self.term_status = self.TermStatusChoices.ACTIVE
        else:
            self.term_status = self.TermStatusChoices.COMPLETED

        super().save(*args, **kwargs)

    @property
    def duration_days(self):
        """Calculate term duration in days"""
        return (self.end_date - self.start_date).days + 1

    @property
    def days_remaining(self):
        """Calculate days remaining in term"""
        today = timezone.now().date()
        if today < self.start_date:
            return self.duration_days
        elif today > self.end_date:
            return 0
        else:
            return (self.end_date - today).days

    @property
    def is_current(self):
        """Check if this is the current term"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date


class ClassRoom(models.Model):
    """Classroom model for class/stream management"""

    class SubjectSpecializationChoices(models.TextChoices):
        SCIENCE = "science", "Science"
        ARTS = "arts", "Arts"
        GENERAL = "general", "General"
        TECHNICAL = "technical", "Technical"
        BUSINESS = "business", "Business"
        AGRICULTURE = "agriculture", "Agriculture"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey( School, on_delete=models.CASCADE,related_name="classrooms",help_text="School this classroom belongs to",)
    # Class identification
    level = models.CharField( max_length=50, help_text='Class level (e.g., "Form 2", "Grade 5", "Standard 8")' )
    stream = models.CharField( max_length=50, help_text='Stream name (e.g., "East", "North", "Red", "A")')
    classroom_name = models.CharField( max_length=100, blank=True, help_text='Classroom full name (e.g., "Form 2 East")', )
    # Teaching staff
    class_teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="class_teacher_of", help_text="Class teacher",)
    assistant_teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,null=True,blank=True,related_name="assistant_teacher_of",help_text="Assistant class teacher",)
    # Capacity and enrollment
    capacity = models.IntegerField(default=40,validators=[MinValueValidator(Decimal("1")), MaxValueValidator(Decimal("100"))],help_text="Maximum student capacity",)
    current_enrollment = models.IntegerField(default=0,validators=[MinValueValidator(Decimal("0"))],help_text="Current number of students", )
    room_number = models.CharField( max_length=50, blank=True, help_text="Room number/identifier" )
    building = models.CharField(max_length=100, blank=True, help_text="Building name")
    floor = models.IntegerField( null=True, blank=True, validators=[MinValueValidator(Decimal("0"))], help_text="Floor number",)
    has_smart_board = models.BooleanField(default=False, help_text="Has smart board?")
    has_projector = models.BooleanField(default=False, help_text="Has projector?")
    # Academic specialization (for secondary schools)
    subject_specialization = models.CharField( max_length=20, choices=SubjectSpecializationChoices.choices, null=True,blank=True, help_text="Subject specialization (for secondary schools)",)
    # Year group tracking
    year_group = models.IntegerField( null=True, blank=True, help_text="Year group (e.g., 2025 for KCSE candidates)" )
    average_performance = models.DecimalField( max_digits=5, decimal_places=2, null=True, blank=True, help_text="Average class performance (%)", )
    attendance_rate = models.DecimalField( max_digits=5,  decimal_places=2, null=True, blank=True, help_text="Average attendance rate (%)",)
    # Metadata
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
            models.Index(fields=['school', 'class_teacher', 'assistant_teacher']),
            models.Index(fields=['subject_specialization', 'level']),
        ]

    def __str__(self):
        return f"{self.classroom_name} - {self.school.school_name}"

    def clean(self):
        """Validate classroom data"""
        super().clean()

        # Auto-generate name if not provided
        if not self.classroom_name:
            self.classroom_name = f"{self.level} {self.stream}"

        # Validate current count doesn't exceed capacity
        if self.current_enrollment > self.capacity:
            raise ValidationError(
                {
                    "current_enrollment": f"Current count ({self.current_enrollment}) cannot exceed capacity ({self.capacity})"
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def vacancy_count(self):
        """Calculate available vacancies"""
        return max(0, self.capacity - self.current_enrollment)

    @property
    def occupancy_percentage(self):
        """Calculate occupancy percentage"""
        if self.capacity == 0:
            return 0
        return (self.current_enrollment / self.capacity) * 100

    def update_student_count(self, change):
        """Update student count with validation"""
        new_count = self.current_enrollment + change
        if new_count < 0:
            raise ValidationError("Student count cannot be negative")
        if new_count > self.capacity:
            raise ValidationError(
                f"Student count cannot exceed capacity of {self.capacity}"
            )

        self.current_enrollment = new_count
        self.save(update_fields=["current_enrollment"])


class Department(models.Model):
    """Department model for subject grouping (mainly secondary schools)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey( School, on_delete=models.CASCADE, related_name="departments", help_text="School this department belongs to",)
    department_name = models.CharField(max_length=100, help_text="Department name")
    department_code = models.CharField( max_length=20, help_text='Department code (e.g., "MATH", "LANG")' )
    head_of_department = models.ForeignKey( settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="headed_departments", help_text="Head of Department", )
    assistant_hod = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True, related_name="assistant_departments",help_text="Assistant Head of Department",)
    # Add for better RBAC/department scoping
    department_type         = models.CharField(max_length=30, choices=[('core','Core'),('elective','Elective')], default='core')
    description = models.TextField(blank=True, help_text="Department description")
    color_code = models.CharField( max_length=7, default="#3B82F6", help_text="Color code for UI (hex format)")
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Department budget" )
    member_count = models.IntegerField(default=0,validators=[MinValueValidator(Decimal("0"))],help_text="Number of department members",)
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ["school", "department_name"]
        unique_together = [['school', 'department_code', 'department_name']]
        indexes = [
            models.Index(fields=["school", "department_code"]),
            models.Index(fields=["head_of_department"]),
            models.Index(fields=["school", "department_name"]),
        ]

    def __str__(self):
        return f"{self.department_name} - {self.school.school_name}"

    def clean(self):
        """Validate department data"""
        super().clean()
        if not re.match(r"^#[0-9A-Fa-f]{6}$", self.color_code):
            raise ValidationError(
                {"color_code": "Color code must be in hex format (e.g., #3B82F6)"}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
