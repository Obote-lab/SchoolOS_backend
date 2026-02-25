import logging
from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from accounts.models import Role, UserRole
from .models import StaffProfile, StaffAttendance

logger = logging.getLogger(__name__)


#  StaffProfile Signals
@receiver(post_save, sender=StaffProfile)
def sync_user_active_status(sender, instance: StaffProfile, created: bool, **kwargs):
    """
    Keep user.is_active in sync with staff.is_active
    """
    try:
        if instance.user.is_active != instance.is_active:
            instance.user.is_active = instance.is_active
            instance.user.save(update_fields=["is_active"])
            action = "activated" if instance.is_active else "deactivated"
            logger.info(f"User {instance.user.email} {action} due to staff profile change")
    except Exception as e:
        logger.error(f"Failed to sync user active status for staff {instance.staff_id}: {e}")


@receiver(post_save, sender=StaffProfile)
def assign_default_role(sender, instance: StaffProfile, created: bool, **kwargs):
    """
    Assign appropriate role when a new staff profile is created
    """
    if not created:
        return

    try:
        with transaction.atomic():
            # Map staff_type → role name
            role_mapping = {
                "teacher": "Teacher",
                "principal": "Principal",
                "deputy_principal": "Deputy Principal",
                "hod": "Head of Department",
                "admin": "Administrator",
                # Add more mappings as needed
            }

            role_name = role_mapping.get(instance.staff_type, "Staff Member")

            # Get or create the role
            role, _ = Role.objects.get_or_create(
                name=role_name,
                defaults={
                    "category": "Academic" if "teacher" in instance.staff_type else "Administrative",
                    "description": f"Default role for {role_name}",
                    "access_level": "School",
                }
            )

            # Assign role to user in this school
            UserRole.objects.get_or_create(
                user=instance.user,
                role=role,
                school=instance.school,
                defaults={
                    "is_primary_role": True,
                    "assigned_by": instance.user,  # or request.user if available
                    "assigned_date": timezone.now(),
                }
            )

            logger.info(f"Assigned role '{role_name}' to staff {instance.staff_id}")

    except Exception as e:
        logger.error(f"Failed to assign role to staff {instance.staff_id}: {e}")


@receiver(post_delete, sender=StaffProfile)
def deactivate_user_on_staff_delete(sender, instance: StaffProfile, **kwargs):
    """
    Deactivate linked user when staff profile is deleted
    """
    try:
        if instance.user.is_active:
            instance.user.is_active = False
            instance.user.save(update_fields=["is_active"])
            logger.info(f"Deactivated user {instance.user.email} after staff profile deletion")
    except Exception as e:
        logger.error(f"Failed to deactivate user on staff delete: {e}")



#  StaffAttendance Signals
@receiver(pre_save, sender=StaffAttendance)
def normalize_attendance_data(sender, instance: StaffAttendance, **kwargs):
    """
    Clean/normalize attendance before save (e.g. clear leave_type if not on leave)
    """
    if instance.status != StaffAttendance.StatusChoices.LEAVE:
        instance.leave_type = ""

    if not instance.status:
        instance.status = StaffAttendance.StatusChoices.PRESENT


@receiver(post_save, sender=StaffAttendance)
@receiver(post_delete, sender=StaffAttendance)
def log_attendance_change(sender, instance: StaffAttendance, **kwargs):
    """
    Simple logging of attendance changes (useful for audit trail)
    """
    action = "created" if kwargs.get("created") else "updated" if "post_save" in str(sender) else "deleted"
    logger.info(f"Attendance record {action} for {instance.staff.staff_id} on {instance.date}")