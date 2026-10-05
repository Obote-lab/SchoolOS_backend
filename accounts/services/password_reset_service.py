import logging
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from core.audit import create_audit_log
from core.choices.identity import AuditActionChoices
from ..models import CustomUser
from ..utils import generate_password_reset_token, validate_password_reset_token
from .email_service import EmailService

logger = logging.getLogger(__name__)


class PasswordResetService:
    """
    Handles the secure password reset flow with proper auditing.
    """

    @staticmethod
    def send_password_reset_email(user: CustomUser, request=None) -> bool:
        """
        Generate a reset token and send the password reset email.
        """
        recipient = user.email or user.recovery_email
        if not recipient:
            raise ValueError(f"No email or recovery email configured for user {user.login_id}")

        token = generate_password_reset_token(user)

        success = EmailService.send_password_reset_email(
            user=user,
            token=token,
            request=request,
        )

        if success:
            highest_role = user.get_highest_tier()
            role_name = highest_role.name if highest_role else ""

            create_audit_log(
                actor=user,
                action=AuditActionChoices.REQUEST_RESET,
                model_name="CustomUser",
                record_id=user.id,
                reason="Password reset link requested",
                school=user.school,
                user_ip=request.META.get("REMOTE_ADDR") if request else None,
            )

            logger.info("Password reset email sent to %s", user.login_id)

        return success

    @staticmethod
    def validate_reset_token(token: str) -> CustomUser | None:
        """Validate the token and return the user if valid."""
        user = validate_password_reset_token(token)
        if not user:
            logger.warning("Invalid or expired password reset token used")
        return user

    @staticmethod
    def reset_password(user: CustomUser, new_password: str, request=None) -> CustomUser:
        """
        Reset the user's password, clear lock flags, and audit the action.
        """
        validate_password(new_password, user)

        user.set_password(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_password_change = timezone.now()

        # Clear must-change-password flag
        prefs = user.notification_prefs or {}
        prefs.pop("must_change_password", None)
        user.notification_prefs = prefs

        user.save(
            update_fields=[
                "password",
                "failed_login_attempts",
                "locked_until",
                "last_password_change",
                "notification_prefs",
            ]
        )

        highest_role = user.get_highest_tier()
        role_name = highest_role.name if highest_role else ""

        create_audit_log(
            actor=user,
            action=AuditActionChoices.PASSWORD_RESET,
            model_name="CustomUser",
            record_id=user.id,
            reason="Password successfully reset",
            school=user.school,
            user_ip=request.META.get("REMOTE_ADDR") if request else None,
        )

        # Send confirmation email
        try:
            EmailService.send_password_changed_email(user=user)
        except Exception:
            logger.exception("Failed to send password changed confirmation to %s", user.login_id)

        logger.info("Password reset completed for %s", user.login_id)
        return user