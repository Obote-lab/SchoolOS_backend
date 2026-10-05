import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.choices.welfare import (
    DisciplineCategoryChoices,
    DisciplineSeverityChoices,
    DisciplineStatusChoices,
    CounselingSessionTypeChoices,
    CounselingSessionStatusChoices,
    NutritionQualityChoices,
    ExerciseFrequencyChoices,
)
from core.choices.common import StressLevelChoices

CustomUser = get_user_model()


class DisciplineIncident(models.Model):
    """Discipline incident records"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident_code = models.CharField(max_length=50, unique=True, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    reported_by = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL, null=True,related_name="reported_incidents",)
    discipline_category = models.CharField(max_length=20, choices=DisciplineCategoryChoices.choices)
    severity = models.CharField(max_length=20, choices=DisciplineSeverityChoices.choices)
    description = models.TextField()
    location = models.CharField(max_length=200)
    witnesses = models.JSONField(default=list, blank=True)
    evidence = models.JSONField(default=list, blank=True)
    date_occurred = models.DateTimeField(default=timezone.now)
    date_reported = models.DateTimeField(default=timezone.now)
    action_taken = models.TextField(blank=True)
    action_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True,blank=True,related_name="actioned_incidents",)
    parent_notified = models.BooleanField(default=False)
    parent_response = models.TextField(blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_notes = models.TextField(blank=True)
    discipline_status = models.CharField(max_length=20,choices=DisciplineStatusChoices.choices, default=DisciplineStatusChoices.REPORTED,)
    resolution_date = models.DateField(null=True, blank=True)
    recurring_pattern = models.BooleanField(default=False)
    previous_incidents = models.JSONField(default=list, blank=True)
    counseling_recommended = models.BooleanField(default=False)
    counseling_scheduled = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_occurred"]
        verbose_name = _("Discipline Incident")
        verbose_name_plural = _("Discipline Incidents")
        indexes = [
            models.Index(fields=["student", "date_occurred"]),
            models.Index(fields=["discipline_category", "severity"]),
            models.Index(fields=["discipline_status"]),
        ]

    def __str__(self):
        return f"{self.incident_code} - {self.student.admission_number}"

    def save(self, *args, **kwargs):
        if not self.incident_code:
            with transaction.atomic():
                year = timezone.now().year
                prefix = f"DISC/{year}/"
                last = (
                    DisciplineIncident.objects.select_for_update()
                    .filter(incident_code__startswith=prefix)
                    .order_by("-incident_code")
                    .first()
                )
                n = int(last.incident_code.split("/")[-1]) + 1 if last else 1
                self.incident_code = f"{prefix}{n:03d}"

            # Auto-set resolution date if status is resolved
            if (
                    self.discipline_status == DisciplineStatusChoices.RESOLVED
                    and not self.resolution_date
                ):
                self.resolution_date = timezone.now().date()

            super().save(*args, **kwargs)


    # DisciplineIncident / SickBay / Counseling / Wellness
    def clean(self):
        super().clean()
        if self.student_id and self.school_id:
            if self.student.school_id != self.school_id:
                raise ValidationError(
                    {"student": _("Student must belong to this school.")}
                )


class SickBayRecord(models.Model):
    """Student sick bay/health records"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE)
    complaint = models.TextField()
    diagnosis = models.TextField(blank=True)
    treatment = models.TextField(blank=True)
    medication_given = models.TextField(blank=True)
    vital_signs = models.JSONField( default=dict, blank=True)  # {temp: 36.5, bp: '120/80', pulse: 72}
    referred_to_hospital = models.BooleanField(default=False)
    hospital_name = models.CharField(max_length=200, blank=True)
    parent_notified = models.BooleanField(default=False)
    parent_response = models.TextField(blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    attended_by = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL, null=True,related_name="attended_records",)
    doctor_seen = models.BooleanField(default=False)
    doctor_name = models.CharField(max_length=200, blank=True)
    date = models.DateTimeField(default=timezone.now)
    duration_minutes = models.PositiveIntegerField(default=0)
    is_contagious = models.BooleanField(default=False)
    isolation_required = models.BooleanField(default=False)
    isolation_end_date = models.DateField(null=True, blank=True)
    class_excused = models.BooleanField(default=False)
    class_excuse_days = models.PositiveIntegerField(default=0)
    attachments = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = _("Sick Bay Record")
        verbose_name_plural = _("Sick Bay Records")
        indexes = [
            models.Index(fields=["student", "date"]),
            models.Index(fields=["is_contagious"]),
        ]

    def __str__(self):
        return f"{self.student.admission_number} - {self.date.date()}"

    # DisciplineIncident / SickBay / Counseling / Wellness
    def clean(self):
        super().clean()
        if self.student_id and self.school_id:
            if self.student.school_id != self.school_id:
                raise ValidationError(
                    {"student": _("Student must belong to this school.")}
                )


class CounselingSession(models.Model):
    """Counseling session records"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE)
    counselor = models.ForeignKey( "accounts.CustomUser", on_delete=models.CASCADE, related_name="counseling_sessions" )
    session_type = models.CharField(max_length=20, choices=CounselingSessionTypeChoices.choices )
    date = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    location = models.CharField(max_length=200)
    reason = models.TextField()
    notes = models.TextField(blank=True)  # Confidential notes
    recommendations = models.TextField(blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    parent_involved = models.BooleanField(default=False)
    parent_feedback = models.TextField(blank=True)
    referral_made = models.BooleanField(default=False)
    referral_to = models.CharField(max_length=200, blank=True)
    counseling_status = models.CharField( max_length=20,choices=CounselingSessionStatusChoices.choices,default=CounselingSessionStatusChoices.SCHEDULED,)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = _("Counseling Session")
        verbose_name_plural = _("Counseling Sessions")
        indexes = [
            models.Index(fields=["student", "date"]),
            models.Index(fields=["counselor", "session_type"]),
            models.Index(fields=["counseling_status"]),
        ]

    def __str__(self):
        return f"{self.student.admission_number} - {self.get_session_type_display()} - {self.date.date()}"

    # DisciplineIncident / SickBay / Counseling / Wellness
    def clean(self):
        super().clean()
        if self.student_id and self.school_id:
            if self.student.school_id != self.school_id:
                raise ValidationError(
                    {"student": _("Student must belong to this school.")}
                )
class WellnessCheck(models.Model):
    """Student wellness assessment records"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE)
    checked_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True, related_name="wellness_checks")
    check_date = models.DateField(default=timezone.now)
    mental_wellbeing_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)], null=True, blank=True)
    physical_wellbeing_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)], null=True, blank=True)
    social_wellbeing_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)], null=True, blank=True)
    academic_stress_level = models.CharField(choices=StressLevelChoices.choices, null=True, blank=True)
    sleep_hours_nightly = models.DecimalField(max_digits=4,decimal_places=1,null=True, blank=True,validators=[MinValueValidator(0), MaxValueValidator(24)], )
    nutrition_quality = models.CharField(max_length=20, choices=NutritionQualityChoices.choices, null=True, blank=True)
    exercise_frequency = models.CharField(max_length=20, choices=ExerciseFrequencyChoices.choices, null=True, blank=True)
    concerns_raised = models.TextField(blank=True)
    support_provided = models.TextField(blank=True)
    follow_up_planned = models.BooleanField(default=False)
    next_check_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-check_date"]
        verbose_name = _("Wellness Check")
        verbose_name_plural = _("Wellness Checks")
        indexes = [
            models.Index(fields=["student", "check_date"]),
            models.Index(fields=["academic_stress_level"]),
        ]

    def __str__(self):
        return f"{self.student.admission_number} - {self.check_date}"

    def calculate_overall_score(self):
        """Calculate overall wellness score"""
        scores = []
        if self.mental_wellbeing_score:
            scores.append(self.mental_wellbeing_score)
        if self.physical_wellbeing_score:
            scores.append(self.physical_wellbeing_score)
        if self.social_wellbeing_score:
            scores.append(self.social_wellbeing_score)

        if scores:
            return sum(scores) / len(scores)
        return None

    @property
    def overall_wellness(self):
        """Get overall wellness category"""
        score = self.calculate_overall_score()
        if score:
            if score >= 8:
                return "Excellent"
            elif score >= 6:
                return "Good"
            elif score >= 4:
                return "Fair"
            else:
                return "Poor"
        return None

    # DisciplineIncident / SickBay / Counseling / Wellness
    def clean(self):
        super().clean()
        if self.student_id and self.school_id:
            if self.student.school_id != self.school_id:
                raise ValidationError(
                    {"student": _("Student must belong to this school.")}
                )
