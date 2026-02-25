import uuid,logging
from django.db import models
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from schools.models import School, AcademicYear, Term
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.gis.db.models import PointField
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

class AttendanceSession(models.Model):
    """Attendance session (e.g., morning assembly, class session)"""
    
    class AttendanceSessionTypeChoices(models.TextChoices):
        MORNING_ASSEMBLY = 'morning_assembly', _('Morning Assembly')
        CLASS = 'class', _('Class')
        DORMITORY = 'dormitory', _('Dormitory')
        MEAL = 'meal', _('Meal')
        ACTIVITY = 'activity', _('Activity')
        STUDY = 'study', _('Study')
        CHAPEL = 'chapel', _('Chapel')
        SPORTS = 'sports', _('Sports')
        LAB = 'lab', _('Laboratory')
    
    class AttendanceStatusChoices(models.TextChoices):
        SCHEDULED = 'scheduled', _('Scheduled')
        ONGOING = 'ongoing', _('Ongoing')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_type = models.CharField(max_length=20, choices=AttendanceSessionTypeChoices.choices)
    reference_id = models.UUIDField(null=True, blank=True) 

    school = models.ForeignKey( School, on_delete=models.CASCADE,related_name='attendance_sessions')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE )

    date = models.DateField(default=timezone.now)
    start_time = models.TimeField()
    end_time = models.TimeField()
    expected_count = models.PositiveIntegerField(default=0)
    actual_count = models.PositiveIntegerField(default=0)
    conducted_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='conducted_sessions')
    verified_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True,related_name='verified_sessions')
    notes = models.TextField(blank=True)
    attendance_session_status = models.CharField(max_length=20, choices=AttendanceStatusChoices.choices, default=AttendanceStatusChoices.SCHEDULED)
    automated = models.BooleanField(default=False)
    device_id = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=200, blank=True)  # GPS coordinates or room name
    weather = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['date', 'start_time']
        verbose_name = _('Attendance Session')
        verbose_name_plural = _('Attendance Sessions')
        indexes = [
            models.Index(fields=['date', 'session_type']),
            models.Index(fields=['school', 'date']), 
            models.Index(fields=['attendance_session_status']),
            models.Index(fields=['conducted_by']),
            models.Index(fields=['reference_id']), 
        ]
    
    def __str__(self):
        return f"{self.get_session_type_display()} - {self.date} {self.start_time}"
    
    def clean(self):
        """Validate session data"""
        if self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'End time must be after start time'})
        
        if self.actual_count > self.expected_count and self.expected_count > 0:
            raise ValidationError({'actual_count': 'Actual count cannot exceed expected count'})
    
    def update_actual_count(self):
        from .models import AttendanceRecord
        self.actual_count = AttendanceRecord.objects.filter(
            session=self,
            status__in=[
                AttendanceRecord.AttendanceRecordStatusChoices.PRESENT,
                AttendanceRecord.AttendanceRecordStatusChoices.LATE
            ]
        ).count()
        self.save(update_fields=['actual_count'])



class AttendanceRecord(models.Model):
    """Individual student attendance record"""
    
    class AttendanceRecordStatusChoices(models.TextChoices):
        PRESENT = 'present', _('Present')
        LATE = 'late', _('Late')
        ABSENT = 'absent', _('Absent')
        EXCUSED = 'excused', _('Excused')
        SICK = 'sick', _('Sick')
        SUSPENDED = 'suspended', _('Suspended')
    
    class DeviceUsedChoices(models.TextChoices):
        BIOMETRIC = 'biometric', _('Biometric')
        QR_CODE = 'qr', _('QR Code')
        MANUAL = 'manual', _('Manual')
        MOBILE_APP = 'mobile_app', _('Mobile App')
        RFID = 'rfid', _('RFID')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE)
    
    status = models.CharField(max_length=20, choices=AttendanceRecordStatusChoices.choices, default=AttendanceRecordStatusChoices.PRESENT)
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    
    doctor_note = models.BooleanField(default=False)
    parent_notified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True,related_name='verified_records')
    
    device_used = models.CharField(max_length=20, choices=DeviceUsedChoices.choices, default=DeviceUsedChoices.MANUAL)
    location = PointField(null=True, blank=True, geography=True)  # GPS location
    photo_evidence = models.ImageField(upload_to='attendance/photos/', null=True, blank=True)
    
    follow_up_required = models.BooleanField(default=False)
    follow_up_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['session', 'student']]
        ordering = ['-created_at']
        verbose_name = _('Attendance Record')
        verbose_name_plural = _('Attendance Records')
        indexes = [
            models.Index(fields=['session', 'student']),
            models.Index(fields=['status']),
            models.Index(fields=['student', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.student.admission_number} - {self.get_status_display()} - {self.session.date}"
    
    def clean(self):
        """Validate attendance record"""
        if self.check_out_time and self.check_in_time:
            if self.check_out_time <= self.check_in_time:
                raise ValidationError({'check_out_time': 'Check-out time must be after check-in time'})
        
        # Auto-set status based on times
        if self.check_in_time:
            session_start = timezone.make_aware(
                timezone.datetime.combine(self.session.date, self.session.start_time)
            )
            if self.check_in_time > session_start:
                self.status = self.AttendanceRecordStatusChoices.LATE
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    
    def update_attendance_pattern(self):
        """Update student's attendance pattern"""
        from schools.models import AcademicYear, Term
        try:
            # Get current academic year and term
            current_year = AcademicYear.objects.filter(is_current=True).first()
            current_term = Term.objects.filter(is_current=True).first()
            
            if current_year and current_term:
                pattern, created = AttendancePattern.objects.get_or_create(
                    student=self.student,
                    academic_year=current_year,
                    term=current_term,
                    defaults={
                        'total_sessions': 0,
                        'present_count': 0,
                        'late_count': 0,
                        'absent_count': 0,
                        'excused_count': 0,
                    }
                )
                
                # Update counts
                pattern.total_sessions = AttendanceRecord.objects.filter(
                    student=self.student,
                    session__academic_year=current_year,
                    session__term=current_term
                ).count()
                
                pattern.present_count = AttendanceRecord.objects.filter(
                    student=self.student,
                    status='present',
                    session__date__range=[current_term.start_date, current_term.end_date]
                ).count()
                
                pattern.late_count = AttendanceRecord.objects.filter(
                    student=self.student,
                    status='late',
                    session__date__range=[current_term.start_date, current_term.end_date]
                ).count()
                
                pattern.absent_count = AttendanceRecord.objects.filter(
                    student=self.student,
                    status='absent',
                    session__date__range=[current_term.start_date, current_term.end_date]
                ).count()
                
                pattern.excused_count = AttendanceRecord.objects.filter(
                    student=self.student,
                    status='excused',
                    session__date__range=[current_term.start_date, current_term.end_date]
                ).count()
                
                # Calculate rates
                if pattern.total_sessions > 0:
                    pattern.attendance_rate = (pattern.present_count / pattern.total_sessions) * 100
                    pattern.tardiness_rate = (pattern.late_count / pattern.total_sessions) * 100
                
                pattern.last_updated = timezone.now()
                pattern.save()
                
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating attendance pattern: {e}")


class AttendancePattern(models.Model):
    """Student attendance pattern/statistics"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='attendance_patterns')
    academic_year = models.ForeignKey('schools.AcademicYear', on_delete=models.CASCADE)
    term = models.ForeignKey('schools.Term', on_delete=models.CASCADE)
    total_sessions = models.PositiveIntegerField(default=0)
    present_count = models.PositiveIntegerField(default=0)
    late_count = models.PositiveIntegerField(default=0)
    absent_count = models.PositiveIntegerField(default=0)
    excused_count = models.PositiveIntegerField(default=0)
    attendance_rate = models.DecimalField( max_digits=5, decimal_places=2,  default=0, validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    tardiness_rate = models.DecimalField(max_digits=5,  decimal_places=2, default=0,validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    absent_pattern = models.JSONField(default=dict, blank=True)  # {day: count, time: count}
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['student', 'academic_year', 'term']]
        ordering = ['-attendance_rate']
        verbose_name = _('Attendance Pattern')
        verbose_name_plural = _('Attendance Patterns')
        indexes = [
            models.Index(fields=['student', 'academic_year', 'term']),
            models.Index(fields=['attendance_rate']),
        ]
    
    def __str__(self):
        return f"{self.student.admission_number} - {self.attendance_rate}%"
    
    def update_pattern_analysis(self):
        """Analyze and update absent pattern"""
        try:
            from django.db.models import Count
            from django.db.models.functions import ExtractWeekDay, ExtractHour
            
            # Get absence records for this term
            absences = AttendanceRecord.objects.filter(
                    student=self.student,
                    session__academic_year=self.academic_year,
                    session__term=self.term,
                    status__in=['absent', 'late']
                )

            day_pattern = absences.annotate(
                day=ExtractWeekDay('session__date')
            ).values('day').annotate(count=Count('id')).order_by('-count')
            
            # Analyze by time of day
            time_pattern = absences.annotate(
                hour=ExtractHour('session__start_time')
            ).values('hour').annotate(count=Count('id')).order_by('-count')
            
            self.absent_pattern = {
                'by_day': list(day_pattern),
                'by_time': list(time_pattern),
            }
            self.save()
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating pattern analysis: {e}")