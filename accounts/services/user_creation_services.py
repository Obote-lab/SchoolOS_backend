import logging
from typing import Dict, List, Optional
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.db.models import Q
from ..models import AuditLog, CustomUser, Role, UserRole, PermissionMatrix
from ..utils import send_welcome_email
from .login_id_generator import LoginIDGenerator

logger = logging.getLogger(__name__)


class UserCreationService:
    """
    Secure, audited user creation with hierarchy enforcement.
    Uses PermissionMatrix for authorization.
    No plaintext temp passwords returned.
    """

    @staticmethod
    def can_create(creator: CustomUser, target_role: Role, target_school=None) -> bool:
        """
        Check if creator can assign the target role (via PermissionMatrix)
        """
        actor_roles_qs = creator.user_roles.filter(is_active=True)
        if target_school:
            actor_roles_qs = actor_roles_qs.filter(
                Q(school=target_school) | Q(role__access_level__in=["county", "national"])
            )
        else:
            actor_roles_qs = actor_roles_qs.filter(role__access_level__in=["county", "national"])

        if not actor_roles_qs.exists():
            return False

        return PermissionMatrix.objects.filter(
            role__in=actor_roles_qs.values_list("role_id", flat=True),
            module="users",
            action="create",
            is_allowed=True,
            resource_scope__in=["school", "county", "national"] if target_school else ["county", "national"]
        ).exists()

    @staticmethod
    @transaction.atomic
    def create_user(
        *,
        creator: CustomUser,
        school: Optional["schools.School"],
        user_data: Dict,
        role_name: str,
        send_email: bool = True,
    ) -> CustomUser:
        """
        Create user + assign role + audit + send welcome (no temp password returned)
        """
        # Resolve role
        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            raise ValueError(f"Role not found: {role_name}")

        # Permission check
        if not UserCreationService.can_create(creator, role, school):
            raise PermissionDenied(f"Cannot create user with role '{role_name}'")

        # School validation
        if role.access_level == Role.AccessLevelChoices.SCHOOL and not school:
            raise ValueError(f"School required for role: {role_name}")
        if role.access_level in ["county", "national"] and school:
            raise ValueError(f"Role {role_name} cannot be school-specific")

        # Generate short login_id
        user_type_code = "USR"  # fallback
        for k, v in {
            "SYS": "System Root", "RAD": "Regional Admin", "PRN": "Principal",
            "DEP": "Deputy", "HOD": "Head of Department", "ADM": "Administrator",
            "TCH": "Teacher", "STU": "Student", "PAR": "Parent",
            "MTN": "Matron", "SEC": "Security", "DRV": "Driver", "COK": "Cook"
        }.items():
            if v == role_name:
                user_type_code = k
                break

        max_attempts = 10
        login_id = None
        for _ in range(max_attempts):
            candidate = LoginIDGenerator.generate_login_id(school=school, user_type=user_type_code)
            if not CustomUser.objects.filter(login_id=candidate).exists():
                login_id = candidate
                break
        if not login_id:
            raise RuntimeError("Failed to generate unique login ID")

        # Prepare user
        password = user_data.pop("password", None)
        auto_password = password is None
        plain_password = password or get_random_string(12)

        try:
            user = CustomUser.objects.create_user(
                login_id=login_id,
                school=school,
                user_type=user_type_code,
                password=plain_password,
                **user_data
            )
        except ValidationError as exc:
            raise ValueError(f"Validation failed: {exc.message_dict}")

        # Assign role
        UserRole.objects.create(
            user=user,
            role=role,
            school=school if role.access_level == Role.AccessLevelChoices.SCHOOL else None,
            is_primary_role=True,
            assigned_by=creator
        )

        # Student defaults
        if user_type_code == "STU":
            user.can_login = False
            if school and "swahili" in school.county.lower():
                user.preferred_language = "sw"
            user.save(update_fields=["can_login", "preferred_language"])

        # Force password change if auto-generated
        if auto_password:
            prefs = user.notification_prefs or {}
            prefs["must_change_password"] = True
            user.notification_prefs = prefs
            user.save(update_fields=["notification_prefs"])

        # Audit
        AuditLog.objects.create(
            user=creator,
            action_type="CREATE",
            model_name="CustomUser",
            record_id=user.id,
            new_value=f"Created {role_name} user: {user.login_id} ({user.get_full_name()})",
            reason=f"User creation by {creator.get_full_name()}",
            school=school,
            timestamp=timezone.now()
        )

        # Welcome email (no temp password)
        if send_email and (user.email or user.recovery_email):
            try:
                send_welcome_email(user)
            except Exception as exc:
                logger.warning(f"Welcome email failed for {user.login_id}: {exc}")

        return user

    @staticmethod
    @transaction.atomic
    def create_bulk_users(
        creator: CustomUser,
        school: Optional["schools.School"],
        users_data: List[Dict],
        role_name: str,
        send_email: bool = False,
    ) -> Dict:
        results = {"created": [], "failed": []}

        for idx, data in enumerate(users_data):
            try:
                user = UserCreationService.create_user(
                    creator=creator,
                    school=school,
                    user_data=data,
                    role_name=role_name,
                    send_email=send_email
                )
                results["created"].append({
                    "index": idx,
                    "user_id": str(user.id),
                    "login_id": user.login_id,
                    "full_name": user.get_full_name(),
                })
            except Exception as exc:
                results["failed"].append({
                    "index": idx,
                    "data": data,
                    "error": str(exc)
                })
                logger.error(f"Bulk creation failed at index {idx}: {exc}")

        return results