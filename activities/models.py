import uuid
from django.conf import settings
from django.db import models
from core.choices.activities import (
    ActivityCategoryChoices,
    ActivityStatusChoices ,
    ActivitySeasonChoices,
    ActivityRoleChoices,
    StudentActivityStatusChoices,
    PerformanceLevelChoices,
    PotentialLevelChoices,
    CompetitionLevelChoices,
)
from django.core.exceptions import ValidationError

class Activity(models.Model):
    """Model representing a co-curricular activity in the school."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="activities")
    name = models.CharField(max_length=200)
    activity_category = models.CharField( max_length=20, choices=ActivityCategoryChoices.choices)
    sub_category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    teacher_in_charge = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL,null=True,related_name="activities_leading",)
    assistant_in_charge = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL,null=True,blank=True,related_name="activities_assisting",)
    max_participants = models.IntegerField(default=30)
    current_participants = models.IntegerField(default=0)
    schedule = models.JSONField(default=dict, blank=True)
    equipment_needed = models.TextField(blank=True)
    budget_allocated = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    budget_used = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    achievements = models.JSONField(default=list, blank=True)
    activity_status = models.CharField(max_length=20, choices=ActivityStatusChoices.choices, default=ActivityStatusChoices.ACTIVE)
    season = models.CharField(max_length=10, choices=ActivitySeasonChoices.choices, blank=True)
    performance_metrics = models.JSONField(default=dict, blank=True)
    prerequisites = models.TextField(blank=True)
    uniform_required = models.BooleanField(default=False)
    parent_consent_required = models.BooleanField(default=False)
    risk_assessment_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        verbose_name_plural = "Activities"
        ordering = ["name"]
        unique_together = ["school", "name"]

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.teacher_in_charge_id and self.school_id:
            # optional: staff must be in same school via staff_profile
            pass
        if self.budget_used > self.budget_allocated and self.budget_allocated > 0:
            raise ValidationError(
                {"budget_used": "Cannot exceed allocated budget."}
            )


class StudentActivity(models.Model):
    """Model representing a student's participation in an activity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="activities")
    activity = models.ForeignKey("activities.Activity", on_delete=models.CASCADE, related_name="participants")
    role = models.CharField(max_length=15, choices=ActivityRoleChoices.choices, default=ActivityRoleChoices.MEMBER)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    student_activity_status = models.CharField(max_length=10,choices=StudentActivityStatusChoices.choices,default=StudentActivityStatusChoices.ACTIVE,)
    performance_level = models.CharField(max_length=15,choices=PerformanceLevelChoices.choices,default=PerformanceLevelChoices.BEGINNER,)
    achievements = models.JSONField(default=list, blank=True)
    hours_logged = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    coach_feedback = models.TextField(blank=True)
    improvement_areas = models.TextField(blank=True)
    talent_score = models.DecimalField( max_digits=5, decimal_places=2, null=True, blank=True)  # 1-100
    potential_level = models.CharField(max_length=15, choices=PotentialLevelChoices.choices, blank=True)
    career_potential = models.BooleanField(default=False)
    recommendations = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Student Activities"
        ordering = ["-start_date", "student"]
        unique_together = ["student", "activity"]

    def __str__(self):
        return f"{self.student.admission_number} - {self.activity.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.activity:
            self.activity.save()

    def clean(self):
        super().clean()
        if self.activity_id and self.student_id:
            if self.student.school_id != self.activity.school_id:
                raise ValidationError(
                    {"student": "Student must belong to the activity's school."}
                )
        if (
            self.student_activity_status == StudentActivityStatusChoices.ACTIVE
            and self.activity_id
            and not self.pk
        ):
            active = self.activity.participants.filter(
                student_activity_status=StudentActivityStatusChoices.ACTIVE
            ).count()
            if active >= self.activity.max_participants:
                raise ValidationError(
                    {"activity": "Activity is at maximum capacity."}
                )


class Competition(models.Model):
    """Model representing a competition/event related to an activity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey("activities.Activity", on_delete=models.CASCADE, related_name="competitions")
    name = models.CharField(max_length=200)
    competition_level = models.CharField(max_length=15, choices=CompetitionLevelChoices.choices)
    date = models.DateField()
    venue = models.CharField(max_length=200, blank=True)
    organizer = models.CharField(max_length=200, blank=True)
    results = models.JSONField(default=dict, blank=True)
    participants = models.JSONField(default=list, blank=True)
    media_links = models.JSONField(default=list, blank=True)
    learnings = models.TextField(blank=True)
    next_competition = models.DateField(null=True, blank=True)
    budget_used = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sponsors = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL,null=True,related_name="competitions_created",)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "name"]
        verbose_name_plural = "Competitions"

    def __str__(self):
        return f"{self.name} ({self.activity.name})"

    def clean(self):
        if self.next_competition and self.date and self.next_competition < self.date:
            raise ValidationError(
                {"next_competition": "Must be on or after competition date."}
            )