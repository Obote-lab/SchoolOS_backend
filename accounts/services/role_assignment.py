import logging
from typing import Optional
from uuid import UUID
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from core.choices import AccessLevelChoices
from ..models import AuditLog, CustomUser, Role, UserRole
from .email_service import EmailService
from core.audit import create_audit_log
from core.choices.identity import AuditActionChoices


logger = logging.getLogger(__name__)


class RoleAssignmentService:
    """
    Centralized service for all user-role operations.

    Responsibilities:
    - Assign roles
    - Revoke roles
    - Promote users
    - Transfer users between schools
    - Maintain exactly one active primary role
    - Send notifications
    - Create audit logs
    """

    # Internal Helpers
    @staticmethod
    def _get_role(role_id: UUID | str | Role) -> Role:
        if isinstance(role_id, Role):
            return role_id
        try:
            return Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            raise ValidationError(f"Role '{role_id}' does not exist.")

    @staticmethod
    def _get_user(user_id: UUID | str | CustomUser) -> CustomUser:
        if isinstance(user_id, CustomUser):
            return user_id
        try:
            return CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            raise ValidationError(f"User '{user_id}' does not exist.")

    @staticmethod
    def _get_assignment(assignment_id: UUID | str | UserRole) -> UserRole:
        if isinstance(assignment_id, UserRole):
            return assignment_id
        try:
            return UserRole.objects.get(id=assignment_id)
        except UserRole.DoesNotExist:
            raise ValidationError(f"Role assignment '{assignment_id}' does not exist.")

    @staticmethod
    def _validate_school(role: Role, school) -> None:
        if role.access_level == AccessLevelChoices.SCHOOL and school is None:
            raise ValidationError(f"School is required for role '{role.name}'.")

        if role.access_level in (AccessLevelChoices.COUNTY, AccessLevelChoices.NATIONAL) and school is not None:
            raise ValidationError(f"Role '{role.name}' cannot be assigned to a specific school.")

    @staticmethod
    def _deactivate_existing_primary(user: CustomUser, school=None) -> None:
        qs = UserRole.objects.filter(user=user, is_primary_role=True, is_active=True)
        if school is not None:
            qs = qs.filter(school=school)
        qs.update(is_primary_role=False)

    @staticmethod
    def _ensure_primary_role(user: CustomUser) -> None:
        """Ensure the user has exactly one active primary role."""
        has_primary = user.user_roles.filter(is_active=True, is_primary_role=True).exists()
        if has_primary:
            return

        replacement = (
            user.user_roles.filter(is_active=True)
            .select_related("role")
            .order_by("role__permissions_tier")
            .first()
        )
        if replacement:
            replacement.is_primary_role = True
            replacement.save(update_fields=["is_primary_role"])

    @staticmethod
    def _audit(*, actor: CustomUser, action: str, model: str, record_id, message: str, school=None, reason: str = "") -> None:
        highest_role = actor.get_highest_tier()
        role_name = highest_role.name if highest_role else ""

        create_audit_log(
            actor=actor,
            action=AuditActionChoices.ROLE_ASSIGNED,
            model_name="UserRole",
            record_id=record_id,
            new_value=message,
            reason=reason,
            school=school,
        )

    # Public API
    @staticmethod
    @transaction.atomic
    def assign_role(
        *,
        actor: CustomUser,
        target_user: UUID | str | CustomUser,
        role: UUID | str | Role,
        school=None,
        is_primary: bool = False,
        valid_until=None,
        metadata: dict | None = None,
    ) -> UserRole:
        role = RoleAssignmentService._get_role(role)
        target_user = RoleAssignmentService._get_user(target_user)

        if not actor.can_manage_role(role, school):
            raise PermissionDenied(f"You cannot assign the role '{role.name}'.")

        RoleAssignmentService._validate_school(role, school)

        if UserRole.objects.filter(user=target_user, role=role, school=school, is_active=True).exists():
            raise ValidationError(f"{target_user.get_full_name()} already has the role '{role.name}'.")

        if is_primary:
            RoleAssignmentService._deactivate_existing_primary(target_user, school)

        assignment = UserRole.objects.create(
            user=target_user,
            role=role,
            school=school if role.access_level == AccessLevelChoices.SCHOOL else None,
            is_primary_role=is_primary,
            valid_until=valid_until,
            metadata=metadata or {},
            assigned_by=actor,
        )

        RoleAssignmentService._audit(
            actor=actor,
            action=AuditActionChoices.ROLE_ASSIGNED,
            model="UserRole",
            record_id=assignment.id,
            message=f"Assigned '{role.name}' to {target_user.login_id}",
            school=school,
        )

        try:
            EmailService.send_role_assignment_email(actor=actor, user=target_user, role=role)
        except Exception:
            logger.exception("Failed to send role assignment email")

        logger.info("Role '%s' assigned to %s by %s", role.name, target_user.login_id, actor.login_id)
        return assignment

    @staticmethod
    @transaction.atomic
    def revoke_role(
        *,
        actor: CustomUser,
        assignment: UUID | str | UserRole,
        reason: str = "Role revoked",
    ) -> UserRole:
        assignment = RoleAssignmentService._get_assignment(assignment)

        if not actor.can_manage_role(assignment.role, assignment.school):
            raise PermissionDenied("You do not have permission to revoke this role.")

        if not assignment.is_active:
            raise ValidationError("This role assignment has already been revoked.")

        was_primary = assignment.is_primary_role

        assignment.is_active = False
        assignment.is_primary_role = False
        assignment.save(update_fields=["is_active", "is_primary_role"])

        if was_primary:
            RoleAssignmentService._ensure_primary_role(assignment.user)

        RoleAssignmentService._audit(
            actor=actor,
            action=AuditActionChoices.ROLE_REVOKED,
            model="UserRole",
            record_id=assignment.id,
            message=f"Revoked '{assignment.role.name}' from {assignment.user.login_id}",
            school=assignment.school,
            reason=reason,
        )

        try:
            EmailService.send_role_revoked_email(actor=actor, user=assignment.user, role=assignment.role)
        except Exception:
            logger.exception("Failed to send role revocation email")

        logger.info("Role '%s' revoked from %s", assignment.role.name, assignment.user.login_id)
        return assignment

    @staticmethod
    @transaction.atomic
    def promote_user(
        *,
        actor: CustomUser,
        target_user: UUID | str | CustomUser,
        new_role: UUID | str | Role,
        school=None,
        reason: str = "Promotion",
        metadata: Optional[dict] = None,
    ) -> UserRole:
        target_user = RoleAssignmentService._get_user(target_user)
        new_role = RoleAssignmentService._get_role(new_role)

        current_primary = (
            target_user.user_roles
            .filter(is_active=True, is_primary_role=True)
            .first()
        )

        if current_primary:
            RoleAssignmentService.revoke_role(
                actor=actor,
                assignment=current_primary,
                reason=reason,
            )

        return RoleAssignmentService.assign_role(
            actor=actor,
            target_user=target_user,
            role=new_role,
            school=school,
            is_primary=True,
            metadata=metadata or {},
        )

    @staticmethod
    @transaction.atomic
    def transfer_user(
        *,
        actor: CustomUser,
        target_user: UUID | str | CustomUser,
        new_school,
        reason: str = "School Transfer",
    ) -> list[UserRole]:
        user = RoleAssignmentService._get_user(target_user)

        active_roles = list(user.user_roles.filter(is_active=True).select_related("role"))
        recreated = []

        for old_assignment in active_roles:
            RoleAssignmentService.revoke_role(
                actor=actor,
                assignment=old_assignment,
                reason=reason,
            )

            new_assignment = RoleAssignmentService.assign_role(
                actor=actor,
                target_user=user,
                role=old_assignment.role,
                school=new_school,
                is_primary=old_assignment.is_primary_role,
            )
            recreated.append(new_assignment)

        user.school = new_school
        user.save(update_fields=["school"])

        return recreated


    # Query Helpers
    @staticmethod
    def get_primary_role(user: UUID | str | CustomUser) -> Optional[UserRole]:
        user = RoleAssignmentService._get_user(user)
        return (
            user.user_roles
            .filter(is_active=True, is_primary_role=True)
            .select_related("role")
            .first()
        )

    @staticmethod
    def get_active_roles(user: UUID | str | CustomUser):
        user = RoleAssignmentService._get_user(user)
        return user.user_roles.filter(is_active=True).select_related("role")

    @staticmethod
    def user_has_role(user: UUID | str | CustomUser, role_name: str) -> bool:
        user = RoleAssignmentService._get_user(user)
        return user.user_roles.filter(is_active=True, role__name=role_name).exists()

    @staticmethod
    def can_assign_role(actor: CustomUser, target_role: Role, school=None) -> bool:
        return actor.can_manage_role(target_role, school)

    @staticmethod
    def can_revoke_role(actor: CustomUser, assignment: UserRole) -> bool:
        return actor.can_manage_role(assignment.role, assignment.school)