# students/models.py
import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

from .utils import validate_age, validate_phone_number


class Student(models.Model):
    """Core student record — identity, status, class assignment, emergency info"""

    class GenderChoices(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other"

    class StudentCategoryChoices(models.TextChoices):
        REGULAR = "regular", "Regular Student"
        BURSARY = "bursary", "Bursary Student"
        SCHOLARSHIP = "scholarship", "Scholarship Student"
        SPECIAL_NEEDS = "special_needs", "Special Needs"
        SPONSORED = "sponsored", "Sponsored"

    class StudentStatusChoices(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        TRANSFERRED = "transferred", "Transferred"
        GRADUATED = "graduated", "Graduated"
        WITHDRAWN = "withdrawn", "Withdrawn"
        EXPELLED = "expelled", "Expelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admission_number = models.CharField(max_length=50,help_text="Unique admission number within the school")
    user = models.OneToOneField( settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="student_profile", help_text="Linked user account")
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE,related_name="students")
    current_class = models.ForeignKey("schools.ClassRoom", on_delete=models.SET_NULL, null=True, blank=True,related_name="students",help_text="Current class / stream")
    admission_date = models.DateField(help_text="Date of admission to school")
    registration_date = models.DateField(default=timezone.now)
    # Personal basics
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GenderChoices.choices)
    nationality = models.CharField(max_length=100, default="Kenyan")
    county_of_origin = models.CharField(max_length=100, blank=True)
    # Health & emergency (minimal but useful)
    allergies = models.TextField(blank=True, help_text="Known allergies / medical alerts")
    emer_contact_name = models.CharField(max_length=200)
    emer_contact_phone = models.CharField(max_length=20, validators=[RegexValidator(r"^\+?1?\d{9,15}$")])
    emer_contact_relation = models.CharField(max_length=100)
    emer_contact_alternate_phone = models.CharField(max_length=20, blank=True)
    # Academic entry points
    previous_school = models.CharField(max_length=200, blank=True)
    kcpe_index = models.CharField(max_length=20, blank=True, help_text="KCPE index number (secondary)")
    # Boarding (link only — details in dormitory app)
    boarding_house = models.ForeignKey( "dormitory.Dormitory",on_delete=models.SET_NULL,null=True, blank=True,related_name="students" )
    # Classification
    student_category = models.CharField( max_length=20,choices=StudentCategoryChoices.choices, default=StudentCategoryChoices.REGULAR)
    sponsor = models.CharField(max_length=200, blank=True, help_text="Sponsor / bursary provider")
    # Status tracking
    student_status = models.CharField(max_length=20,choices=StudentStatusChoices.choices,default=StudentStatusChoices.ACTIVE)
    status_reason = models.TextField(blank=True)
    exit_date = models.DateField(null=True, blank=True)
    # Current context (auto-settable)
    current_academic_year = models.ForeignKey("schools.AcademicYear",on_delete=models.SET_NULL, null=True, blank=True)
    current_term = models.ForeignKey( "schools.Term", on_delete=models.SET_NULL,null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"
        ordering = ["admission_number"]
        unique_together = [["school", "admission_number"]]
        indexes = [
            models.Index(fields=["admission_number"]),
            models.Index(fields=["school", "current_class"]),
            models.Index(fields=["student_status"]),
            models.Index(fields=["student_category"]),
            models.Index(fields=["date_of_birth"]),
        ]

    def __str__(self):
        return f"{self.admission_number} - {self.user.get_full_name() or 'No name'}"

    def clean(self):
        super().clean()

        if self.admission_date and self.admission_date > timezone.now().date():
            raise ValidationError({"admission_date": "Cannot be in future"})

        if self.date_of_birth and self.date_of_birth > timezone.now().date():
            raise ValidationError({"date_of_birth": "Cannot be in future"})

        validate_age(self.date_of_birth)

        if self.exit_date and self.exit_date > timezone.now().date():
            raise ValidationError({"exit_date": "Cannot be in future"})

        if self.current_class and self.current_class.current_enrollment >= self.current_class.capacity:
            raise ValidationError({"current_class": "Class is at full capacity"})

    def save(self, *args, **kwargs):
        if not self.admission_number and self.school:
            from .utils import generate_admission_number
            self.admission_number = generate_admission_number(self.school)

        # Auto-fill current year/term if missing
        if self.school and not self.current_academic_year:
            current_year = self.school.academic_years.filter(is_current=True).first()
            if current_year:
                self.current_academic_year = current_year

        if self.current_academic_year and not self.current_term:
            current_term = self.current_academic_year.terms.filter(
                term_status="active"
            ).first()
            if current_term:
                self.current_term = current_term

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = timezone.now().date()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def full_name(self):
        return self.user.get_full_name()

    def update_status(self, new_status, reason=""):
        if new_status not in dict(self.StudentStatusChoices.choices):
            raise ValueError("Invalid status")

        # Simple transition guard (expand later)
        if new_status in [self.StudentStatusChoices.GRADUATED, self.StudentStatusChoices.TRANSFERRED,
                          self.StudentStatusChoices.WITHDRAWN, self.StudentStatusChoices.EXPELLED]:
            self.exit_date = timezone.now().date()

        self.student_status = new_status
        self.status_reason = reason
        self.save(update_fields=["student_status", "status_reason", "exit_date"])


class ParentGuardian(models.Model):
    """Parent / guardian linked to one or more students"""

    class RelationshipChoices(models.TextChoices):
        FATHER = "father", "Father"
        MOTHER = "mother", "Mother"
        GUARDIAN = "guardian", "Guardian"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="parent_profile" )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="guardians")
    relationship = models.CharField( max_length=20, choices=RelationshipChoices.choices, default=RelationshipChoices.GUARDIAN)
    is_primary = models.BooleanField(default=False)
    # Permissions & contact
    can_pickup = models.BooleanField(default=True)
    can_consent = models.BooleanField(default=True)  
    # Optional extra contact
    alternate_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Parent/Guardian"
        verbose_name_plural = "Parents/Guardians"
        unique_together = [["user", "student"]]
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(is_primary=True),
                name="unique_primary_guardian_per_student"
            )
        ]
        indexes = [
            models.Index(fields=["student", "is_primary"]),
            models.Index(fields=["relationship"]),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_relationship_display()})"

    def clean(self):
        super().clean()
        if self.is_primary:
            existing = ParentGuardian.objects.filter(
                student=self.student, is_primary=True
            ).exclude(id=self.id)
            if existing.exists():
                raise ValidationError({"is_primary": "Student already has a primary guardian"})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class StudentMedicalHistory(models.Model):
    """Historical medical records — kept separate from main student record"""

    class RecordTypeChoices(models.TextChoices):
        VACCINATION = "vaccination", "Vaccination"
        CHECKUP = "checkup", "Checkup"
        ILLNESS = "illness", "Illness / Treatment"
        ACCIDENT = "accident", "Accident / Injury"
        ALLERGY = "allergy", "Allergy Event"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey( Student,on_delete=models.CASCADE, related_name="medical_history")
    record_type = models.CharField( max_length=20,choices=RecordTypeChoices.choices,default=RecordTypeChoices.CHECKUP)
    description = models.TextField()
    date = models.DateField(default=timezone.now)
    doctor_name = models.CharField(max_length=200, blank=True)
    hospital = models.CharField(max_length=200, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    medication = models.TextField(blank=True)
    logged_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL, null=True, related_name="medical_records_logged")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Medical History Record"
        verbose_name_plural = "Medical History Records"
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["student", "record_type"]),
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"{self.student.admission_number} - {self.get_record_type_display()} ({self.date})"

    def clean(self):
        super().clean()
        if self.date > timezone.now().date():
            raise ValidationError({"date": "Cannot be in future"})
        if self.follow_up_date and self.follow_up_date < self.date:
            raise ValidationError({"follow_up_date": "Cannot be before event date"})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)