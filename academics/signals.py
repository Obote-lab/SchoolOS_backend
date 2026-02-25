import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Exam, Subject, SubjectAssignment

logger = logging.getLogger(__name__)



#  Exam Signals
@receiver(pre_save, sender=Exam)
def auto_update_exam_status(sender, instance: Exam, **kwargs):
    """
    Automatically adjust exam status based on current date.
    - Scheduled → if exam date is in future
    - In Progress → if today is exam date
    - Completed → if exam date passed
    """
    today = timezone.now().date()

    if instance.exam_date > today:
        instance.exam_status = Exam.StatusChoices.SCHEDULED
    elif instance.exam_date == today:
        instance.exam_status = Exam.StatusChoices.IN_PROGRESS
    else:
        instance.exam_status = Exam.StatusChoices.COMPLETED


@receiver(post_save, sender=Exam)
def log_exam_change(sender, instance: Exam, created: bool, **kwargs):
    """
    Simple audit logging for exam creation/update
    """
    action = "created" if created else "updated"
    logger.info(
        f"Exam {action}: {instance.name} ({instance.exam_date}) "
        f"Status: {instance.get_exam_status_display()} "
        f"(School: {instance.school_id})"
    )



#  Subject & Assignment Signals
@receiver(post_save, sender=Subject)
def log_subject_creation(sender, instance: Subject, created: bool, **kwargs):
    """
    Log when new subjects are created (useful for audit)
    """
    if created:
        logger.info(
            f"New subject created: {instance.subject_code} - {instance.subject_name} "
            f"(School: {instance.school_id})"
        )


@receiver(pre_save, sender=SubjectAssignment)
def validate_assignment_dates(sender, instance: SubjectAssignment, **kwargs):
    """
    Basic validation for assignment dates (if term/academic year added later)
    """
    # No date fields now → placeholder for future
    pass