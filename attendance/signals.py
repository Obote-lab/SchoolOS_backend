from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import AttendanceRecord, AttendancePattern
from students.models import Student
import logging

logger = logging.getLogger(__name__)


#  ATTENDANCE RECORD SIGNALS 
@receiver(pre_save, sender=AttendanceRecord)
def auto_set_status(sender, instance, **kwargs):
    """Auto-set status based on check-in time"""
    try:
        if instance.check_in_time and instance.session:
            # Check if late (after session start + 15 minutes grace)
            session_start = timezone.make_aware(
                timezone.datetime.combine(
                    instance.session.date, 
                    instance.session.start_time
                )
            )
            grace_period = timezone.timedelta(minutes=15)
            
            if instance.check_in_time > session_start + grace_period:
                instance.status = 'late'
            elif instance.status in ['absent', 'excused', 'sick']:
                # Keep existing status if already set
                pass
            else:
                instance.status = 'present'
                
    except Exception as e:
        logger.error(f"Error auto-setting status: {e}")


@receiver(post_save, sender=AttendanceRecord)
def notify_parent_if_absent(sender, instance, created, **kwargs):
    """Notify parent if student is absent"""
    try:
        if instance.status in ['absent', 'sick'] and not instance.parent_notified:
            # Log notification (in real app, would send SMS/email)
            logger.info(
                f"Parent notification needed for {instance.student.admission_number} "
                f"on {instance.session.date} - {instance.status}"
            )
            
    except Exception as e:
        logger.error(f"Error in parent notification: {e}")


@receiver(post_delete, sender=AttendanceRecord)
def cleanup_after_delete(sender, instance, **kwargs):
    """Clean up after attendance record deletion"""
    try:
        # Update session count
        if instance.session:
            instance.session.save()
            
    except Exception as e:
        logger.error(f"Error cleaning up after delete: {e}")


#  ATTENDANCE PATTERN SIGNALS 
@receiver(post_save, sender=AttendancePattern)
def analyze_absent_pattern(sender, instance, created, **kwargs):
    """Analyze and update absent patterns"""
    try:
        if created or kwargs.get('update_fields') is None:
            instance.update_pattern_analysis()
            
    except Exception as e:
        logger.error(f"Error analyzing absent pattern: {e}")


#  STUDENT SIGNALS 
@receiver(post_save, sender=Student)
def create_attendance_pattern(sender, instance, created, **kwargs):
    """Create attendance pattern for new student"""
    try:
        if created:
            from schools.models import AcademicYear, Term
            current_year = AcademicYear.objects.filter(is_current=True).first()
            current_term = Term.objects.filter(is_current=True).first()
            
            if current_year and current_term:
                AttendancePattern.objects.get_or_create(
                    student=instance,
                    academic_year=current_year,
                    term=current_term,
                    defaults={
                        'total_sessions': 0,
                        'present_count': 0,
                        'late_count': 0,
                        'absent_count': 0,
                        'excused_count': 0,
                        'attendance_rate': 0,
                        'tardiness_rate': 0,
                    }
                )
                
    except Exception as e:
        logger.error(f"Error creating attendance pattern: {e}")