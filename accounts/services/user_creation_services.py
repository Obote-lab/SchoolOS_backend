"""
User Creation Service
This is the ONLY recommended entry point for creating users in SchoolOS.
Never create users directly from views or serializers.
"""

from __future__ import annotations
import logging
from typing import Any
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from core.choices import AccessLevelChoices
from core.choices.identity import AuditActionChoices
from ..models import CustomUser, Role, UserRole
from .email_service import EmailService
from .login_id_generator import LoginIDGenerator
from core.audit import create_audit_log


logger = logging.getLogger(__name__)


class UserCreationService:
    """
    Responsible for the complete lifecycle of creating users.
    """

    MAX_LOGIN_ID_ATTEMPTS = 10

    # PUBLIC API
    @classmethod
    @transaction.atomic
    def create_user(cls,*,creator: CustomUser,
        user_data: dict[str, Any],role_name: str,
        school=None,send_email: bool = True) -> CustomUser:
        """
        Create a user with full consistency guarantees.

        Steps:
        1. Resolve role
        2. Validate permissions
        3. Generate unique login ID
        4. Create user record
        5. Assign primary role
        6. Apply role-based defaults
        7. Create audit log
        8. Send welcome email (optional)
        """
        role = cls._get_role(role_name)
        cls._validate_permissions(creator, role, school)

        login_id = cls._generate_unique_login_id(school=school)

        user = cls._create_user_record(
            login_id=login_id,school=school,user_data=user_data,)
        cls._assign_primary_role(creator, user, role, school)
        cls._apply_defaults(user, role)
        cls._create_audit_log(creator, user, role, school, request=None)

        if send_email:
            try:
                EmailService.send_welcome_email(user)
            except Exception:
                logger.exception("Failed to send welcome email to %s", user.login_id)

        logger.info("User %s created by %s with role %s", user.login_id, creator.login_id, role.name)
        return user

    # PRIVATE HELPERS
    @staticmethod
    def _get_role(role_name: str) -> Role:
        try:
            return Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            raise ValidationError(f"Role '{role_name}' does not exist.")

    @staticmethod
    def _validate_permissions(creator: CustomUser, role: Role, school) -> None:
        if not creator.can_manage_role(role, school):
            raise PermissionDenied(f"You do not have permission to assign the role '{role.name}'.")

        if role.access_level == AccessLevelChoices.SCHOOL and school is None:
            raise ValidationError(f"Role '{role.name}' requires a school.")

        if role.access_level in (AccessLevelChoices.COUNTY, AccessLevelChoices.NATIONAL) and school is not None:
            raise ValidationError(f"Role '{role.name}' cannot be assigned to a specific school.")

    @classmethod
    def _generate_unique_login_id(cls, school) -> str:
        for _ in range(cls.MAX_LOGIN_ID_ATTEMPTS):
            candidate = LoginIDGenerator.generate_login_id(school=school)
            if not CustomUser.objects.filter(login_id=candidate).exists():
                return candidate
        raise RuntimeError("Unable to generate a unique login ID after multiple attempts.")

    @staticmethod
    def _create_user_record(*, login_id: str, school, user_data: dict[str, Any]) -> CustomUser:
        return CustomUser.objects.create_user(
            login_id=login_id,
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
    def _apply_defaults(user: CustomUser, role: Role):
        """
        Apply sensible defaults based on the role.
        Currently only special handling for Students.
        """
        # Students should not log in by default
        if role.name.lower() in ("student", "learner"):
            user.can_login = False
            prefs = user.notification_prefs or {}
            prefs["must_change_password"] = True
            user.notification_prefs = prefs
            user.save(update_fields=["can_login", "notification_prefs"])

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


    # BULK CREATION
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
                created.append({
                    "index": index,
                    "user_id": str(user.id),
                    "login_id": user.login_id,
                })
            except Exception as exc:
                logger.exception("Failed to create user at index %s", index)
                failed.append({
                    "index": index,
                    "error": str(exc),
                })

        return {
            "created": created,
            "failed": failed,
            "total_requested": len(users_data),
            "total_created": len(created),
            "total_failed": len(failed),
        }