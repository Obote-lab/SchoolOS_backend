import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from accounts.models import Role, UserRole
from core.choices.staff import StaffAttendanceStatusChoices, StaffTypeChoices
from .models import StaffAttendance, StaffProfile

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# StaffProfile signals
# ------------------------------------------------------------------
@receiver(post_save, sender=StaffProfile)
def sync_user_active_status(sender, instance: StaffProfile, **kwargs):
    """Keep CustomUser.is_active in sync with StaffProfile.is_active."""
    try:
        if instance.user.is_active != instance.is_active:
            instance.user.is_active = instance.is_active
            instance.user.save(update_fields=["is_active"])
            action = "activated" if instance.is_active else "deactivated"
            logger.info(
                "User %s %s due to staff profile change",
                instance.user.login_id,
                action,
            )
    except Exception as e:
        logger.error(
            "Failed to sync user active status for staff %s: %s",
            instance.staff_id,
            e,
        )


@receiver(post_save, sender=StaffProfile)
def assign_default_role(sender, instance: StaffProfile, created: bool, **kwargs):
    """
    Automatically assign an appropriate role when a new staff profile is created.
    """
    if not created:
        return

    # Map staff_type → role name
    role_mapping = {
        StaffTypeChoices.TEACHER: "Teacher",
        StaffTypeChoices.PRINCIPAL: "Principal",
        StaffTypeChoices.DEPUTY: "Deputy Principal",
        StaffTypeChoices.HOD: "Head of Department",
        StaffTypeChoices.ADMIN: "Administrator",
        StaffTypeChoices.MATRON: "Matron",
        StaffTypeChoices.SECURITY: "Security Officer",
        StaffTypeChoices.DRIVER: "Driver",
        StaffTypeChoices.COOK: "Cook",
        StaffTypeChoices.NURSE: "Nurse",
        StaffTypeChoices.LIBRARIAN: "Librarian",
        StaffTypeChoices.LAB_TECH: "Lab Technician",
        StaffTypeChoices.OTHER: "Support Staff",
    }

    role_name = role_mapping.get(instance.staff_type, "Support Staff")

    try:
        with transaction.atomic():
            role, _ = Role.objects.get_or_create(
                name=role_name,
                defaults={
                    "role_category": "academic" if instance.is_teacher else "support",
                    "description": f"Default role for {role_name}",
                    "access_level": "school",
                },
            )

            # Avoid duplicate primary roles
            UserRole.objects.get_or_create(
                user=instance.user,
                role=role,
                school=instance.school,
                defaults={
                    "is_primary_role": True,
                    "assigned_by": instance.user,
                    "assigned_date": timezone.now(),
                    "is_active": True,
                },
            )

            logger.info(
                "Assigned role '%s' to staff %s",
                role_name,
                instance.staff_id,
            )

    except Exception as e:
        logger.error(
            "Failed to assign role to staff %s: %s",
            instance.staff_id,
            e,
        )


@receiver(post_delete, sender=StaffProfile)
def deactivate_user_on_staff_delete(sender, instance: StaffProfile, **kwargs):
    """Deactivate the linked user when a staff profile is deleted."""
    try:
        if instance.user.is_active:
            instance.user.is_active = False
            instance.user.save(update_fields=["is_active"])
            logger.info(
                "Deactivated user %s after staff profile deletion",
                instance.user.login_id,
            )
    except Exception as e:
        logger.error("Failed to deactivate user on staff delete: %s", e)


# ------------------------------------------------------------------
# StaffAttendance signals
# ------------------------------------------------------------------
@receiver(pre_save, sender=StaffAttendance)
def normalize_attendance_data(sender, instance: StaffAttendance, **kwargs):
    """Optional cleanup before saving attendance."""
    # Example: clear notes when status is not leave
    if instance.status != StaffAttendanceStatusChoices.LEAVE:
        # Keep notes if you prefer – currently we leave them as-is
        pass


@receiver(post_save, sender=StaffAttendance)
def log_attendance_created_or_updated(sender, instance: StaffAttendance, created: bool, **kwargs):
    action = "created" if created else "updated"
    logger.info(
        "Attendance record %s for %s on %s (%s)",
        action,
        instance.staff.staff_id,
        instance.date,
        instance.get_status_display(),
    )


@receiver(post_delete, sender=StaffAttendance)
def log_attendance_deleted(sender, instance: StaffAttendance, **kwargs):
    logger.info(
        "Attendance record deleted for %s on %s",
        instance.staff.staff_id,
        instance.date,
    )


# ------------------------------------------------------------------
# Cached metrics
# ------------------------------------------------------------------
@receiver(post_save, sender=StaffProfile)
def invalidate_staff_cached_metrics(sender, instance: StaffProfile, created: bool, **kwargs):
    """
    Reset cached performance/attendance metrics when core data changes.
    """
    if created:
        return

    # Use update() to avoid recursion
    StaffProfile.objects.filter(pk=instance.pk).update(
        performance_score=None,
        attendance_rate=None,
    )