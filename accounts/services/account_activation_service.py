import logging
from django.db import transaction
from core.choices.identity import AuditActionChoices
from ..models import CustomUser
from ..utils import (
    generate_account_activation_token,
    validate_account_activation_token,
)
from .email_service import EmailService
from core.audit import create_audit_log
logger = logging.getLogger(__name__)


class AccountActivationService:
    """
    Handles the complete account activation workflow.

    Responsibilities:
    - Generate activation tokens
    - Send activation emails
    - Validate activation tokens
    - Activate user accounts
    - Audit activation events
    - Send confirmation notifications
    """

    @staticmethod
    def send_activation_email(user: CustomUser) -> bool:
        """
        Generate an activation token and send the activation email.
        """
        token = generate_account_activation_token(user)
        success = EmailService.send_account_activation_email(user=user, token=token)

        if success:
            highest_role = user.get_highest_tier()
            role_name = highest_role.name if highest_role else ""

            create_audit_log(
                actor=user,
                action=AuditActionChoices.NOTIFY,
                model_name="CustomUser",
                record_id=user.id,
                reason="Activation email sent",
                school=user.school,
            )

        return success

    @staticmethod
    def validate_token(token: str) -> CustomUser | None:
        """Validate an activation token and return the user if valid."""
        return validate_account_activation_token(token)

    @staticmethod
    @transaction.atomic
    def activate_account(token: str) -> CustomUser:
        """
        Activate a user account using a valid token.
        """
        user = AccountActivationService.validate_token(token)

        if user is None:
            raise ValueError("Invalid or expired activation token.")

        if user.is_verified:
            return user

        user.is_verified = True
        user.verification_token = None
        user.can_login = True
        user.save(update_fields=["is_verified", "verification_token", "can_login"])

        highest_role = user.get_highest_tier()
        role_name = highest_role.name if highest_role else ""

        create_audit_log(
            actor=user,
            action=AuditActionChoices.ACCOUNT_ACTIVATED,
            model_name="CustomUser",
            record_id=user.id,
            reason="Account activated",
            school=user.school,
        )

        try:
            EmailService.send_account_activated_email(user=user)
        except Exception:
            logger.exception("Failed to send account activated email to %s", user.login_id)

        logger.info("Account activated for %s", user.login_id)
        return user

    @staticmethod
    @transaction.atomic
    def resend_activation_email(user: CustomUser) -> bool:
        """
        Resend an activation email.
        Already activated accounts are ignored.
        """
        if user.is_verified:
            logger.info(
                "Activation email not sent because account is already verified: %s",
                user.login_id,
            )
            return False

        return AccountActivationService.send_activation_email(user)