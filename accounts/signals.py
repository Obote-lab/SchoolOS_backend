import logging
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_delete
from django.dispatch import receiver

from core.audit import create_audit_log
from core.choices.identity import AuditActionChoices
from .models import CustomUser, UserRole

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=UserRole)
def reassign_primary_role(sender, instance: UserRole, **kwargs):
    """
    When a primary role assignment is deleted,
    automatically promote the most recently assigned
    active role for the same context (same school or null).
    """
    if not instance.is_primary_role:
        return

    replacement = (
        UserRole.objects.filter(
            user=instance.user,
            school=instance.school,
            is_active=True,
        )
        .exclude(pk=instance.pk)
        .order_by("-assigned_date")
        .first()
    )

    if replacement:
        replacement.is_primary_role = True
        replacement.save(update_fields=["is_primary_role"])

        logger.info(
            "Primary role reassigned to '%s' for user %s",
            replacement.role.name,
            instance.user.login_id,
        )


@receiver(user_logged_in)
def log_successful_login(sender, request, user, **kwargs):
    """
    Reset failed login attempts and create an audit log entry
    after a successful login.
    """
    if user.failed_login_attempts > 0:
        user.failed_login_attempts = 0
        user.save(update_fields=["failed_login_attempts"])

    create_audit_log(
        actor=user,
        action=AuditActionChoices.LOGIN,
        model_name="CustomUser",
        record_id=user.pk,
        school=user.school,
        reason="Successful login",
        new_value=user.login_id,
        request=request,
    )


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    """
    Increment failed login attempts, lock the account if needed,
    and create an audit log entry.
    """
    login_id = credentials.get("login_id") or credentials.get("username")

    if not login_id:
        return

    user = CustomUser.objects.filter(login_id=login_id).first()
    if not user:
        return

    try:
        user.record_failed_login()

        create_audit_log(
            actor=user,
            action=AuditActionChoices.LOGIN_FAILED,
            model_name="CustomUser",
            record_id=user.pk,
            school=user.school,
            reason=f"Failed login attempt #{user.failed_login_attempts}",
            new_value=user.login_id,
            request=request,
        )

    except Exception:
        logger.exception("Failed to process failed login for %s", login_id)