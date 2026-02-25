import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import AcademicYear, School, Term
from accounts.models import AuditLog

logger = logging.getLogger(__name__)


# ── SCHOOL SIGNALS 

@receiver(pre_save, sender=School)
def school_pre_save(sender, instance: School, **kwargs):
    """
    Normalize and validate school data before save.
    Store original status for post-save comparison.
    """
    # Store original status for change detection
    if instance.pk:
        original = School.objects.get(pk=instance.pk)
        instance._original_status = original.onboarding_status
        instance._original_progress = original.onboarding_progress
    else:
        instance._original_status = None
        instance._original_progress = None

    # Auto-generate email if missing
    if not instance.email and instance.school_code:
        safe_code = re.sub(r"[^a-zA-Z0-9]", "-", instance.school_code.lower())
        instance.email = f"info@{safe_code}.school.ac.ke"


@receiver(post_save, sender=School)
def school_post_save(sender, instance: School, created: bool, **kwargs):
    """
    Post-save actions: default settings, audit onboarding changes.
    """
    if created:
        logger.info("School created: %s (%s)", instance.school_name, instance.school_code)

        # Default settings (merge with any existing)
        default_settings = {
            "theme": "default",
            "language": "en",
            "timezone": "Africa/Nairobi",
            "currency": "KES",
            "grading_system": "kcse" if instance.type == School.SchoolTypeChoices.SECONDARY else "knec",
            "fee_structure": "termly",
            "attendance_threshold": 75.0,
            "exam_weight": 60.0,
            "ca_weight": 40.0,
            "late_fee_percentage": 5.0,
            "grace_period_days": 14,
        }

        current = instance.school_settings or {}
        merged = {**default_settings, **current}

        # Safe update without triggering signal recursion
        School.objects.filter(pk=instance.pk).update(school_settings=merged)

        # Audit creation
        AuditLog.objects.create(
            user=instance.created_by,
            action_type="CREATE",
            model_name="School",
            record_id=instance.id,
            new_value=f"School created: {instance.school_name} ({instance.school_code})",
            reason="School onboarded",
            school=instance,
            timestamp=timezone.now()
        )

    else:
        # Audit onboarding status change
        if hasattr(instance, '_original_status') and instance.onboarding_status != instance._original_status:
            AuditLog.objects.create(
                user=instance.last_modified_by or instance.created_by,
                action_type="UPDATE",
                model_name="School",
                record_id=instance.id,
                old_value=f"Status: {instance._original_status} → {instance.onboarding_status}",
                reason="Onboarding status updated",
                school=instance,
                timestamp=timezone.now()
            )


# ── ACADEMIC YEAR SIGNALS 

@receiver(post_save, sender=AcademicYear)
def academic_year_post_save(sender, instance: AcademicYear, created: bool, **kwargs):
    """
    Auto-create terms for new academic years.
    Prevents duplicates on re-save.
    """
    if not created:
        return

    if Term.objects.filter(academic_year=instance).exists():
        logger.info("Terms already exist for %s - skipping creation", instance.year)
        return

    logger.info("Creating %s terms for %s", instance.terms_count, instance.year)

    total_days = (instance.end_date - instance.start_date).days + 1
    term_duration = total_days // max(instance.terms_count, 1)
    today = timezone.now().date()

    for i in range(instance.terms_count):
        term_start = instance.start_date + timezone.timedelta(days=i * term_duration)
        term_end = instance.end_date if i == instance.terms_count - 1 else term_start + timezone.timedelta(days=term_duration - 1)

        status = (
            Term.TermStatusChoices.UPCOMING if today < term_start else
            Term.TermStatusChoices.ACTIVE if term_start <= today <= term_end else
            Term.TermStatusChoices.COMPLETED
        )

        Term.objects.create(
            academic_year=instance,
            name=f"Term {i+1}",
            sequence=i+1,
            start_date=term_start,
            end_date=term_end,
            term_status=status,
        )