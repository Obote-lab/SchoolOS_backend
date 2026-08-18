import uuid
from datetime import timedelta
from django.db.models import F
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.choices.dormitory import DormStatusChoices, DormTypeChoices


class Dormitory(models.Model):
    """School dormitory / hostel block."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="dormitories")
    name = models.CharField(max_length=100)
    dorm_type = models.CharField(max_length=20, choices=DormTypeChoices.choices)
    capacity = models.PositiveIntegerField(default=0, validators=[MinValueValidator(1)])
    current_occupancy = models.PositiveIntegerField(default=0, editable=False)
    prefect = models.ForeignKey("students.StudentProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="dorm_prefect_of",)
    matron = models.ForeignKey("staff.StaffProfile",on_delete=models.SET_NULL,null=True, blank=True,related_name="dorm_matron_of",)
    building = models.CharField(max_length=100, blank=True)
    floor = models.PositiveIntegerField(default=1)
    rooms = models.JSONField( default=list, blank=True,help_text=_("List of rooms: [{'number':'101','beds':4,'type':'double'}]"),)
    facilities = models.JSONField(default=list, blank=True, help_text=_("e.g. ['hot_water','study_area','wifi']"))
    rules = models.TextField(blank=True)
    curfew_time = models.TimeField(null=True, blank=True)
    lights_out_time = models.TimeField(null=True, blank=True)
    dorm_status = models.CharField(max_length=20, choices=DormStatusChoices.choices, default=DormStatusChoices.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Dormitories"
        ordering = ["name"]
        unique_together = [["school", "name"]]
        indexes = [
            models.Index(fields=["school", "dorm_type", "dorm_status"]),
            models.Index(fields=["current_occupancy"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.school.school_code})"

    def clean(self):
        if self.prefect:
            if self.dorm_type == DormTypeChoices.BOYS and self.prefect.gender != "Male":
                raise ValidationError(_("Boys' dormitory prefect must be male."))
            if self.dorm_type == DormTypeChoices.GIRLS and self.prefect.gender != "Female":
                raise ValidationError(_("Girls' dormitory prefect must be female."))

        if self.current_occupancy > self.capacity:
            raise ValidationError(_("Current occupancy cannot exceed capacity."))

    def save(self, *args, **kwargs):
        if self.pk:
            original = Dormitory.objects.get(pk=self.pk)
            if self.capacity < original.current_occupancy:
                raise ValidationError(
                    _("Cannot reduce capacity below current occupancy.")
                )
        super().save(*args, **kwargs)


class DormitoryInspection(models.Model):
    """Routine / surprise dormitory inspection record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dormitory = models.ForeignKey("dormitory.Dormitory", on_delete=models.CASCADE, related_name="inspections")
    inspected_by = models.ForeignKey("accounts.CustomUser",on_delete=models.SET_NULL, null=True,related_name="dorm_inspections_conducted",)
    inspection_date = models.DateTimeField(default=timezone.now)
    cleanliness_score = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)])
    orderliness_score = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)])
    safety_score = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)])
    issues_found = models.JSONField(default=list, blank=True)
    actions_taken = models.TextField(blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    next_inspection_date = models.DateTimeField(null=True, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-inspection_date"]
        indexes = [
            models.Index(fields=["dormitory", "inspection_date"]),
            models.Index(fields=["follow_up_required", "follow_up_date"]),
        ]

    def __str__(self):
        return f"Inspection {self.dormitory.name} – {self.inspection_date.date()}"

    @property
    def average_score(self):
        return round(
            (self.cleanliness_score + self.orderliness_score + self.safety_score) / 3, 1
        )

    def save(self, *args, **kwargs):
        if self.follow_up_required and not self.follow_up_date:
            self.follow_up_date = self.inspection_date.date() + timedelta(days=7)

        if not self.next_inspection_date:
            self.next_inspection_date = self.inspection_date + timedelta(days=30)

        super().save(*args, **kwargs)


class RoomAllocation(models.Model):
    """Student → room/bed assignment (historical & active)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="dorm_allocations")
    dormitory = models.ForeignKey( "dormitory.Dormitory", on_delete=models.CASCADE, related_name="allocations")
    room_number = models.CharField(max_length=20)
    bed_number = models.CharField(max_length=20, blank=True)
    locker_number = models.CharField(max_length=20, blank=True)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["dormitory", "room_number", "bed_number", "-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["dormitory", "room_number", "bed_number", "is_active"],
                condition=models.Q(is_active=True),
                name="unique_active_bed",
            ),
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(is_active=True),
                name="unique_active_allocation_per_student",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "is_active"]),
            models.Index(fields=["dormitory", "is_active"]),
        ]

    def __str__(self):
        return f"{self.student.admission_number} – {self.dormitory.name} Rm {self.room_number}"

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError(_("End date must be after start date."))

    def save(self, *args, **kwargs):
        self.clean()

        if self.pk:
            original = RoomAllocation.objects.get(pk=self.pk)
            if original.is_active and not self.is_active:
                # Deactivation → reduce occupancy
                self.dormitory.current_occupancy = models.F("current_occupancy") - 1
                self.dormitory.save(update_fields=["current_occupancy"])
        else:
            if self.is_active:
                # New active allocation → increase occupancy
                self.dormitory.current_occupancy = models.F("current_occupancy") + 1
                self.dormitory.save(update_fields=["current_occupancy"])

        super().save(*args, **kwargs)
