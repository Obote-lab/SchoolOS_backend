import logging
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_field
from rest_framework import serializers
from ..models import CustomUser, PermissionMatrix, Role, UserRole
from ..services.role_assignment import RoleAssignmentService
from ..services.password_reset_service import PasswordResetService
from ..services.account_activation_service import AccountActivationService
from ..utils import validate_password_reset_token
from core.choices import GenderChoices


logger = logging.getLogger(__name__)

class UserRoleBasicSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    role_category = serializers.CharField(source="role.role_category",read_only=True)
    school_name = serializers.CharField(source="school.school_name", allow_null=True,read_only=True)

    class Meta:
        model = UserRole
        fields = [
            "id",
            "role_name",
            "role_category",
            "school_name",
            "role",
            "school",
            "is_primary_role",
            "assigned_date",
            "valid_until",
            "is_active",
            "metadata",
        ]
        read_only_fields = ["role", "school"]


class CustomUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "permanent_id",
            "login_id",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "user_gender",
            "preferred_language",
            "notification_prefs",
            "profile_picture",
            "county",
            "sub_county",
            "ward",
            "address",
            "recovery_email",
            "is_active",
            "is_verified",
            "can_login",
            "is_locked",
            "date_joined",
            "last_login",
            "created_at",
            "updated_at",
            "roles",
            "last_password_change",
        ]
        read_only_fields = [
            "id",
            "permanent_id",
            "login_id",
            "is_locked",
            "date_joined",
            "last_login",
            "created_at",
            "updated_at",
            "last_password_change",
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_full_name(self, obj) -> str:
        return obj.get_full_name()

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_locked(self, obj) -> bool:
        return obj.is_locked()


    @extend_schema_field(UserRoleBasicSerializer(many=True))
    def get_roles(self, obj):
        active_roles = (
            obj.user_roles.filter(is_active=True)
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=timezone.now()))
            .select_related("role", "school")
        )
        return UserRoleBasicSerializer(active_roles, many=True).data

class CustomUserCreateSerializer(serializers.Serializer):
    """Input for user creation — no temporary password is ever returned."""

    first_name = serializers.CharField(max_length=100, required=True)
    last_name = serializers.CharField(max_length=100, required=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    user_gender = serializers.ChoiceField(choices=GenderChoices.choices, required=False)
    date_of_birth = serializers.DateField(required=False)
    role_name = serializers.CharField(required=True, help_text="Role to assign")
    school_id = serializers.UUIDField(
        required=False, help_text="School UUID (required for school-level roles)"
    )

    def validate(self, data):
        if not data.get("email") and not data.get("phone"):
            raise serializers.ValidationError("Either email or phone is required.")
        return data

    @transaction.atomic
    def create(self, validated_data):
        from schools.models import School
        from ..services.user_creation_services import UserCreationService

        request = self.context.get("request")
        creator = request.user if request else None

        role_name = validated_data.pop("role_name")
        school_id = validated_data.pop("school_id", None)

        school = None
        if school_id:
            school = School.objects.get(id=school_id)

        user = UserCreationService.create_user(
            creator=creator,
            school=school,
            user_data=validated_data,
            role_name=role_name,
            send_email=True,
        )

        return {
            "message": "User created successfully. They must set a password on first login.",
            "login_id": user.login_id,
            "user": CustomUserSerializer(user, context=self.context).data,
        }


class CustomUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "email",
            "phone",
            "user_gender",
            "preferred_language",
            "notification_prefs",
            "profile_picture",
            "county",
            "sub_county",
            "ward",
            "address",
            "recovery_email",
        ]


class LoginSerializer(serializers.Serializer):
    login_id = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})

    def validate(self, data):
        login_id = data.get("login_id")
        password = data.get("password")
        request = self.context.get("request")

        if not login_id or not password:
            raise serializers.ValidationError("login_id and password required.")

        user = CustomUser.objects.filter(login_id=login_id).first()
        if not user:
            raise serializers.ValidationError("Invalid credentials.")

        if not user.can_authenticate():
            raise serializers.ValidationError(
                "Account disabled, locked, or unverified."
            )

        if not user.check_password(password):
            user.record_failed_login()
            raise serializers.ValidationError("Invalid credentials.")

        user.reset_failed_logins()

        prefs = user.notification_prefs or {}
        if not isinstance(prefs, dict):
            prefs = {}
            user.notification_prefs = prefs
            user.save(update_fields=["notification_prefs"])

        data["user"] = user
        data["must_change_password"] = prefs.get("must_change_password", False)
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)


class PasswordChangeSerializer(serializers.Serializer):

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user

        if not user.check_password(attrs["old_password"]):
            raise serializers.ValidationError(
                {
                    "old_password":
                    "Incorrect password."
                }
            )

        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {
                    "confirm_password":
                    "Passwords do not match."
                }
            )

        validate_password(
            attrs["new_password"],
            user,
        )

        return attrs

    def save(self):

        user = self.context["request"].user

        PasswordResetService.reset_password(
            user=user,
            new_password=self.validated_data["new_password"],
            request=self.context.get("request"),
        )

        return user

class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Request a password reset.
    Delegates the actual reset process to PasswordResetService.
    """

    login_id = serializers.CharField(required=True)

    def validate_login_id(self, value):
        try:
            return CustomUser.objects.get(login_id=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError(
                "No account exists with that Login ID."
            )

    def create(self, validated_data):
        request = self.context.get("request")
        user = validated_data["login_id"]
        PasswordResetService.send_password_reset_email(user=user,request=request,)
        return {"message": "Password reset instructions have been sent."}


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )

        user = validate_password_reset_token(data["token"])
        if not user:
            raise serializers.ValidationError(
                {"token": "Invalid or expired password reset token."}
            )

        # Full Django password validation
        validate_password(data["new_password"], user)

        data["user"] = user
        return data

    def create(self, validated_data):
        user = validated_data["user"]
        request = self.context.get("request")

        PasswordResetService.reset_password(
            user=user,
            new_password=validated_data["new_password"],
            request=request,
        )

        return {"message": "Password has been reset successfully."}


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "role_category",
            "permissions_tier",
            "description",
            "default_dashboard",
            "access_level",
            "created_at",
            "updated_at",
            "created_by",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


class UserRoleSerializer(serializers.ModelSerializer):
    user_details = CustomUserSerializer(source="user", read_only=True)
    role_details = RoleSerializer(source="role", read_only=True)
    school_name = serializers.CharField(source="school.school_name", read_only=True, allow_null=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = UserRole
        fields = [
            "id",
            "user",
            "user_details",
            "role",
            "role_details",
            "school",
            "school_name",
            "is_primary_role",
            "assigned_by",
            "assigned_date",
            "valid_until",
            "metadata",
            "is_active",
            "is_expired",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "assigned_date", "created_at", "updated_at"]

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_expired(self, obj) -> bool:
        return obj.is_expired()

    def validate(self, data):
        if data.get("valid_until") and data["valid_until"] < timezone.now():
            raise serializers.ValidationError(
                {"valid_until": "Expiry cannot be in past."}
            )
        return data

    def create(self, validated_data):
        """
        Delegate role assignment to RoleAssignmentService.
        This automatically handles:
        • permission checks
        • duplicate prevention
        • school validation
        • primary role switching
        • audit logging
        • email notifications
        """
        request = self.context.get("request")

        return RoleAssignmentService.assign_role(
            actor=request.user,
            target_user=validated_data["user"],
            role=validated_data["role"],
            school=validated_data.get("school"),
            is_primary=validated_data.get("is_primary_role", False),
            valid_until=validated_data.get("valid_until"),
            metadata=validated_data.get("metadata", {}),
        )


class PermissionMatrixSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = PermissionMatrix
        fields = [
            "id",
            "role",
            "role_name",
            "module",
            "action",
            "resource_scope",
            "conditions",
            "is_allowed",
            "priority",
            "created_at",
            "updated_at",
            "created_by",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


class BulkUserCreateSerializer(serializers.Serializer):
    school_id = serializers.UUIDField(required=False)
    role_name = serializers.CharField(required=True)
    users = serializers.ListField(child=serializers.DictField(), required=True)

    @transaction.atomic
    def create(self, validated_data):
        from schools.models import School

        from ..services.user_creation_services import UserCreationService

        request = self.context.get("request")
        creator = request.user if request else None

        school = (
            School.objects.get(id=validated_data.get("school_id"))
            if validated_data.get("school_id")
            else None
        )

        results = UserCreationService.create_bulk_users(
            creator=creator,
            school=school,
            users_data=validated_data["users"],
            role_name=validated_data["role_name"],
            send_email=False,
        )

        return results

class RegionalAdminCreateSerializer(serializers.Serializer):
    """
    Create a Regional Admin.
    managed_counties is stored in the UserRole.metadata for now.
    """

    first_name = serializers.CharField(max_length=100, required=True)
    last_name = serializers.CharField(max_length=100, required=True)
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(max_length=15, required=True)
    managed_counties = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=True,
        min_length=1,
        help_text="List of county names or codes (e.g. ['Nairobi', 'Kiambu'])",
    )

    def create(self, validated_data):
        from ..services.user_creation_services import UserCreationService
        from ..services.role_assignment import RoleAssignmentService

        request = self.context.get("request")
        creator = request.user if request else None

        managed_counties = validated_data.pop("managed_counties")

        user = UserCreationService.create_user(
            creator=creator,
            school=None,
            user_data=validated_data,
            role_name="Regional Admin",
            send_email=True,
        )

        # Store managed counties in the primary role metadata
        primary_role = user.user_roles.filter(is_primary_role=True, is_active=True).first()
        if primary_role:
            primary_role.metadata = primary_role.metadata or {}
            primary_role.metadata["managed_counties"] = managed_counties
            primary_role.save(update_fields=["metadata"])

        return {
            "message": "Regional Admin created successfully. They must set a password on first login.",
            "login_id": user.login_id,
            "user": CustomUserSerializer(user, context=self.context).data,
        }



class UserSearchSerializer(serializers.Serializer):
    query = serializers.CharField(required=False)
    role = serializers.CharField(required=False)
    school = serializers.UUIDField(required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, data):
        if not any(data.values()):
            raise serializers.ValidationError("At least one search parameter required.")
        return data

class AccountActivationSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)

    def validate_token(self, value):
        user = AccountActivationService.validate_token(value)
        if not user:
            raise serializers.ValidationError("Invalid or expired activation token.")
        return value

    def create(self, validated_data):
        user = AccountActivationService.activate_account(validated_data["token"])
        return {
            "message": "Account activated successfully.",
            "login_id": user.login_id,
            "user": CustomUserSerializer(user, context=self.context).data,
        }


class RoleAssignmentSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    role_id = serializers.UUIDField()
    school_id = serializers.UUIDField(required=False)
    is_primary = serializers.BooleanField(default=True)


class RoleRevocationSerializer(serializers.Serializer):
    assignment_id = serializers.UUIDField()
    reason = serializers.CharField(required=False)


class PromotionSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    new_role_id = serializers.UUIDField()
    school_id = serializers.UUIDField(required=False)


class TransferSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    new_school_id = serializers.UUIDField()



class ResendActivationSerializer(serializers.Serializer):
    """POST /auth/resend-activation/"""
    login_id = serializers.CharField(max_length=50)


class CreateTeacherSerializer(serializers.Serializer):
    """POST /schools/<school_id>/teachers/"""
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    user_gender = serializers.CharField(max_length=20, required=False, allow_blank=True)


class CreatePrincipalSerializer(serializers.Serializer):
    """POST /system/schools/<school_id>/principals/"""
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)


class DashboardStatsSerializer(serializers.Serializer):
    """Generic dashboard payload (adjust keys to match what your views return)."""
    message = serializers.CharField(required=False)
    stats = serializers.DictField(required=False)
    data = serializers.DictField(required=False)



class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()


class SystemRootDashboardResponseSerializer(serializers.Serializer):
    summary = serializers.DictField()
    recent_users = CustomUserSerializer(many=True)


class RegionalAdminDashboardResponseSerializer(serializers.Serializer):
    regional_admin = serializers.CharField()
    summary = serializers.DictField()
    schools = serializers.ListField(child=serializers.DictField())
    note = serializers.CharField(required=False)

class TokenPairSerializer(serializers.Serializer):
    refresh = serializers.CharField()
    access = serializers.CharField()


class LoginUserInfoSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    login_id = serializers.CharField()
    full_name = serializers.CharField()
    email = serializers.EmailField(allow_null=True)
    is_superuser = serializers.BooleanField()
    school = serializers.DictField(allow_null=True)
    primary_role = serializers.CharField(allow_null=True)
    must_change_password = serializers.BooleanField()


class LoginResponseSerializer(serializers.Serializer):
    user = LoginUserInfoSerializer()
    tokens = TokenPairSerializer()


class UserCreatedResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    login_id = serializers.CharField()
    user = CustomUserSerializer()


class BulkUserCreateResultItemSerializer(serializers.Serializer):
    index = serializers.IntegerField()
    user_id = serializers.CharField(required=False)
    login_id = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class BulkUserCreateResponseSerializer(serializers.Serializer):
    created = BulkUserCreateResultItemSerializer(many=True)
    failed = BulkUserCreateResultItemSerializer(many=True)
    total_requested = serializers.IntegerField()
    total_created = serializers.IntegerField()
    total_failed = serializers.IntegerField()


class AccountActivatedResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    login_id = serializers.CharField()
    user = CustomUserSerializer()