import uuid
import shortuuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.gis.db.models import PointField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.utils.phone import validate_kenyan_phone

from core.choices import (
    GenderChoices,
    LanguageChoices,
    RoleCategoryChoices,
    AccessLevelChoices,
    ModuleChoices,
    ActionChoices,
    ResourceScopeChoices,
    AuditActionChoices,
)

class CustomUserManager(BaseUserManager):
    def create_user(self, login_id, password=None, school=None, **extra_fields):
        if not login_id:
            raise ValueError(_("login_id is required"))

        if "notification_prefs" not in extra_fields:
            extra_fields["notification_prefs"] = {
                "email": True,"sms": True,
                "push": True,"whatsapp": False,
                "must_change_password": False,
            }

        user = self.model(login_id=login_id, school=school, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(self, login_id, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)
        # extra_fields.setdefault("user_type", CustomUser.UserTypeChoices.SYSTEM)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(login_id=login_id, password=password, school=None, **extra_fields)


class County(models.Model):
    """Kenyan counties for scoping Regional Admins"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=3, unique=True)

    class Meta:
        verbose_name = _("County")
        verbose_name_plural = _("Counties")
        ordering = ["name"]

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    """
    Slim Core User model - Only common fields + Authentication.
    Specific data goes to StaffProfile, StudentProfile, ParentGuardian.
    """
    username = None

    #  Core Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    permanent_id = models.CharField(max_length=50, unique=True, editable=False,help_text=_("Internal immutable system identifier"))
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    # user_type = models.CharField( max_length=3, choices=UserTypeChoices.choices,help_text=_("High-level user category. Does NOT control permissions."))
    #  Contact & Location
    email = models.EmailField(_("email address"), blank=True, null=True, unique=True)
    recovery_email = models.EmailField(blank=True, null=True)
    # phone_regex = RegexValidator( regex=r"^(\+?254|0)?(7\d{8})$", message=_("Phone number must be a valid Kenyan number."))
    phone = models.CharField(max_length=15,validators=[validate_kenyan_phone],blank=True,null=True,unique=True,)
    user_gender = models.CharField(max_length=20, choices=GenderChoices.choices, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    county = models.CharField(max_length=100, blank=True)
    sub_county = models.CharField(max_length=100, blank=True)
    ward = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    #  School & System
    school = models.ForeignKey("schools.School", on_delete=models.SET_NULL, null=True,blank=True,related_name="school_users")
    #  Authentication & Security
    login_id = models.CharField(max_length=50, db_index=True, blank=False, unique=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True, null=True)
    last_password_change = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(blank=True, null=True)
    last_locked_at = models.DateTimeField(null=True, blank=True)
    can_login = models.BooleanField(default=True)
    preferred_language = models.CharField( max_length=20, choices=LanguageChoices.choices, default=LanguageChoices.ENGLISH )
    notification_prefs = models.JSONField(default=dict)
    profile_picture = models.ImageField( upload_to="profile_pics/", blank=True, null=True)
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "login_id"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["login_id"]),
            models.Index(fields=["is_active", "is_verified"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                name="unique_email",
                condition=models.Q(email__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.login_id} ({self.get_full_name() or self.phone})"

    def get_highest_tier(self):
        role_assignment = self.user_roles.filter(is_active=True).order_by('role__permissions_tier').first()
        return role_assignment.role if role_assignment else None


    def get_full_name(self):
        return " ".join(
            part for part in [self.first_name, self.middle_name, self.last_name] if part
        ).strip() or self.login_id
    
    
    def normalize_phone(self):
        if not self.phone:
            return

        phone = self.phone.strip().replace(" ", "").replace("-", "")

        if phone.startswith("0"):
            phone = "+254" + phone[1:]
        elif phone.startswith("254") and not phone.startswith("+254"):
            phone = "+" + phone
        elif phone.startswith("7") and len(phone) == 9:
            phone = "+254" + phone

        self.phone = phone


    def clean(self):
        super().clean()
        # self.normalize_phone()
        # if ( self.date_of_birth and self.date_of_birth > timezone.now().date()):
        #     raise ValidationError(
        #         {"date_of_birth": _( "Date of birth cannot be in the future." ) }
        #     )

    def save(self, *args, **kwargs):
        if not self.permanent_id:
            self.permanent_id = self.generate_permanent_id()

        # self.normalize_phone()
        # if kwargs.pop("validate", True):
        #     self.full_clean()

        super().save(*args, **kwargs)

    def generate_permanent_id(self):
        """
        Generates an immutable internal system identifier.
        Example:
            PID-7KJ9P4XWQ2
        """
        return f"PID-{shortuuid.ShortUUID().random(length=10).upper()}"
    


    def lock_account(self, hours=24):
        self.locked_until = timezone.now() + timezone.timedelta(hours=hours)
        self.last_locked_at = timezone.now()
        self.failed_login_attempts = 0
        self.save(update_fields=["locked_until", "last_locked_at", "failed_login_attempts"])

    def unlock_account(self):
        self.locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=["locked_until", "failed_login_attempts"])

    def is_locked(self):
        if self.locked_until:
            return timezone.now() < self.locked_until
        return False

    def record_failed_login(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.lock_account()
        else:
            self.save(update_fields=["failed_login_attempts"])

    def reset_failed_logins(self):
        self.failed_login_attempts = 0
        self.save(update_fields=["failed_login_attempts"])

    def set_notification_pref(self, channel, enabled=True):
        if not isinstance(self.notification_prefs, dict):
            self.notification_prefs = {}
        self.notification_prefs[channel] = enabled
        self.save(update_fields=["notification_prefs"])

    def get_notification_pref(self, channel, default=True):
        return self.notification_prefs.get(channel, default)

    def can_authenticate(self):
        return (
            self.is_active
            and self.can_login
            and self.is_verified
            and not self.is_locked()
        )

    def can_manage_role(self, target_role: "Role", target_school=None) -> bool:
        if self.is_superuser:
            return True

        my_assignments = self.user_roles.filter(is_active=True).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gt=timezone.now())
        )

        if target_school:
            my_assignments = my_assignments.filter(Q(school=target_school) | Q(role__access_level__in=["county", "national"]))
        else:
            my_assignments = my_assignments.filter(role__access_level__in=["county", "national"])

        for assignment in my_assignments:
            if assignment.role.permissions_tier < target_role.permissions_tier:
                return True
        return False

class Role(models.Model):
    """Role definition for RBAC system"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, help_text=_("Role name (e.g., Principal, Teacher, Student, Parent)"))
    role_category = models.CharField(max_length=20, choices=RoleCategoryChoices.choices, default=RoleCategoryChoices.ADMINISTRATIVE)
    permissions_tier = models.IntegerField(default=5, help_text=_("RBAC hierarchy level (1-10, lower number = higher privilege)"))
    description = models.TextField(blank=True)
    default_dashboard = models.CharField(max_length=200, blank=True, help_text=_("Default dashboard route for this role"))
    access_level = models.CharField(max_length=20,choices=AccessLevelChoices.choices,default=AccessLevelChoices.SCHOOL,)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey( CustomUser, on_delete=models.SET_NULL, null=True, related_name="created_roles")

    class Meta:
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
        ordering = ["permissions_tier", "name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["role_category", "permissions_tier"]),
        ]

    def __str__(self):
        return f"{self.name} (Tier: {self.permissions_tier})"

    def clean(self):
        super().clean()
        if (
            self.access_level == AccessLevelChoices.SCHOOL
            and "regional" in self.name.lower()
        ):
            raise ValidationError(_("Regional roles cannot have school-level access"))
        if (
            self.access_level == AccessLevelChoices.COUNTY
            and "principal" in self.name.lower()
        ):
            raise ValidationError(_("Principal roles cannot have county-level access"))

    def get_default_dashboard_url(self):
        if self.default_dashboard:
            return self.default_dashboard
        if self.role_category == RoleCategoryChoices.ACADEMIC:
            return "/academic/dashboard/"
        elif self.role_category == RoleCategoryChoices.ADMINISTRATIVE:
            return "/admin/dashboard/"
        elif self.role_category == RoleCategoryChoices.SUPPORT:
            return "/support/dashboard/"
        return "/dashboard/"


class UserRole(models.Model):
    """Links users to roles with school context"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_assignments")
    school = models.ForeignKey("schools.School",on_delete=models.SET_NULL, null=True,blank=True,related_name="users",help_text=_("School where this role applies (null for county/national roles)"),)
    is_primary_role = models.BooleanField(default=False)
    assigned_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="assigned_roles")
    assigned_date = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("User Role Assignment")
        verbose_name_plural = _("User Role Assignments")
        ordering = ["-assigned_date"]
        constraints = [
                models.UniqueConstraint(
                    fields=["user", "role", "school"],
                    name="unique_user_role_school",
                )
            ]
        indexes = [
            models.Index(fields=["user", "is_primary_role"]),
            models.Index(fields=["school", "role"]),
            models.Index(fields=["valid_until", "is_active"]),
        ]

    def __str__(self):
        school_name = self.school.school_name if self.school else _("County/National")
        return f"{self.user.login_id} as {self.role.name} at {school_name}"

    def clean(self):
        super().clean()

        if self.valid_until and self.valid_until < timezone.now():
            raise ValidationError(
                {"valid_until": _("Expiry date cannot be in the past")}
            )

        if self.is_primary_role:
            existing = UserRole.objects.filter(
                user=self.user, school=self.school, is_primary_role=True, is_active=True
            ).exclude(id=self.id)
            if existing.exists():
                raise ValidationError(
                    {
                        "is_primary_role": _(
                            "User already has a primary role for this school"
                        )
                    }
                )

        if self.role.access_level == AccessLevelChoices.SCHOOL and not self.school:
            raise ValidationError(
                {"school": _("School is required for school-level roles")}
            )

        if (
            self.role.access_level
            in [AccessLevelChoices.COUNTY,AccessLevelChoices.NATIONAL]
            and self.school
        ):
            raise ValidationError(
                {"school": _("School must be null for county/national roles")}
            )

    def is_expired(self):
        return self.valid_until and timezone.now() > self.valid_until

    def get_effective_role(self):
        return self.role if self.is_active and not self.is_expired() else None


class PermissionMatrix(models.Model):
    """Defines detailed permissions for each role"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    module = models.CharField(max_length=50, choices=ModuleChoices.choices)
    action = models.CharField(max_length=20, choices=ActionChoices.choices)
    resource_scope = models.CharField(max_length=20,choices=ResourceScopeChoices.choices,default=ResourceScopeChoices.SCHOOL,)
    conditions = models.JSONField(default=dict)
    is_allowed = models.BooleanField(default=True)
    priority = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(CustomUser,on_delete=models.SET_NULL,null=True,related_name="created_permissions",)

    class Meta:
        verbose_name = _("Permission Matrix")
        verbose_name_plural = _("Permission Matrix")
        ordering = ["role", "module", "action"]
        unique_together = [["role", "module", "action", "resource_scope"]]
        permissions = [("manage_permissions", _("Can manage permission matrix"))]
        indexes = [
            models.Index(fields=["role", "module"]),
            models.Index(fields=["module", "action"]),
        ]

    def __str__(self):
        status = "ALLOW" if self.is_allowed else "DENY"
        return f"{status} {self.role.name} to {self.action} in {self.module} ({self.resource_scope})"

    def check_permission(self, user, obj=None, school=None):
        if not self.is_allowed:
            return False

        if self.conditions:
            return self._check_conditions(user, obj, school)

        return True

    def _check_conditions(self, user, obj, school):
        if self.conditions.get("must_be_owner") and obj and hasattr(obj, "created_by"):
            return obj.created_by == user

        if "time_restriction" in self.conditions:
            restriction = self.conditions["time_restriction"]
            now = timezone.now().time()
            if "start" in restriction and now < restriction["start"]:
                return False
            if "end" in restriction and now > restriction["end"]:
                return False

        return True


class AuditLog(models.Model):
    """
    Tamper-proof audit trail
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    user_role = models.CharField(max_length=100, help_text=_("Role at time of action"))
    user_ip = models.GenericIPAddressField(null=True, blank=True)
    user_device = models.CharField(max_length=200, blank=True, null=True)
    action_type = models.CharField(max_length=30, choices=AuditActionChoices.choices)
    model_name = models.CharField(max_length=100)
    record_id = models.UUIDField(null=True, blank=True)
    field_changed = models.CharField(max_length=100, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    approval_required = models.BooleanField(default=False)
    approved_by = models.ForeignKey( CustomUser,on_delete=models.SET_NULL, null=True,blank=True,related_name="approved_logs",)
    school = models.ForeignKey("schools.School", on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    gps_coordinates = PointField(null=True, blank=True, help_text=_("GPS if available"))
    session_id = models.CharField(max_length=100, blank=True, null=True)
    checksum = models.CharField( max_length=64, blank=True, null=True, help_text=_("For tamper detection"))
    blockchain_hash = models.CharField(max_length=256, blank=True, null=True, help_text=_("Future blockchain integration"), )

    class Meta:
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Logs")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["record_id"]),
            models.Index(fields=["action_type", "timestamp"]),
        ]
    def __str__(self):
        return f"{self.action_type} on {self.model_name} by {self.user} at {self.timestamp}"


class LoginHistory(models.Model):
    """
    Tracks changes to a user's login_id over time.
    Supports transfers, role changes, demotions, etc.
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="login_history")
    old_login_id = models.CharField(max_length=50)
    new_login_id = models.CharField(max_length=50)
    reason = models.CharField( max_length=255,help_text="Why the ID changed (e.g. 'School transfer', 'Demotion')",)
    changed_by = models.ForeignKey(CustomUser,on_delete=models.SET_NULL,null=True,blank=True,related_name="changed_logins",help_text="Who initiated the change (admin or self)",)
    school = models.ForeignKey("schools.School", on_delete=models.SET_NULL, null=True, blank=True, help_text="School context at time of change")
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Login ID History"
        verbose_name_plural = "Login ID Histories"
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["user", "changed_at"]),
            models.Index(fields=["old_login_id"]),
            models.Index(fields=["new_login_id"]),
        ]

    def __str__(self):
        return f"{self.user.login_id} changed from {self.old_login_id} → {self.new_login_id} ({self.reason})"