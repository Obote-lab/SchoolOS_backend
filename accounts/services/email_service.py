import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from core.audit import create_audit_log
from core.choices.identity import AuditActionChoices
from ..models import AuditLog, CustomUser, Role

logger = logging.getLogger(__name__)


class EmailService:
    """
    Centralized email service for SchoolOS.

    This is the ONLY class responsible for sending emails.
    """

    @staticmethod
    def _send_email(
        *,
        subject: str,
        recipient: str,
        html_template: str,
        text_template: str,
        context: dict,
        audit_user: CustomUser | None = None,
        audit_action: str | None = None,
        audit_message: str | None = None,
    ) -> bool:
        """Internal reusable email sender."""
        try:
            html_message = render_to_string(html_template, context)
            text_message = render_to_string(text_template, context)

            # TODO: Move to Celery later
            send_mail(
                subject=subject,
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                html_message=html_message,
                fail_silently=False,
            )

            if audit_user and audit_action:
                highest_role = audit_user.get_highest_tier()
                role_name = highest_role.name if highest_role else ""
                create_audit_log(
                        actor=audit_user,
                        action=audit_action,
                        model_name="CustomUser",
                        record_id=audit_user.id,
                        new_value=audit_message or "",
                        school=getattr(audit_user, "school", None),
                        reason=audit_message or "Email notification sent",
                    )

            logger.info("Email sent successfully to %s", recipient)
            return True

        except Exception:
            logger.exception("Failed sending email to %s", recipient)
            return False


    # Welcome
    @classmethod
    def send_welcome_email(cls, user: CustomUser) -> bool:
        recipient = user.email or user.recovery_email
        if not recipient or not user.get_notification_pref("email"):
            return False

        context = {
            "user": user,
            "full_name": user.get_full_name(),
            "school": user.school.school_name if user.school else "SchoolOS",
            "login_id": user.login_id,
            "login_url": f"{settings.FRONTEND_URL.rstrip('/')}/login",
            "support_email": settings.DEFAULT_FROM_EMAIL,
        }

        return cls._send_email(
            subject="Welcome to SchoolOS",
            recipient=recipient,
            html_template="accounts/emails/welcome.html",
            text_template="accounts/emails/welcome.txt",
            context=context,
            audit_user=user,
            audit_action=AuditActionChoices.NOTIFY,
            audit_message="Welcome email sent.",
        )

    # Password Reset
    @classmethod
    def send_password_reset_email(cls, *, user: CustomUser, token: str, request=None) -> bool:
        recipient = user.email or user.recovery_email
        if not recipient or not user.get_notification_pref("email"):
            return False

        reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password/{token}"

        context = {
            "user": user,
            "full_name": user.get_full_name(),
            "reset_url": reset_url,
            "expires_hours": 24,
            "support_email": settings.DEFAULT_FROM_EMAIL,
        }

        return cls._send_email(
            subject="SchoolOS - Password Reset Request",
            recipient=recipient,
            html_template="accounts/emails/password_reset.html",
            text_template="accounts/emails/password_reset.txt",
            context=context,
            audit_user=user,
            audit_action=AuditActionChoices.REQUEST_RESET,
            audit_message="Password reset email sent.",
        )

    @classmethod
    def send_password_changed_email(cls, *, user: CustomUser) -> bool:
        recipient = user.email or user.recovery_email
        if not recipient or not user.get_notification_pref("email"):
            return False

        context = {
            "user": user,
            "full_name": user.get_full_name(),
            "changed_at": timezone.now(),
            "support_email": settings.DEFAULT_FROM_EMAIL,
        }

        return cls._send_email(
            subject="Your SchoolOS Password Has Been Changed",
            recipient=recipient,
            html_template="accounts/emails/password_changed.html",
            text_template="accounts/emails/password_changed.txt",
            context=context,
            audit_user=user,
            audit_action=AuditActionChoices.NOTIFY,
            audit_message="Password changed confirmation email sent.",
        )

    # Role Notifications
    @classmethod
    def send_role_assignment_email(cls, *, actor: CustomUser, user: CustomUser, role: Role) -> bool:
        recipient = user.email or user.recovery_email
        if not recipient or not user.get_notification_pref("email"):
            return False

        context = {
            "actor": actor,
            "user": user,
            "full_name": user.get_full_name(),
            "role": role,
            "school": user.school,
        }

        return cls._send_email(
            subject="Your SchoolOS Role Has Been Updated",
            recipient=recipient,
            html_template="accounts/emails/role_assigned.html",
            text_template="accounts/emails/role_assigned.txt",
            context=context,
            audit_user=user,
            audit_action=AuditActionChoices.NOTIFY,
            audit_message=f"Role assignment notification sent ({role.name}).",
        )

    @classmethod
    def send_role_revoked_email(
        cls,
        *,
        actor: CustomUser,
        user: CustomUser,
        role: Role,
        reason: str = "",
    ) -> bool:
        recipient = user.email or user.recovery_email
        if not recipient or not user.get_notification_pref("email"):
            return False

        context = {
            "actor": actor,
            "user": user,
            "full_name": user.get_full_name(),
            "role": role,
            "reason": reason,
        }

        return cls._send_email(
            subject="Your SchoolOS Role Has Been Revoked",
            recipient=recipient,
            html_template="accounts/emails/role_revoked.html",
            text_template="accounts/emails/role_revoked.txt",
            context=context,
            audit_user=user,
            audit_action=AuditActionChoices.NOTIFY,
            audit_message=f"Role revocation notification sent ({role.name}).",
        )

    # Account Lock / Unlock
    @classmethod
    def send_account_locked_email(cls, user: CustomUser) -> bool:
        recipient = user.email or user.recovery_email
        if not recipient or not user.get_notification_pref("email"):
            return False

        context = {
            "user": user,
            "full_name": user.get_full_name(),
        }

        return cls._send_email(
            subject="Your SchoolOS Account Has Been Locked",
            recipient=recipient,
            html_template="accounts/emails/account_locked.html",
            text_template="accounts/emails/account_locked.txt",
            context=context,
            audit_user=user,
            audit_action=AuditActionChoices.NOTIFY,
            audit_message="Account locked notification sent.",
        )

    @classmethod
    def send_account_unlocked_email(cls, user: CustomUser) -> bool:
        recipient = user.email or user.recovery_email
        if not recipient or not user.get_notification_pref("email"):
            return False

        context = {
            "user": user,
            "full_name": user.get_full_name(),
        }

        return cls._send_email(
            subject="Your SchoolOS Account Has Been Unlocked",
            recipient=recipient,
            html_template="accounts/emails/account_unlocked.html",
            text_template="accounts/emails/account_unlocked.txt",
            context=context,
            audit_user=user,
            audit_action=AuditActionChoices.NOTIFY,
            audit_message="Account unlocked notification sent.",
        )


    # Account Activation
    @classmethod
    def send_account_activation_email(cls, *, user: CustomUser, token: str) -> bool:
        recipient = user.email or user.recovery_email
        if not recipient or not user.get_notification_pref("email"):
            return False

        activation_url = f"{settings.FRONTEND_URL.rstrip('/')}/activate-account/{token}"

        context = {
            "user": user,
            "full_name": user.get_full_name(),
            "activation_url": activation_url,
            "support_email": settings.DEFAULT_FROM_EMAIL,
            "expires_hours": 48,
        }

        return cls._send_email(
            subject="Activate your SchoolOS account",
            recipient=recipient,
            html_template="accounts/emails/account_activation.html",
            text_template="accounts/emails/account_activation.txt",
            context=context,
            audit_user=user,
            audit_action=AuditActionChoices.NOTIFY,
            audit_message="Account activation email sent.",
        )

    @classmethod
    def send_account_activated_email(cls, *, user: CustomUser) -> bool:
        recipient = user.email or user.recovery_email
        if not recipient or not user.get_notification_pref("email"):
            return False

        context = {
            "user": user,
            "full_name": user.get_full_name(),
            "login_url": f"{settings.FRONTEND_URL.rstrip('/')}/login",
            "support_email": settings.DEFAULT_FROM_EMAIL,
        }

        return cls._send_email(
            subject="Your SchoolOS account is now active",
            recipient=recipient,
            html_template="accounts/emails/account_activated.html",
            text_template="accounts/emails/account_activated.txt",
            context=context,
            audit_user=user,
            audit_action=AuditActionChoices.NOTIFY,
            audit_message="Account activation confirmation sent.",
        )