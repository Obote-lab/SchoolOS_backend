import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from core.audit import create_audit_log
from core.choices.identity import AuditActionChoices  # single source
from core.choices.academic import TermNameChoices, TermStatusChoices
from core.choices.schools import SchoolTypeChoices
from .models import AcademicYear, School, Term

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=School)
def school_pre_save(sender, instance: School, **kwargs):
    """Store original onboarding status for change detection."""
    if instance.pk:
        try:
            original = School.objects.only(
                "onboarding_status", "onboarding_progress"
            ).get(pk=instance.pk)
            instance._original_status = original.onboarding_status
            instance._original_progress = original.onboarding_progress
        except School.DoesNotExist:
            instance._original_status = None
    else:
        instance._original_status = None


@receiver(post_save, sender=School)
def school_post_save(sender, instance: School, created: bool, **kwargs):
    if created:
        default_settings = {
            "theme": "default",
            "language": "en",
            "timezone": "Africa/Nairobi",
            "currency": "KES",
            "grading_system": (
                "kcse"
                if instance.school_type == SchoolTypeChoices.SECONDARY
                else "knec"
            ),
            "fee_structure": "termly",
            "attendance_threshold": 75.0,
            "exam_weight": 60.0,
            "ca_weight": 40.0,
        }

        School.objects.filter(pk=instance.pk).update(
            school_settings={**default_settings, **(instance.school_settings or {})}
        )

        create_audit_log(
            actor=instance.created_by,
            action=AuditActionChoices.CREATE,
            model_name="School",
            record_id=instance.id,
            school=instance,
            reason="School onboarding started",
            new_value=f"School created: {instance.school_name}",
        )
        return

    # Status-change audit only
    if (
        hasattr(instance, "_original_status")
        and instance._original_status is not None
        and instance.onboarding_status != instance._original_status
    ):
        actor = instance.last_modified_by or instance.created_by

        create_audit_log(
            actor=actor,
            action=AuditActionChoices.UPDATE,
            model_name="School",
            record_id=instance.id,
            school=instance,
            reason="Onboarding status updated",
            old_value=str(instance._original_status),
            new_value=str(instance.onboarding_status),
        )


@receiver(post_save, sender=AcademicYear)
def academic_year_post_save(sender, instance: AcademicYear, created: bool, **kwargs):
    """Automatically create terms when a new AcademicYear is created."""
    if not created:
        return

    if Term.objects.filter(academic_year=instance).exists():
        logger.info(
            "Terms already exist for %s – skipping auto-creation", instance.year
        )
        return

    logger.info(
        "Creating %s terms for academic year %s",
        instance.terms_count,
        instance.year,
    )

    total_days = (instance.end_date - instance.start_date).days + 1
    term_duration = total_days // max(instance.terms_count, 1)
    today = timezone.now().date()

    term_name_map = {
        1: TermNameChoices.TERM_1,
        2: TermNameChoices.TERM_2,
        3: TermNameChoices.TERM_3,
        4: TermNameChoices.TERM_4,
    }

    for i in range(instance.terms_count):
        sequence = i + 1
        term_start = instance.start_date + timezone.timedelta(days=i * term_duration)

        if sequence == instance.terms_count:
            term_end = instance.end_date
        else:
            term_end = term_start + timezone.timedelta(days=term_duration - 1)

        if today < term_start:
            status = TermStatusChoices.UPCOMING
        elif term_start <= today <= term_end:
            status = TermStatusChoices.ACTIVE
        else:
            status = TermStatusChoices.COMPLETED

        Term.objects.create(
            academic_year=instance,
            name=term_name_map.get(sequence, TermNameChoices.TERM_1),
            sequence=sequence,
            start_date=term_start,
            end_date=term_end,
            term_status=status,
        )

    logger.info(
        "Successfully created %s terms for %s",
        instance.terms_count,
        instance.year,
    )