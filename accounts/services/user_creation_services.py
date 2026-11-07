"""
User Creation Service
This is the ONLY recommended entry point for creating users in SchoolOS.
Never create users directly from views or serializers.
"""

from __future__ import annotations
import logging
import secrets
import string
from typing import Any
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from core.audit import create_audit_log
from core.choices import AccessLevelChoices
from core.choices.identity import AuditActionChoices
from ..models import CustomUser, Role, UserRole
from .email_service import EmailService
from .login_id_generator import LoginIDGenerator

logger = logging.getLogger(__name__)


class UserCreationService:
    """
    Responsible for the complete lifecycle of creating users.
    """

    MAX_LOGIN_ID_ATTEMPTS = 10
    TEMP_PASSWORD_LENGTH = 12

    # PUBLIC API

    @classmethod
    @transaction.atomic
    def create_user(
        cls,
        *,
        creator: CustomUser,
        user_data: dict[str, Any],
        role_name: str,
        school=None,
        send_email: bool = True,
    ) -> CustomUser:
        """
        Create a user with full consistency guarantees.

        Steps:
        1. Resolve role
        2. Validate permissions
        3. Generate unique login ID
        4. Generate one-time temporary password
        5. Create user record (with temp password)
        6. Assign primary role
        7. Apply role-based defaults
        8. Create audit log
        9. Send welcome email with temp password (optional)
        """
        role = cls._get_role(role_name)
        cls._validate_permissions(creator, role, school)

        login_id = cls._generate_unique_login_id(school=school)
        temp_password = cls._generate_temp_password()

        user = cls._create_user_record(
            login_id=login_id,
            school=school,
            user_data=user_data,
            password=temp_password,
        )
        cls._assign_primary_role(creator, user, role, school)
        cls._apply_defaults(user, role)
        cls._create_audit_log(creator, user, role, school, request=None)

        if send_email:
            try:
                EmailService.send_welcome_email(user, temp_password=temp_password)
            except Exception:
                logger.exception(
                    "Failed to send welcome email to %s", user.login_id
                )

        logger.info(
            "User %s created by %s with role %s",
            user.login_id,
            creator.login_id,
            role.name,
        )
        return user

    @classmethod
    def create_bulk_users(
        cls,
        *,
        creator: CustomUser,
        users_data: list[dict],
        role_name: str,
        school=None,
        send_email: bool = False,
    ) -> dict:
        created = []
        failed = []

        for index, data in enumerate(users_data):
            try:
                user = cls.create_user(
                    creator=creator,
                    school=school,
                    user_data=data,
                    role_name=role_name,
                    send_email=send_email,
                )
                created.append(
                    {
                        "index": index,
                        "user_id": str(user.id),
                        "login_id": user.login_id,
                    }
                )
            except Exception as exc:
                logger.exception("Failed to create user at index %s", index)
                failed.append({"index": index, "error": str(exc)})

        return {
            "created": created,
            "failed": failed,
            "total_requested": len(users_data),
            "total_created": len(created),
            "total_failed": len(failed),
        }

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _get_role(role_name: str) -> Role:
        try:
            return Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            raise ValidationError(f"Role '{role_name}' does not exist.")

    @staticmethod
    def _validate_permissions(creator: CustomUser, role: Role, school) -> None:
        if not creator.can_manage_role(role, school):
            raise PermissionDenied(
                f"You do not have permission to assign the role '{role.name}'."
            )

        if role.access_level == AccessLevelChoices.SCHOOL and school is None:
            raise ValidationError(f"Role '{role.name}' requires a school.")

        if (
            role.access_level
            in (AccessLevelChoices.COUNTY, AccessLevelChoices.NATIONAL)
            and school is not None
        ):
            raise ValidationError(
                f"Role '{role.name}' cannot be assigned to a specific school."
            )

    @classmethod
    def _generate_unique_login_id(cls, school) -> str:
        for _ in range(cls.MAX_LOGIN_ID_ATTEMPTS):
            candidate = LoginIDGenerator.generate_login_id(school=school)
            if not CustomUser.objects.filter(login_id=candidate).exists():
                return candidate
        raise RuntimeError(
            "Unable to generate a unique login ID after multiple attempts."
        )

    @classmethod
    def _generate_temp_password(cls, length: int | None = None) -> str:
        """Cryptographically strong one-time password for first login."""
        n = length or cls.TEMP_PASSWORD_LENGTH
        # Exclude ambiguous characters: 0 O o 1 l I
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
        return "".join(secrets.choice(alphabet) for _ in range(n))

    @staticmethod
    def _create_user_record(
        *,
        login_id: str,
        school,
        user_data: dict[str, Any],
        password: str | None = None,
    ) -> CustomUser:
        return CustomUser.objects.create_user(
            login_id=login_id,
            password=password,
            school=school,
            **user_data,
        )

    @staticmethod
    def _assign_primary_role(creator, user, role, school):
        UserRole.objects.create(
            user=user,
            role=role,
            school=school if role.access_level == AccessLevelChoices.SCHOOL else None,
            assigned_by=creator,
            is_primary_role=True,
        )

    @staticmethod
    def _apply_defaults(user: CustomUser, role: Role) -> None:
        """
        Role-based defaults after create.

        - Students / learners: cannot login by default.
        - Everyone else (Regional Admin, Principal, staff, …):
            can login, force password change, leave unverified until
            first successful login (LoginSerializer sets is_verified).
        """
        name = role.name.lower()
        prefs = user.notification_prefs if isinstance(user.notification_prefs, dict) else {}

        if name in ("student", "learner"):
            user.can_login = False
            user.is_verified = False
            prefs["must_change_password"] = True
            user.notification_prefs = prefs
            user.save(
                update_fields=["can_login", "is_verified", "notification_prefs"]
            )
            return

        # Operators / regional / school staff
        user.can_login = True
        user.is_verified = False  # verified on first successful login
        prefs["must_change_password"] = True
        user.notification_prefs = prefs
        user.save(
            update_fields=["can_login", "is_verified", "notification_prefs"]
        )

    @staticmethod
    def _create_audit_log(creator, user, role, school, request=None):
        create_audit_log(
            actor=creator,
            action=AuditActionChoices.CREATE,
            model_name="CustomUser",
            record_id=user.id,
            school=school,
            reason=f"Created user with role '{role.name}'",
            new_value=user.login_id,
            request=request,
        )