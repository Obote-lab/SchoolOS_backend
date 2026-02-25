import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from ..models import AuditLog, CustomUser
from ..utils import generate_password_reset_token, decode_password_reset_token

logger = logging.getLogger(__name__)


class PasswordResetService:
    """Handles secure password reset flow with audit trail"""

    @staticmethod
    def send_password_reset_email(user: CustomUser, request=None):
        """
        Send password reset email + log request
        """
        recipient = user.email or user.recovery_email
        if not recipient:
            raise ValueError("No email or recovery email configured for user")

        token = generate_password_reset_token(user)
        reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password/{token}"

        subject = "SchoolOS - Password Reset Request"
        context = {
            "user": user,
            "full_name": user.get_full_name(),
            "reset_url": reset_url,
            "expiry_hours": 24,
            "support_email": settings.DEFAULT_FROM_EMAIL,
        }

        html = render_to_string("accounts/emails/password_reset.html", context)
        plain = render_to_string("accounts/emails/password_reset.txt", context)

        try:
            send_mail(
                subject=subject,
                message=plain,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                html_message=html,
                fail_silently=False,
            )

            # Audit log
            AuditLog.objects.create(
                user=user,
                action_type="REQUEST_RESET",
                model_name="CustomUser",
                record_id=user.id,
                reason="Password reset link requested",
                school=user.school,
                user_ip=request.META.get('REMOTE_ADDR') if request else None,
                timestamp=timezone.now()
            )

            logger.info(f"Password reset email sent to {user.login_id}")
            return True

        except Exception as e:
            logger.error(f"Password reset email failed for {user.login_id}: {e}")
            raise

    @staticmethod
    def validate_reset_token(token: str) -> CustomUser | None:
        """Validate token and return user"""
        user = decode_password_reset_token(token)
        if not user:
            logger.warning(f"Invalid/expired password reset token used")
            return None
        return user

    @staticmethod
    def reset_password(user: CustomUser, new_password: str, request=None):
        """Reset password + audit + send confirmation + force change flag off"""
        from django.contrib.auth.password_validation import validate_password

        validate_password(new_password, user)

        user.set_password(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_password_change = timezone.now()

        # Clear must-change flag
        prefs = user.notification_prefs or {}
        prefs.pop("must_change_password", None)
        user.notification_prefs = prefs

        user.save(update_fields=[
            "password", "failed_login_attempts", "locked_until",
            "last_password_change", "notification_prefs"
        ])

        # Audit log
        AuditLog.objects.create(
            user=user,
            action_type="PASSWORD_RESET",
            model_name="CustomUser",
            record_id=user.id,
            reason="Password successfully reset",
            school=user.school,
            user_ip=request.META.get('REMOTE_ADDR') if request else None,
            timestamp=timezone.now()
        )

        # Confirmation email
        PasswordResetService._send_password_changed_email(user)

        logger.info(f"Password reset completed for {user.login_id}")
        return user

    @staticmethod
    def _send_password_changed_email(user: CustomUser):
        """Confirmation email after successful reset"""
        recipient = user.email or user.recovery_email
        if not recipient:
            return

        subject = "SchoolOS - Your Password Has Been Changed"
        context = {
            "user": user,
            "changed_at": timezone.now(),
            "support_email": settings.DEFAULT_FROM_EMAIL,
        }

        html = render_to_string("accounts/emails/password_changed.html", context)
        plain = render_to_string("accounts/emails/password_changed.txt", context)

        try:
            send_mail(
                subject=subject,
                message=plain,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                html_message=html,
                fail_silently=True,
            )
        except Exception as e:
            logger.warning(f"Password changed confirmation email failed for {user.login_id}: {e}")