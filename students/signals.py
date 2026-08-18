import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from core.choices.students import StudentStatusChoices
from .models import ParentGuardian, StudentProfile

logger = logging.getLogger(__name__)


def _update_classroom_enrollment(classroom):
    """Safely update a classroom's current_enrollment count."""
    if not classroom:
        return

    try:
        count = classroom.current_students.filter(
            student_status=StudentStatusChoices.ACTIVE
        ).count()
        type(classroom).objects.filter(pk=classroom.pk).update(
            current_enrollment=count
        )
    except Exception as e:
        logger.warning("Failed to update classroom enrollment for %s: %s", classroom, e)


def _update_dormitory_occupancy(dormitory):
    """Safely update a dormitory's occupancy count (if the field exists)."""
    if not dormitory or not hasattr(dormitory, "current_occupancy"):
        return

    try:
        count = dormitory.current_students.filter(
            student_status=StudentStatusChoices.ACTIVE
        ).count()
        type(dormitory).objects.filter(pk=dormitory.pk).update(
            current_occupancy=count
        )
    except Exception as e:
        logger.warning("Failed to update dormitory occupancy for %s: %s", dormitory, e)


# StudentProfile signals
@receiver(pre_save, sender=StudentProfile)
def store_old_values_for_sync(sender, instance: StudentProfile, **kwargs):
    """Store previous class and boarding house for change detection."""
    if not instance.pk:
        instance._old_class = None
        instance._old_boarding_house = None
        return

    try:
        old = StudentProfile.objects.only("current_class", "boarding_house").get(pk=instance.pk)
        instance._old_class = old.current_class
        instance._old_boarding_house = old.boarding_house
    except StudentProfile.DoesNotExist:
        instance._old_class = None
        instance._old_boarding_house = None


@receiver(post_save, sender=StudentProfile)
def sync_classroom_and_dormitory_counts(sender, instance: StudentProfile, **kwargs):
    """Update enrollment / occupancy counts when class or dorm changes."""
    # Current class
    if instance.current_class:
        _update_classroom_enrollment(instance.current_class)

    # Old class (if changed)
    if hasattr(instance, "_old_class") and instance._old_class != instance.current_class:
        _update_classroom_enrollment(instance._old_class)

    # Current dormitory
    if instance.boarding_house:
        _update_dormitory_occupancy(instance.boarding_house)

    # Old dormitory (if changed)
    if (
        hasattr(instance, "_old_boarding_house")
        and instance._old_boarding_house != instance.boarding_house
    ):
        _update_dormitory_occupancy(instance._old_boarding_house)


@receiver(post_delete, sender=StudentProfile)
def cleanup_student_counts(sender, instance: StudentProfile, **kwargs):
    """Clean up counts when a student profile is deleted."""
    if instance.current_class:
        _update_classroom_enrollment(instance.current_class)
    if instance.boarding_house:
        _update_dormitory_occupancy(instance.boarding_house)


@receiver(post_save, sender=StudentProfile)
def invalidate_cached_metrics(sender, instance: StudentProfile, created: bool, **kwargs):
    """Reset cached metrics when important student data changes."""
    if created:
        return

    # Only clear the cached fields – avoid recursion by using update()
    StudentProfile.objects.filter(pk=instance.pk).update(
        attendance_rate=None,
        average_grade=None,
        fee_compliance_rate=None,
    )


# ParentGuardian signals
@receiver(post_save, sender=ParentGuardian)
def ensure_single_primary_guardian(sender, instance: ParentGuardian, **kwargs):
    """
    Ensure only one primary guardian per student.
    Because ParentGuardian ↔ Student is M2M, we handle it carefully.
    """
    if not instance.is_primary:
        return

    # Demote other primary guardians linked to the same students
    for student in instance.students.all():
        ParentGuardian.objects.filter(
            students=student,
            is_primary=True,
        ).exclude(pk=instance.pk).update(is_primary=False)


@receiver(post_save, sender=ParentGuardian)
def sync_primary_guardian_to_emergency_contact(sender, instance: ParentGuardian, **kwargs):
    """
    When a guardian is marked primary, copy their contact info
    into the student's emergency contact fields.
    """
    if not instance.is_primary:
        return

    try:
        for student in instance.students.all():
            StudentProfile.objects.filter(pk=student.pk).update(
                emer_contact_name=instance.user.get_full_name(),
                emer_contact_phone=instance.user.phone or instance.alternate_phone or "",
                emer_contact_relation=instance.get_relationship_display(),
            )
    except Exception as e:
        logger.warning("Failed to sync primary guardian contact: %s", e)


    def _update_school_enrollment(school):
        if not school:
            return
        try:
            count = school.students.filter(
                student_status=StudentStatusChoices.ACTIVE
            ).count()
            type(school).objects.filter(pk=school.pk).update(current_enrollment=count)
        except Exception as e:
            logger.warning("Failed to update school enrollment for %s: %s", school, e)