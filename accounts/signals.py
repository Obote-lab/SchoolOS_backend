import logging
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth.signals import user_logged_in, user_login_failed
from .models import CustomUser, UserRole, AuditLog

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CustomUser)
def log_user_creation_or_update(sender, instance: CustomUser, created: bool, **kwargs):
    """
    Audit user creation and important updates.
    """
    if created:
        if instance.notification_prefs is None and not instance.is_system_root:
            CustomUser.objects.filter(pk=instance.pk).update(
                notification_prefs={
                    "email": True,
                    "sms": True,
                    "push": True,
                    "whatsapp": False,
                    "must_change_password": True,
                }
            )

        # Audit creation
        AuditLog.objects.create(
            user=instance.created_by if hasattr(instance, 'created_by') and instance.created_by else None,
            action_type="CREATE",
            model_name="CustomUser",
            record_id=instance.id,
            new_value=f"User created: {instance.login_id} ({instance.get_full_name()}) - Type: {instance.user_type}",
            reason="New user registration",
            school=instance.school,
            timestamp=timezone.now()
        )
    else:
        # Optional: log updates only for sensitive fields (you can expand later)
        pass


@receiver(post_save, sender=UserRole)
def log_user_role_change(sender, instance: UserRole, created: bool, **kwargs):
    """
    Audit role assignment (create/update)
    """
    action = "CREATE" if created else "UPDATE"
    value = f"{instance.role.name} assigned to {instance.user.login_id} at {instance.school.school_name if instance.school else 'County/National'}"
    if not created:
        value += f" (is_primary: {instance.is_primary_role}, valid_until: {instance.valid_until})"

    AuditLog.objects.create(
        user=instance.assigned_by,
        action_type=action,
        model_name="UserRole",
        record_id=instance.id,
        new_value=value,
        reason="Role assignment" if created else "Role update",
        school=instance.school,
        timestamp=timezone.now()
    )


@receiver(post_delete, sender=UserRole)
def log_user_role_deletion_and_reassign(sender, instance: UserRole, **kwargs):
    """
    Log role removal + handle primary role reassignment
    """
    logger.warning(f"Role {instance.role.name} removed from {instance.user.login_id} (was primary: {instance.is_primary_role})")

    # Audit deletion
    AuditLog.objects.create(
        user=instance.assigned_by,
        action_type="DELETE",
        model_name="UserRole",
        record_id=instance.id,
        old_value=f"{instance.role.name} at {instance.school.school_name if instance.school else 'County/National'}",
        reason="Role assignment revoked",
        school=instance.school,
        timestamp=timezone.now()
    )

    # Reassign primary role if needed
    if instance.is_primary_role:
        other_roles = UserRole.objects.filter(
            user=instance.user,
            school=instance.school,
            is_active=True
        ).exclude(id=instance.id)

        if other_roles.exists():
            new_primary = other_roles.order_by("-assigned_date").first()
            new_primary.is_primary_role = True
            new_primary.save(update_fields=["is_primary_role"])

            logger.info(f"Reassigned primary role to {new_primary.role.name} for user {instance.user.login_id}")

            # Audit reassignment
            AuditLog.objects.create(
                user=new_primary.assigned_by,
                action_type="UPDATE",
                model_name="UserRole",
                record_id=new_primary.id,
                new_value=f"Set as primary role after deletion of previous primary ({instance.role.name})",
                reason="Automatic primary role reassignment",
                school=instance.school,
                timestamp=timezone.now()
            )


@receiver(user_logged_in)
def log_successful_login(sender, request, user, **kwargs):
    """Log successful login with IP and current roles"""
    current_roles = ", ".join([r.role.name for r in user.user_roles.filter(is_active=True)])
    AuditLog.objects.create(
        user=user,
        action_type="LOGIN",
        model_name="CustomUser",
        record_id=user.id,
        new_value=f"Successful login - Roles: {current_roles}",
        reason="User logged in",
        school=user.school,
        user_ip=request.META.get('REMOTE_ADDR'),
        timestamp=timezone.now()
    )


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    """Log failed login attempt"""
    login_id = credentials.get('login_id', 'unknown')
    try:
        user = CustomUser.objects.filter(login_id=login_id).first()
        if user:
            user.record_failed_login()
            AuditLog.objects.create(
                user=user,
                action_type="LOGIN_FAILED",
                model_name="CustomUser",
                record_id=user.id,
                reason=f"Failed login attempt #{user.failed_login_attempts}",
                school=user.school,
                user_ip=request.META.get('REMOTE_ADDR') if request else None,
                timestamp=timezone.now()
            )
    except Exception as e:
        logger.error(f"Failed to log login failure for {login_id}: {e}")