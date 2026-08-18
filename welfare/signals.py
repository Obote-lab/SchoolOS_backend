import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import CounselingSession, DisciplineIncident, SickBayRecord, WellnessCheck
from core.choices.common import StressLevelChoices

logger = logging.getLogger(__name__)


#  DISCIPLINE INCIDENT
@receiver(pre_save, sender=DisciplineIncident)
def auto_set_incident_defaults(sender, instance, **kwargs):
    """Set default dates and basic fields before save"""
    if not instance.date_reported:
        instance.date_reported = timezone.now()


@receiver(post_save, sender=DisciplineIncident)
def check_recurring_pattern(sender, instance, created, **kwargs):
    """Light check for recurring incidents"""
    if not created:
        return

    try:
        # Quick check for previous similar incidents
        past_count = DisciplineIncident.objects.filter(
            student=instance.student,
            discipline_category=instance.discipline_category,
        ).exclude(id=instance.id).count()

        if past_count >= 2:
            DisciplineIncident.objects.filter(id=instance.id).update(
                recurring_pattern=True
            )
            logger.info(f"Recurring discipline pattern detected for {instance.student.admission_number}")
    except Exception as e:
        logger.error(f"Recurring pattern check failed: {e}")


# SICK BAY
@receiver(pre_save, sender=SickBayRecord)
def set_medical_defaults(sender, instance, **kwargs):
    """Set automatic fields for medical records"""
    if instance.isolation_required and not instance.isolation_end_date:
        instance.isolation_end_date = instance.date.date() + timedelta(days=3)

    # Auto notify parent for serious cases
    if instance.referred_to_hospital or instance.isolation_required:
        instance.parent_notified = True


@receiver(post_save, sender=SickBayRecord)
def log_contagious_case(sender, instance, created, **kwargs):
    """Log contagious cases for quick attention"""
    if created and instance.is_contagious:
        logger.warning(
            f"CONTAGIOUS CASE: {instance.student.admission_number} - {instance.complaint}"
        )


# COUNSELING
@receiver(pre_save, sender=CounselingSession)
def set_counseling_defaults(sender, instance, **kwargs):
    """Auto-set follow-up date if needed"""
    if instance.follow_up_required and not instance.follow_up_date:
        instance.follow_up_date = instance.date.date() + timedelta(days=14)


#  WELLNESS
@receiver(pre_save, sender=WellnessCheck)
def set_wellness_defaults(sender, instance, **kwargs):
    """Auto-set next check date"""
    if instance.follow_up_planned and not instance.next_check_date:
        instance.next_check_date = instance.check_date + timedelta(days=30)


@receiver(post_save, sender=WellnessCheck)
def flag_critical_wellness(sender, instance, created, **kwargs):
    """Flag critical cases"""
    if not created:
        return

    try:
        if instance.academic_stress_level == StressLevelChoices.CRITICAL:
            logger.warning(f"CRITICAL STRESS: {instance.student.admission_number}")

        overall = instance.calculate_overall_score()
        if overall and overall < 4:
            logger.warning(f"LOW WELLNESS SCORE: {instance.student.admission_number} ({overall})")
    except Exception as e:
        logger.error(f"Wellness flagging failed: {e}")