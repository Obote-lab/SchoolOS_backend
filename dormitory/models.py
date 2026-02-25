import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone  
from datetime import timedelta 


class Dormitory(models.Model):
    """Model representing a school dormitory/hostel."""
    
    BOYS = 'Boys'
    GIRLS = 'Girls'
    MIXED = 'Mixed'
    TYPE_CHOICES = [
        (BOYS, 'Boys'),
        (GIRLS, 'Girls'),
        (MIXED, 'Mixed'),
    ]
    
    # Status choices
    OPEN = 'Open'
    CLOSED = 'Closed'
    UNDER_RENOVATION = 'Under_Renovation'
    STATUS_CHOICES = [
        (OPEN, 'Open'),
        (CLOSED, 'Closed'),
        (UNDER_RENOVATION, 'Under Renovation'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='dormitories')
    name = models.CharField(max_length=100)
    dormitory_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    capacity = models.IntegerField(default=0)
    current_occupancy = models.IntegerField(default=0)
    prefect = models.ForeignKey('students.Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='dormitory_prefect')
    matron = models.ForeignKey('staff.StaffProfile', on_delete=models.SET_NULL, null=True, related_name='dormitory_matron')
    building = models.CharField(max_length=100, blank=True)
    floor = models.IntegerField(default=1)
    rooms = models.JSONField(default=list, blank=True)  
    facilities = models.JSONField(default=list, blank=True)
    rules = models.TextField(blank=True)
    curfew_time = models.TimeField(null=True, blank=True)
    lights_out_time = models.TimeField(null=True, blank=True)
    dormitory_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Dormitories"
        ordering = ['name']
        unique_together = ['school', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.school.code})"
    
    def save(self, *args, **kwargs):
        # Validate prefect matches dormitory type
        if self.prefect:
            if self.dormitory_type == self.BOYS and self.prefect.gender != 'Male':
                raise ValidationError("Boys dormitory prefect must be male student")
            elif self.dormitory_type == self.GIRLS and self.prefect.gender != 'Female':
                raise ValidationError("Girls dormitory prefect must be female student")
        
        super().save(*args, **kwargs)


class DormitoryInspection(models.Model):
    """Model for dormitory inspection records."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dormitory = models.ForeignKey(
        Dormitory,
        on_delete=models.CASCADE,
        related_name='inspections'
    )
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dormitory_inspections'
    )
    inspection_date = models.DateTimeField()
    cleanliness_score = models.IntegerField(default=1, choices=[(i, i) for i in range(1, 11)])
    orderliness_score = models.IntegerField(default=1, choices=[(i, i) for i in range(1, 11)])
    safety_score = models.IntegerField(default=1, choices=[(i, i) for i in range(1, 11)])
    issues_found = models.JSONField(default=list, blank=True)
    actions_taken = models.TextField(blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    next_inspection_date = models.DateTimeField(null=True, blank=True)
    attachments = models.JSONField(default=list, blank=True)  # photos
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-inspection_date']
        verbose_name_plural = "Dormitory Inspections"
    
    def __str__(self):
        return f"Inspection of {self.dormitory.name} on {self.inspection_date}"
    
    def save(self, *args, **kwargs):
    # Calculate average score
        avg_score = (self.cleanliness_score + self.orderliness_score + self.safety_score) / 3
        
        # Auto-set follow-up if scores are low
        if avg_score < 5 and not self.follow_up_required:
            self.follow_up_required = True
        
        # Auto-set next inspection date (default 1 month later)
        if not self.next_inspection_date and self.inspection_date:
            # Already imported timezone at top
            self.next_inspection_date = self.inspection_date + timedelta(days=30)  # Use timedelta
        
        super().save(*args, **kwargs)
    
    @property
    def average_score(self):
        """Calculate average inspection score."""
        return round((self.cleanliness_score + self.orderliness_score + self.safety_score) / 3, 1)
    

class RoomAllocation(models.Model):
    """Model for allocating students to specific rooms/beds."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey('students.Student',on_delete=models.CASCADE,related_name='room_allocations') 
    dormitory = models.ForeignKey(Dormitory,on_delete=models.CASCADE, related_name='allocations')
    room_number = models.CharField(max_length=20)
    bed_number = models.CharField(max_length=20, blank=True)
    locker_number = models.CharField(max_length=20, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['dormitory', 'room_number', 'bed_number']
        constraints = [
            models.UniqueConstraint(
                fields=['dormitory', 'room_number', 'bed_number'],
                name='unique_bed_per_dormitory'
            ),
            models.UniqueConstraint(
                fields=['student'],
                condition=models.Q(is_active=True),
                name='unique_active_allocation_per_student'
            ),
        ]
    def __str__(self):
        return f"{self.student} in {self.dormitory.name} Room {self.room_number}"
    
