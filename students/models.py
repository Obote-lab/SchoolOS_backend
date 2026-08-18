import uuid
from decimal import Decimal
from rest_framework.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .utils import generate_admission_number, validate_age
from core.utils.phone import validate_kenyan_phone

from core.choices.people import (
    ReligionChoices,
    DisabilityChoices,
    BloodGroupChoices,
    RelationshipChoices,
)
from core.choices.students import (
    StudentCategoryChoices,
    StudentStatusChoices,
)
from core.choices.common import GenderChoices
from core.choices.health import RecordTypeChoices
from core.utils.dates import calculate_age


class StudentProfile(models.Model):
    """Extended profile for Students."""

    user = models.OneToOneField( "accounts.CustomUser", on_delete=models.PROTECT, related_name="student_profile",)
    school = models.ForeignKey("schools.School",on_delete=models.CASCADE, related_name="students")
    admission_number = models.CharField( max_length=50,help_text=_("Unique admission number within the school"))
    current_class = models.ForeignKey("schools.ClassRoom",on_delete=models.SET_NULL,null=True, blank=True,related_name="current_students")
    registration_date = models.DateField(default=timezone.now)
    admission_date = models.DateField()
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20, choices=GenderChoices.choices)
    religion = models.CharField(max_length=20, choices=ReligionChoices.choices, blank=True)
    nationality = models.CharField(max_length=100, default="Kenyan")
    county_of_origin = models.CharField(max_length=100, blank=True)
    sub_county_of_origin = models.CharField(max_length=100, blank=True)
    disability = models.CharField(max_length=4, choices=DisabilityChoices.choices, default=DisabilityChoices.NONE)
    disability_details = models.TextField(blank=True)
    blood_group = models.CharField(max_length=3, choices=BloodGroupChoices.choices, blank=True)
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    emer_contact_name = models.CharField(max_length=200)
    emer_contact_phone = models.CharField(max_length=20, validators=[validate_kenyan_phone])
    emer_contact_relation = models.CharField(max_length=100)
    emer_contact_alternate_phone = models.CharField(max_length=20,blank=True,validators=[validate_kenyan_phone])
    previous_school = models.CharField(max_length=200, blank=True)
    kcpe_index = models.CharField(max_length=20, blank=True)
    boarding_house = models.ForeignKey( "dormitory.Dormitory",on_delete=models.SET_NULL, null=True, blank=True, related_name="current_students")
    student_category = models.CharField( max_length=4, choices=StudentCategoryChoices.choices, default=StudentCategoryChoices.REGULAR)
    sponsor = models.CharField(max_length=200, blank=True)
    sponsor_contact = models.CharField(max_length=200, blank=True)
    talents = models.JSONField(default=list, blank=True)
    learning_style = models.CharField(max_length=20, blank=True)
    academic_potential = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    risk_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    student_status = models.CharField( max_length=20, choices=StudentStatusChoices.choices, default=StudentStatusChoices.ACTIVE)
    status_reason = models.TextField(blank=True)
    exit_date = models.DateField(null=True, blank=True)
    exit_notes = models.TextField(blank=True)
    last_health_check = models.DateField(null=True, blank=True)
    last_discipline_check = models.DateField(null=True, blank=True)
    # Cached / computed
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    average_grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fee_compliance_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    current_academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.SET_NULL, null=True, blank=True)
    current_term = models.ForeignKey("schools.Term", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Student Profile")
        verbose_name_plural = _("Student Profiles")
        ordering = ["admission_number"]
        indexes = [
            models.Index(fields=["admission_number"]),
            models.Index(fields=["school", "current_class"]),
            models.Index(fields=["student_status"]),
            models.Index(fields=["risk_score"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "admission_number"],
                name="unique_admission_per_school",
            ),
]

    def __str__(self):
        return f"{self.admission_number} - {self.user.get_full_name()}"

    # def clean(self):
    #     super().clean()
    #     validate_age(self.date_of_birth)
    def clean(self):
        super().clean()
        validate_age(self.date_of_birth)
        if self.current_class and self.school:
            if self.current_class.school != self.school:
                raise ValidationError(
                    {"current_class": "Classroom must belong to the same school."}
                )
        if self.boarding_house and self.school:
            # if Dormitory has school FK
            if getattr(self.boarding_house, "school_id", None) not in (None, self.school):
                raise ValidationError(
                    {"boarding_house": "Dormitory must belong to the same school."}
                )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if not self.admission_number and self.school:
            self.admission_number = generate_admission_number(self.school)
        if validate:
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


class ParentGuardian(models.Model):
    """Parent / Guardian linked to students"""

    user = models.OneToOneField( "accounts.CustomUser", on_delete=models.CASCADE, related_name="parent_profile" )
    students = models.ManyToManyField( StudentProfile, related_name="parents", blank=True)
    relationship = models.CharField( max_length=10, choices=RelationshipChoices.choices, default=RelationshipChoices.MOTHER)
    is_primary = models.BooleanField(default=False)
    can_pickup = models.BooleanField(default=True)
    can_consent = models.BooleanField(default=True)
    alternate_phone = models.CharField(max_length=20, blank=True, validators=[validate_kenyan_phone])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Parent / Guardian")
        verbose_name_plural = _("Parents / Guardians")
        indexes = [models.Index(fields=["is_primary"])]

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_relationship_display()})"


class StudentMedicalHistory(models.Model):

    student = models.ForeignKey( StudentProfile, on_delete=models.CASCADE, related_name="medical_history")
    record_type = models.CharField(max_length=20, choices=RecordTypeChoices.choices)
    description = models.TextField()
    date = models.DateField(default=timezone.now)
    doctor_name = models.CharField(max_length=200, blank=True)
    hospital = models.CharField(max_length=200, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    medication = models.TextField(blank=True)
    logged_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL,null=True )
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.student.admission_number} - {self.get_record_type_display()}"