import uuid
from django.db import models
from django.conf import settings
from schools.models import School
from students.models import Student
from staff.models import StaffProfile
from django.db import transaction

class Notification(models.Model):
    """Model representing notifications sent to users."""
    # Category choices
    ACADEMIC = 'Academic'
    FINANCIAL = 'Financial'
    ATTENDANCE = 'Attendance'
    HEALTH = 'Health'
    EVENT = 'Event'
    EMERGENCY = 'Emergency'
    SYSTEM = 'System'
    CATEGORY_CHOICES = [
        (ACADEMIC, 'Academic'),
        (FINANCIAL, 'Financial'),
        (ATTENDANCE, 'Attendance'),
        (HEALTH, 'Health'),
        (EVENT, 'Event'),
        (EMERGENCY, 'Emergency'),
        (SYSTEM, 'System'),
    ]
    
    # Priority choices
    LOW = 'Low'
    NORMAL = 'Normal'
    HIGH = 'High'
    CRITICAL = 'Critical'
    PRIORITY_CHOICES = [
        (LOW, 'Low'),
        (NORMAL, 'Normal'),
        (HIGH, 'High'),
        (CRITICAL, 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification_id = models.CharField(max_length=50, unique=True)  # NOT/2025/001
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications_received')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications_sent')
    notification_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=NORMAL)
    title = models.CharField(max_length=200)
    message = models.TextField()
    action_url = models.URLField(blank=True)
    channels = models.JSONField(default=list, blank=True)  # SMS, Email, App, WhatsApp
    delivery_status = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_action = models.CharField(max_length=50, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at', '-priority']
    
    def __str__(self):
        return f"{self.notification_id}: {self.title}"
    

    def save(self, *args, **kwargs):
        if not self.notification_id:
            with transaction.atomic():
                year = timezone.now().year
                last = Notification.objects.select_for_update().filter(
                    notification_id__startswith=f"NOT/{year}/"
                ).order_by('-notification_id').first()
                number = int(last.notification_id.split('/')[-1]) + 1 if last else 1
                self.notification_id = f"NOT/{year}/{number:03d}"
        super().save(*args, **kwargs)



class Feedback(models.Model):
    """Model representing feedback from users."""
    
    # Type choices
    COMPLAINT = 'Complaint'
    SUGGESTION = 'Suggestion'
    COMPLIMENT = 'Compliment'
    QUERY = 'Query'
    REPORT = 'Report'
    TYPE_CHOICES = [
        (COMPLAINT, 'Complaint'),
        (SUGGESTION, 'Suggestion'),
        (COMPLIMENT, 'Compliment'),
        (QUERY, 'Query'),
        (REPORT, 'Report'),
    ]
    
    # Category choices
    ACADEMIC = 'Academic'
    ADMINISTRATIVE = 'Administrative'
    FACILITIES = 'Facilities'
    SAFETY = 'Safety'
    OTHER = 'Other'
    CATEGORY_CHOICES = [
        (ACADEMIC, 'Academic'),
        (ADMINISTRATIVE, 'Administrative'),
        (FACILITIES, 'Facilities'),
        (SAFETY, 'Safety'),
        (OTHER, 'Other'),
    ]
    
    # Priority choices
    LOW = 'Low'
    NORMAL = 'Normal'
    HIGH = 'High'
    URGENT = 'Urgent'
    PRIORITY_CHOICES = [
        (LOW, 'Low'),
        (NORMAL, 'Normal'),
        (HIGH, 'High'),
        (URGENT, 'Urgent'),
    ]
    
    # Status choices
    SUBMITTED = 'Submitted'
    UNDER_REVIEW = 'Under_Review'
    RESOLVED = 'Resolved'
    ESCALATED = 'Escalated'
    CLOSED = 'Closed'
    STATUS_CHOICES = [
        (SUBMITTED, 'Submitted'),
        (UNDER_REVIEW, 'Under Review'),
        (RESOLVED, 'Resolved'),
        (ESCALATED, 'Escalated'),
        (CLOSED, 'Closed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feedback_type = models.CharField(max_length=15, choices=TYPE_CHOICES)
    feedback_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='feedback_submitted'
    )
    related_to_student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    related_to_staff = models.ForeignKey(
        StaffProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    anonymous = models.BooleanField(default=False)
    contact_allowed = models.BooleanField(default=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=NORMAL)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feedback_assigned'
    )
    feedback_status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=SUBMITTED)
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feedback_resolved'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    user_rating = models.IntegerField(null=True, blank=True)
    user_followup_feedback = models.TextField(blank=True)
    escalation_path = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at', '-priority']
    
    def __str__(self):
        if self.anonymous:
            return f"Anonymous {self.feedback_type}: {self.title}"
        return f"{self.submitted_by} - {self.feedback_type}: {self.title}"


class Announcement(models.Model):
    """Model representing school announcements."""
    
    # Category choices
    EVENT = 'Event'
    HOLIDAY = 'Holiday'
    EXAM = 'Exam'
    MEETING = 'Meeting'
    GENERAL = 'General'
    CATEGORY_CHOICES = [
        (EVENT, 'Event'),
        (HOLIDAY, 'Holiday'),
        (EXAM, 'Exam'),
        (MEETING, 'Meeting'),
        (GENERAL, 'General'),
    ]
    
    # Priority choices
    NORMAL = 'Normal'
    IMPORTANT = 'Important'
    EMERGENCY = 'Emergency'
    PRIORITY_CHOICES = [
        (NORMAL, 'Normal'),
        (IMPORTANT, 'Important'),
        (EMERGENCY, 'Emergency'),
    ]
    
    # Status choices
    DRAFT = 'Draft'
    PENDING = 'Pending'
    PUBLISHED = 'Published'
    EXPIRED = 'Expired'
    ARCHIVED = 'Archived'
    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (PENDING, 'Pending'),
        (PUBLISHED, 'Published'),
        (EXPIRED, 'Expired'),
        (ARCHIVED, 'Archived'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=200)
    content = models.TextField()
    announcement_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=NORMAL)
    target_audience = models.JSONField(default=dict, blank=True)
    publish_date = models.DateTimeField()
    expiry_date = models.DateTimeField(null=True, blank=True)
    requires_acknowledgment = models.BooleanField(default=False)
    acknowledgment_count = models.IntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,related_name='announcements_created')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='announcements_approved')
    attachments = models.JSONField(default=list, blank=True)
    channels = models.JSONField(default=list, blank=True)
    announcement_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-publish_date', '-priority']
    
    def __str__(self):
        return f"{self.title} ({self.school.code})"


class ParentTeacherMeeting(models.Model):
    """Model representing parent-teacher meetings."""
    
    # Status choices
    SCHEDULED = 'Scheduled'
    IN_PROGRESS = 'In_Progress'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'
    STATUS_CHOICES = [
        (SCHEDULED, 'Scheduled'),
        (IN_PROGRESS, 'In Progress'),
        (COMPLETED, 'Completed'),
        (CANCELLED, 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='parent_teacher_meetings')
    title = models.CharField(max_length=200)
    purpose = models.TextField()
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    venue = models.CharField(max_length=200)
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='meetings_organized'
    )
    invitees = models.JSONField(default=list, blank=True)
    agenda = models.JSONField(default=list, blank=True)
    minutes = models.TextField(blank=True)
    decisions = models.JSONField(default=list, blank=True)
    action_items = models.JSONField(default=list, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    meeting_status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=SCHEDULED)
    attendance = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['date', 'start_time']
    
    def __str__(self):
        return f"{self.title} on {self.date}"