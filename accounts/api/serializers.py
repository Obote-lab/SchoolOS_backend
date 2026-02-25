from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from ..models import CustomUser, PermissionMatrix, Role, UserRole, AuditLog
import logging

logger = logging.getLogger(__name__)


class UserRoleBasicSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name")
    role_category = serializers.CharField(source="role.role_category")
    school_name = serializers.CharField(source="school.school_name", allow_null=True)

    class Meta:
        model = UserRole
        fields = [
            "id", "role_name", "role_category", "school_name",
            "role", "school", "is_primary_role",
            "assigned_date", "valid_until", "is_active",
        ]
        read_only_fields = ["role", "school"]


class CustomUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id", "permanent_id", "login_id",
            "first_name", "middle_name", "last_name", "full_name",
            "email", "phone", "gender", "preferred_language",
            "notification_prefs", "profile_picture",
            "county", "sub_county", "ward", "address", "recovery_email",
            "is_active", "is_verified", "can_login", "is_locked",
            "date_joined", "last_login", "created_at", "updated_at",
            "roles", "last_password_change",
        ]
        read_only_fields = [
            "id", "permanent_id", "login_id", "is_locked",
            "date_joined", "last_login", "created_at", "updated_at",
            "last_password_change",
        ]

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_is_locked(self, obj):
        return obj.is_locked()

    def get_roles(self, obj):
        active = UserRole.objects.filter(
            user=obj, is_active=True
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gt=timezone.now())
        )
        effective = [a for a in active if a.get_effective_role()]
        return UserRoleBasicSerializer(effective, many=True).data


class CustomUserCreateSerializer(serializers.Serializer):
    """Input for user creation — no temp password ever returned"""

    first_name = serializers.CharField(max_length=100, required=True)
    last_name = serializers.CharField(max_length=100, required=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    gender = serializers.ChoiceField(choices=CustomUser.GenderChoices.choices, required=False)
    date_of_birth = serializers.DateField(required=False)
    national_id = serializers.CharField(max_length=20, required=False, allow_blank=True)
    role_name = serializers.CharField(required=True, help_text="Role to assign")
    school_id = serializers.UUIDField(required=False, help_text="School UUID (for school roles)")

    def validate(self, data):
        if not data.get("email") and not data.get("phone"):
            raise serializers.ValidationError("Email or phone is required")
        return data

    @transaction.atomic
    def create(self, validated_data):
        from ..services.user_creation_services import UserCreationService
        request = self.context.get("request")
        creator = request.user if request else None

        school = None
        if "school_id" in validated_data:
            from schools.models import School
            school = School.objects.get(id=validated_data.pop("school_id"))

        user = UserCreationService.create_user(
            creator=creator,
            school=school,
            user_data=validated_data,
            role_name=validated_data.pop("role_name"),
            send_email=True
        )

        return {
            "message": "User created. They must set password on first login.",
            "login_id": user.login_id,
            "user": CustomUserSerializer(user, context=self.context).data,
        }


class CustomUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "first_name", "middle_name", "last_name",
            "email", "phone", "gender", "preferred_language",
            "notification_prefs", "profile_picture",
            "county", "sub_county", "ward", "address", "recovery_email",
        ]


class LoginSerializer(serializers.Serializer):
    login_id = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        login_id = data.get("login_id")
        password = data.get("password")
        request = self.context.get("request")

        if not login_id or not password:
            raise serializers.ValidationError('login_id and password required.')

        user = CustomUser.objects.filter(login_id=login_id).first()
        if not user:
            raise serializers.ValidationError("Invalid credentials.")

        if not user.can_authenticate():
            raise serializers.ValidationError("Account disabled, locked, or unverified.")

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
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        user = self.context["request"].user
        if not user.check_password(data["old_password"]):
            raise serializers.ValidationError({"old_password": "Incorrect current password."})
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        validate_password(data["new_password"], user)
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    login_id = serializers.CharField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        password = data["new_password"].lower()
        forbidden = ["password", "12345678", "qwerty123"]
        if password in forbidden:
            raise serializers.ValidationError({"new_password": "Password too common."})

        user = decode_password_reset_token(data["token"])
        if user:
            user_info = [user.first_name.lower(), user.last_name.lower(), user.login_id.lower()]
            for info in user_info:
                if info and info in password:
                    raise serializers.ValidationError({"new_password": "Avoid personal information in password."})
        return data


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = [
            "id", "name", "role_category", "permissions_tier",
            "description", "default_dashboard", "access_level",
            "created_at", "updated_at", "created_by",
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
            "id", "user", "user_details", "role", "role_details",
            "school", "school_name", "is_primary_role", "assigned_by",
            "assigned_date", "valid_until", "metadata", "is_active",
            "is_expired", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "assigned_date", "created_at", "updated_at"]

    def get_is_expired(self, obj):
        return obj.is_expired()

    def validate(self, data):
        if data.get("valid_until") and data["valid_until"] < timezone.now():
            raise serializers.ValidationError({"valid_until": "Expiry cannot be in past."})

        if self.instance is None:
            if UserRole.objects.filter(
                user=data.get("user"), role=data.get("role"), school=data.get("school")
            ).exists():
                raise serializers.ValidationError("Role assignment already exists.")
        return data

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user:
            validated_data["assigned_by"] = request.user

        instance = super().create(validated_data)

        AuditLog.objects.create(
            user=request.user,
            action_type="CREATE",
            model_name="UserRole",
            record_id=instance.id,
            new_value=f"Assigned {instance.role.name} to {instance.user.login_id}",
            reason="Role assignment via API",
            school=instance.school,
        )
        return instance


class PermissionMatrixSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = PermissionMatrix
        fields = [
            "id", "role", "role_name", "module", "action",
            "resource_scope", "conditions", "is_allowed", "priority",
            "created_at", "updated_at", "created_by",
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
        from ..services.user_creation_services import UserCreationService
        from schools.models import School

        request = self.context.get("request")
        creator = request.user if request else None

        school = School.objects.get(id=validated_data.get("school_id")) if validated_data.get("school_id") else None

        results = UserCreationService.create_bulk_users(
            creator=creator,
            school=school,
            users_data=validated_data["users"],
            role_name=validated_data["role_name"],
            send_email=False
        )

        return results


class UserSearchSerializer(serializers.Serializer):
    query = serializers.CharField(required=False)
    role = serializers.CharField(required=False)
    school = serializers.UUIDField(required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, data):
        if not any(data.values()):
            raise serializers.ValidationError("At least one search parameter required.")
        return data


class RegionalAdminCreateSerializer(serializers.Serializer):
    """Fixed: managed_counties is now list of county names/codes/IDs"""
    first_name = serializers.CharField(max_length=100, required=True)
    last_name = serializers.CharField(max_length=100, required=True)
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(max_length=15, required=True)
    managed_counties = serializers.ListField(
        child=serializers.CharField(max_length=100),  # or UUIDField if using IDs
        required=True,
        min_length=1,
        help_text="List of county names/codes (e.g. ['Nairobi', 'Kiambu'])"
    )
    password = serializers.CharField(
        max_length=128, required=False, write_only=True,
        help_text="Optional — random password generated if omitted"
    )

    def create(self, validated_data):
        # Delegate to service — no temp password returned here
        from ..services.user_creation_services import UserCreationService
        request = self.context.get("request")
        creator = request.user if request else None

        user = UserCreationService.create_user(
            creator=creator,
            school=None,
            user_data=validated_data,
            role_name="Regional Admin",
            send_email=True
        )

        return {
            "message": "Regional Admin created. They must set password on first login.",
            "login_id": user.login_id,
            "user": CustomUserSerializer(user, context=self.context).data,
        }