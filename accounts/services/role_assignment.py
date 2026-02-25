from django.core.exceptions import PermissionDenied
from django.db.models import Q
from ..models import CustomUser, Role, UserRole, PermissionMatrix, AuditLog
from django.utils import timezone


class RoleAssignmentService:
    """Centralized role assignment/revocation using PermissionMatrix"""

    @staticmethod
    def assign_role(
        *, 
        actor: CustomUser, 
        target_user_id, 
        role_id, 
        school=None, 
        metadata=None
    ):
        role = Role.objects.get(id=role_id)

        # Centralized permission check
        if not RoleAssignmentService.can_assign_role(actor, role, school):
            raise PermissionDenied(f"Cannot assign role '{role.name}'")

        target_user = CustomUser.objects.get(id=target_user_id)

        # School validation
        if role.access_level == Role.AccessLevelChoices.SCHOOL and not school:
            raise ValueError(f"School required for role: {role.name}")
        if role.access_level in ["county", "national"] and school:
            raise ValueError(f"Role {role.name} cannot be school-specific")

        # Prevent duplicate assignment
        if UserRole.objects.filter(user=target_user, role=role, school=school).exists():
            raise ValueError(f"User already has role '{role.name}' here")

        # Create assignment
        is_primary = metadata.get('is_primary', False) if metadata else False
        valid_until = metadata.get('valid_until') if metadata else None

        user_role = UserRole.objects.create(
            user=target_user,
            role=role,
            school=school,
            is_primary_role=is_primary,
            valid_until=valid_until,
            metadata=metadata or {},
            assigned_by=actor
        )

        # Audit
        AuditLog.objects.create(
            user=actor,
            action_type="CREATE",
            model_name="UserRole",
            record_id=user_role.id,
            new_value=f"Assigned {role.name} to {target_user.login_id} (primary: {is_primary})",
            reason="Role assignment",
            school=school,
            timestamp=timezone.now()
        )

        return user_role

    @staticmethod
    def revoke_role(
        *, 
        actor: CustomUser, 
        user_role_id, 
        reason="Role revoked"
    ):
        """Revoke (deactivate) a role assignment"""
        user_role = UserRole.objects.get(id=user_role_id)

        # Check permission to revoke
        if not RoleAssignmentService.can_revoke_role(actor, user_role):
            raise PermissionDenied(f"Cannot revoke role '{user_role.role.name}'")

        user_role.is_active = False
        user_role.save(update_fields=["is_active"])

        # Audit
        AuditLog.objects.create(
            user=actor,
            action_type="DELETE",
            model_name="UserRole",
            record_id=user_role.id,
            old_value=f"Revoked {user_role.role.name} from {user_role.user.login_id}",
            reason=reason,
            school=user_role.school,
            timestamp=timezone.now()
        )

        return user_role

    @staticmethod
    def can_assign_role(actor: CustomUser, target_role: Role, school=None) -> bool:
        actor_roles_qs = actor.user_roles.filter(is_active=True)
        if school:
            actor_roles_qs = actor_roles_qs.filter(
                Q(school=school) | Q(role__access_level__in=["county", "national"])
            )
        else:
            actor_roles_qs = actor_roles_qs.filter(role__access_level__in=["county", "national"])

        if not actor_roles_qs.exists():
            return False

        return PermissionMatrix.objects.filter(
            role__in=actor_roles_qs.values_list("role_id", flat=True),
            module="roles",
            action="assign",
            is_allowed=True,
            resource_scope__in=["school", "county", "national"] if school else ["county", "national"]
        ).exists()

    @staticmethod
    def can_revoke_role(actor: CustomUser, user_role: UserRole) -> bool:
        """Same logic as assign for now — can be stricter later"""
        return RoleAssignmentService.can_assign_role(actor, user_role.role, user_role.school)