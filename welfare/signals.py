from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import DisciplineIncident, SickBayRecord, CounselingSession, WellnessCheck
import logging

logger = logging.getLogger(__name__)


#  DISCIPLINE INCIDENT SIGNALS 
@receiver(pre_save, sender=DisciplineIncident)
def auto_set_incident_status(sender, instance, **kwargs):
    """Auto-set incident status and dates"""
    try: 
        # Auto-set date_reported if not provided
        if not instance.date_reported:
            instance.date_reported = timezone.now()
            
    except Exception as e:
        logger.error(f"Error setting incident status: {e}")


@receiver(post_save, sender=DisciplineIncident)
def check_for_recurring_pattern(sender, instance, created, **kwargs):
    """Check if student has recurring discipline pattern"""
    try:
        if created:
            # Get student's past incidents
            past_incidents = DisciplineIncident.objects.filter(
                student=instance.student,
                discipline_category=instance.discipline_category,
            ).exclude(id=instance.id)
            
            if past_incidents.count() >= 2:
                DisciplineIncident.objects.filter(id=instance.id).update(
                    recurring_pattern=True)
                logger.info(f"Recurring pattern detected for {instance.student.admission_number}")
                
    except Exception as e:
        logger.error(f"Error checking recurring pattern: {e}")


#  SICK BAY RECORD SIGNALS 
@receiver(pre_save, sender=SickBayRecord)
def validate_medical_data(sender, instance, **kwargs):
    """Validate sick bay record data"""
    try:
        # Auto-set isolation end date if required
        if instance.isolation_required and not instance.isolation_end_date:
            instance.isolation_end_date = instance.date.date() + timezone.timedelta(days=3)
            
        # Auto-notify parent for serious cases
        if instance.referred_to_hospital or instance.isolation_required:
            instance.parent_notified = True
            
    except Exception as e:
        logger.error(f"Error validating medical data: {e}")


@receiver(post_save, sender=SickBayRecord)
def update_student_health_status(sender, instance, created, **kwargs):
    """Update student's health status"""
    try:
        if created and instance.is_contagious:
            # Log contagious case
            logger.warning(f"Contagious case: {instance.student.admission_number} - {instance.complaint}")
            
            # TODO: In real app, would notify relevant staff
            
    except Exception as e:
        logger.error(f"Error updating health status: {e}")


#  COUNSELING SESSION SIGNALS 
@receiver(pre_save, sender=CounselingSession)
def validate_counseling_session(sender, instance, **kwargs):
    """Validate counseling session"""
    try:
        # Auto-set follow-up date if required
        if instance.follow_up_required and not instance.follow_up_date:
            instance.follow_up_date = instance.date.date() + timezone.timedelta(days=14)
    except Exception as e:
        logger.error(f"Error validating counseling session: {e}")


#  WELLNESS CHECK SIGNALS 
@receiver(pre_save, sender=WellnessCheck)
def calculate_wellness_scores(sender, instance, **kwargs):
    """Calculate wellness scores"""
    try:
        # Auto-set next check date
        if instance.follow_up_planned and not instance.next_check_date:
            instance.next_check_date = instance.check_date + timezone.timedelta(days=30)
            
    except Exception as e:
        logger.error(f"Error calculating wellness scores: {e}")


@receiver(post_save, sender=WellnessCheck)
def flag_critical_wellness(sender, instance, created, **kwargs):
    """Flag critical wellness issues"""
    try:
        if created:
            # Check for critical stress levels
            if instance.academic_stress_level == 'critical':
                logger.warning(f"Critical stress level: {instance.student.admission_number}")
                
            # Check for low wellness scores
            overall = instance.calculate_overall_score()
            if overall and overall < 4:
                logger.warning(f"Low wellness score: {instance.student.admission_number} - {overall}")
                
    except Exception as e:
        logger.error(f"Error flagging critical wellness: {e}")