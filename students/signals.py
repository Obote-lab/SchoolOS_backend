import logging
from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from schools.models import ClassRoom

from .models import ParentGuardian, Student

logger = logging.getLogger(__name__)


def _update_related_count(related_instance, related_field_name, count_field_name):
    """
    Generic helper to update a denormalized count field on a related model.
    
    Example:
        _update_related_count(student.current_class, 'students', 'current_enrollment')
    """
    if not related_instance:
        return

    try:
        with transaction.atomic():
            count = related_instance.__class__.objects.filter(
                **{related_field_name: related_instance},
                student_status=Student.StudentStatusChoices.ACTIVE
            ).count()

            related_instance.__class__.objects.filter(
                pk=related_instance.pk
            ).update(**{count_field_name: count})

    except Exception as e:
        logger.warning(
            f"Failed to update {related_instance.__class__.__name__}.{count_field_name}: {e}",
            exc_info=True
        )


#  Student → ClassRoom enrollment sync
@receiver(post_save, sender=Student)
def sync_classroom_enrollment(sender, instance: Student, **kwargs):
    """
    Update ClassRoom.current_enrollment when a student's class changes
    or status changes.
    """
    # Only care about active students or status changes
    if kwargs.get('created') or instance.student_status != Student.StudentStatusChoices.ACTIVE:
        _update_related_count(instance.current_class, 'students', 'current_enrollment')

    # If class changed, update old class too
    if hasattr(instance, '_old_class') and instance._old_class != instance.current_class:
        _update_related_count(instance._old_class, 'students', 'current_enrollment')


@receiver(post_delete, sender=Student)
def decrement_classroom_enrollment(sender, instance: Student, **kwargs):
    """Decrease count when student is deleted."""
    _update_related_count(instance.current_class, 'students', 'current_enrollment')



#  Student → Dormitory occupancy sync (optional)
def get_dormitory_model():
    try:
        return apps.get_model("dormitory", "Dormitory")
    except LookupError:
        return None


@receiver(post_save, sender=Student)
def sync_dormitory_occupancy(sender, instance: Student, **kwargs):
    """
    Keep Dormitory.current_occupancy in sync (if dormitory app is installed).
    """
    Dormitory = get_dormitory_model()
    if not Dormitory:
        return

    old_house = getattr(instance, '_old_boarding_house', None)
    new_house = instance.boarding_house
    if new_house:
        _update_related_count(new_house, 'students', 'current_occupancy')
    if old_house and old_house != new_house:
        _update_related_count(old_house, 'students', 'current_occupancy')


@receiver(post_delete, sender=Student)
def decrement_dormitory_occupancy(sender, instance: Student, **kwargs):
    Dormitory = get_dormitory_model()
    if not Dormitory or not instance.boarding_house:
        return
    _update_related_count(instance.boarding_house, 'students', 'current_occupancy')



#  ParentGuardian → Student emergency contact sync
@receiver(post_save, sender=ParentGuardian)
def sync_primary_guardian_to_student(sender, instance: ParentGuardian, **kwargs):
    """
    When a primary guardian is saved, sync their details to student's emergency contact.
    Also ensure only one primary guardian per student.
    """
    if not instance.is_primary or not instance.student:
        return

    # Demote any other primary guardians
    ParentGuardian.objects.filter(
        student=instance.student,
        is_primary=True
    ).exclude(pk=instance.pk).update(is_primary=False)

    # Sync emergency contact info
    try:
        Student.objects.filter(pk=instance.student.pk).update(
            emer_contact_name=instance.user.get_full_name(),
            emer_contact_phone=getattr(instance.user, 'phone', instance.alternate_phone or ''),
            emer_contact_relation=instance.relationship,
        )
    except Exception as e:
        logger.warning(f"Failed to sync primary guardian to student {instance.student}: {e}")


#  Track old values for change detection (pre_save)
@receiver(pre_save, sender=Student)
def store_old_class_and_dorm(sender, instance: Student, **kwargs):
    """
    Store previous class and dormitory so we can update counts correctly
    when they change.
    """
    if instance.pk:
        old = Student.objects.get(pk=instance.pk)
        instance._old_class = old.current_class
        instance._old_boarding_house = old.boarding_house
    else:
        instance._old_class = None
        instance._old_boarding_house = None