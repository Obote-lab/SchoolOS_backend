import logging
from django.contrib.gis.geos import Point
from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from accounts.models import UserRole
from ..models import AcademicYear, ClassRoom, Department, School, Term
from ..services.onboarding import SchoolOnboardingService
from core.choices.schools import (
    SchoolTypeChoices,
    SchoolCategoryChoices,
    OnboardingStatusChoices,
)

logger = logging.getLogger(__name__)



class PrincipalCreateDataSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)

    def validate(self, data):
        if not data.get("email") and not data.get("phone"):
            raise serializers.ValidationError("Either email or phone is required.")
        return data

class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()



#   SCHOOL SERIALIZERS
class SchoolSimpleSerializer(serializers.ModelSerializer):
    """Minimal serializer for lists and search results"""

    class Meta:
        model = School
        fields = [
            "id",
            "school_name",
            "school_code",
            "county",
            "school_type",
            "school_category",
            "is_active",
        ]


class SchoolSerializer(serializers.ModelSerializer):
    """Full school detail serializer"""

    enrollment_percentage = serializers.SerializerMethodField()
    vacancy_count = serializers.SerializerMethodField()
    principal_name = serializers.CharField(source="principal.get_full_name", read_only=True)
    deputy_academic_name = serializers.CharField(source="deputy_academic.get_full_name", read_only=True)
    deputy_admin_name = serializers.CharField(source="deputy_admin.get_full_name", read_only=True)
    gps_coordinates = serializers.CharField(required=False,allow_blank=True,help_text='Format: "latitude,longitude" e.g. "-1.2921,36.8219"',)
    onboarded_by_name = serializers.CharField(source="onboarded_by.get_full_name", read_only=True)
    first_principal_name = serializers.CharField(source="first_principal.get_full_name", read_only=True)
    is_in_trial = serializers.BooleanField(read_only=True)
    trial_days_remaining = serializers.IntegerField(read_only=True)
    needs_onboarding_attention = serializers.BooleanField(read_only=True)
    onboarding_checklist = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = [
            "id",
            "school_name",
            "school_code",
            "school_type",
            "school_category",
            "county",
            "sub_county",
            "ward",
            "address",
            "gps_coordinates",
            "phone",
            "email",
            "principal",
            "principal_name",
            "deputy_academic",
            "deputy_academic_name",
            "deputy_admin",
            "deputy_admin_name",
            "boarding_status",
            "capacity",
            "current_enrollment",
            "establishment_year",
            "registration_number",
            "nemis_code",
            "tsc_code",
            "knec_center_number",
            "bank_account",
            "school_motto",
            "vision",
            "mission",
            "logo",
            "banner",
            "school_settings",
            "is_active",
            "enrollment_percentage",
            "vacancy_count",
            "created_at",
            "updated_at",
            "created_by",
            "onboarding_status",
            "onboarding_progress",
            "onboarded_by",
            "onboarded_by_name",
            "onboarded_date",
            "first_principal",
            "first_principal_name",
            "trial_start_date",
            "trial_end_date",
            "subscription_tier",
            "is_in_trial",
            "trial_days_remaining",
            "needs_onboarding_attention",
            "onboarding_checklist",
        ]
        read_only_fields = [
            "id",
            "enrollment_percentage",
            "vacancy_count",
            "created_at",
            "updated_at",
            "onboarding_status",
            "onboarding_progress",
            "is_in_trial",
            "trial_days_remaining",
            "needs_onboarding_attention",
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Consistent GPS string output
        if instance.gps_coordinates:
            ret["gps_coordinates"] = (
                f"{instance.gps_coordinates.y},{instance.gps_coordinates.x}"
            )
        else:
            ret["gps_coordinates"] = None
        return ret

    def validate_gps_coordinates(self, value):
        if value and value.strip():
            try:
                lat, lng = map(float, value.split(","))
                return Point(lng, lat)  # GeoDjango: x=longitude, y=latitude
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    'Must be "latitude,longitude" e.g. "-1.2921,36.8219"'
                )
        return None

    @extend_schema_field(OpenApiTypes.FLOAT)
    def get_enrollment_percentage(self, obj) -> float:
        return obj.enrollment_percentage

    @extend_schema_field(OpenApiTypes.INT)
    def get_vacancy_count(self, obj) -> int:
        return obj.vacancy_count

    @extend_schema_field({
    "type": "object",
    "properties": {
            "has_principal": {"type": "boolean"},
            "has_academic_year": {"type": "boolean"},
            "has_classrooms": {"type": "boolean"},
            "onboarding_status": {"type": "string"},
            },
        })
    def get_onboarding_checklist(self, obj) -> dict:
        return {
            "has_principal": obj.principal_id is not None,
            "has_academic_year": obj.academic_years.exists(),
            "has_classrooms": obj.classrooms.exists(),
            "onboarding_status": obj.onboarding_status,
        }

class SchoolOnboardedResponseSerializer(serializers.Serializer):
    """Response after create school + principal (+ optional structures)."""
    school = SchoolSerializer()
    principal_login_id = serializers.CharField()
    message = serializers.CharField()


class SchoolCreateSerializer(serializers.ModelSerializer):
    """Create school + principal in one request"""

    principal_data = PrincipalCreateDataSerializer(write_only=True)
    auto_setup_structures = serializers.BooleanField(
        default=True,
        write_only=True,
        help_text="Create academic year (terms via signal) and sample classrooms",
    )

    class Meta:
        model = School
        fields = [
            "school_name",
            "school_code",
            "school_type",
            "school_category",
            "county",
            "sub_county",
            "ward",
            "address",
            "phone",
            "email",
            "boarding_status",
            "capacity",
            "establishment_year",
            "registration_number",
            "nemis_code",
            "principal_data",
            "auto_setup_structures",
        ]

    def validate(self, data):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        user = request.user

        # Allow superusers or users with Regional Admin / County Admin / System Root role
        can_create = user.is_superuser or user.user_roles.filter(
            is_active=True,
            role__name__in=["Regional Admin", "County Admin", "System Root"],
        ).exists()

        if not can_create:
            raise serializers.ValidationError(
                "Only System Root, Regional Admins or County Admins can create schools."
            )

        return data

    @transaction.atomic
    def create(self, validated_data):
        principal_data = validated_data.pop("principal_data")
        auto_setup = validated_data.pop("auto_setup_structures", True)
        request = self.context.get("request")

        school, principal = SchoolOnboardingService.create_school_with_principal(
            school_data=validated_data,
            principal_data=principal_data,
            creator=request.user,
        )

        if auto_setup:
            SchoolOnboardingService.setup_basic_structures(school, request.user)

        return school


class SchoolUpdateSerializer(serializers.ModelSerializer):
    """Update basic school information"""

    class Meta:
        model = School
        fields = [
            "school_name",
            "school_type",
            "school_category",
            "county",
            "sub_county",
            "ward",
            "address",
            "gps_coordinates",
            "phone",
            "email",
            "principal",
            "deputy_academic",
            "deputy_admin",
            "boarding_status",
            "capacity",
            "school_motto",
            "vision",
            "mission",
            "logo",
            "banner",
            "school_settings",
            "is_active",
        ]

    def validate_principal(self, value):
        if not value:
            return value
        school = self.instance
        qs = UserRole.objects.filter(
            user=value,
            role__name__iexact="Principal",
            is_active=True,
        )
        if school is not None:
            qs = qs.filter(school=school)
        if not qs.exists():
            raise serializers.ValidationError(
                "User must have an active Principal role for this school."
            )
        return value

    def validate_deputy_academic(self, value):
        if value:
            has_role = UserRole.objects.filter(
                user=value,
                role__name__in=["Principal", "Deputy Principal"],
                is_active=True,
            ).exists()
            if not has_role:
                raise serializers.ValidationError(
                    "User must have Principal or Deputy Principal role."
                )
        return value

    def validate_deputy_admin(self, value):
        if value:
            has_role = UserRole.objects.filter(
                user=value,
                role__name__in=["Principal", "Deputy Principal"],
                is_active=True,
            ).exists()
            if not has_role:
                raise serializers.ValidationError(
                    "User must have Principal or Deputy Principal role."
                )
        return value

#   ACADEMIC YEAR & TERM
class AcademicYearSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ["id", "year", "label", "start_date", "end_date", "is_current"]


class AcademicYearSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()
    school_name = serializers.CharField(source="school.school_name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)

    class Meta:
        model = AcademicYear
        fields = [
            "id",
            "school",
            "school_name",
            "year",
            "label",
            "start_date",
            "end_date",
            "is_current",
            "is_active",
            "terms_count",
            "holidays",
            "important_dates",
            "created_at",
            "updated_at",
            "created_by",
            "created_by_name",
        ]
        read_only_fields = ["id", "is_active", "created_at", "updated_at"]

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_active(self, obj) -> bool:
        return obj.is_active

    def validate(self, data):
        if data.get("is_current"):
            qs = AcademicYear.objects.filter(school=data["school"], is_current=True)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"is_current": "Only one academic year can be current per school"}
                )
        return data


class TermSerializer(serializers.ModelSerializer):
    duration_days = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    is_current = serializers.SerializerMethodField()
    academic_year_label = serializers.CharField(source="academic_year.label", read_only=True)

    class Meta:
        model = Term
        fields = [
            "id",
            "academic_year",
            "academic_year_label",
            "name",
            "sequence",
            "start_date",
            "end_date",
            "midterm_break_start",
            "midterm_break_end",
            "fee_due_date",
            "exam_start_date",
            "exam_end_date",
            "term_status",
            "duration_days",
            "days_remaining",
            "is_current",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "duration_days",
            "days_remaining",
            "is_current",
            "term_status",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(OpenApiTypes.INT)
    def get_duration_days(self, obj) -> int:
        return obj.duration_days

    @extend_schema_field(OpenApiTypes.INT)
    def get_days_remaining(self, obj) -> int:
        return obj.days_remaining

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_current(self, obj) -> bool:
        return obj.is_current


#   CLASSROOM & DEPARTMENT
class ClassRoomSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassRoom
        fields = [
            "id",
            "classroom_name",
            "level",
            "stream",
            "capacity",
            "current_enrollment",
        ]


class ClassRoomSerializer(serializers.ModelSerializer):
    vacancy_count = serializers.SerializerMethodField()
    occupancy_percentage = serializers.SerializerMethodField()
    school_name = serializers.CharField(source="school.school_name", read_only=True)
    class_teacher_name = serializers.CharField(source="class_teacher.get_full_name", read_only=True)
    assistant_teacher_name = serializers.CharField(source="assistant_teacher.get_full_name", read_only=True)

    class Meta:
        model = ClassRoom
        fields = [
            "id",
            "school",
            "school_name",
            "level",
            "stream",
            "classroom_name",
            "class_teacher",
            "class_teacher_name",
            "assistant_teacher",
            "assistant_teacher_name",
            "capacity",
            "current_enrollment",
            "room_number",
            "building",
            "floor",
            "has_smart_board",
            "has_projector",
            "subject_specialization",
            "year_group",
            "average_performance",
            "attendance_rate",
            "vacancy_count",
            "occupancy_percentage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "vacancy_count",
            "occupancy_percentage",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(OpenApiTypes.INT)
    def get_vacancy_count(self, obj) -> int:
        return obj.vacancy_count

    @extend_schema_field(OpenApiTypes.FLOAT)
    def get_occupancy_percentage(self, obj) -> float:
        return obj.occupancy_percentage


class DepartmentSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.school_name", read_only=True)
    head_of_department_name = serializers.CharField(source="head_of_department.get_full_name", read_only=True)
    assistant_hod_name = serializers.CharField(source="assistant_hod.get_full_name", read_only=True)

    class Meta:
        model = Department
        fields = [
            "id",
            "school",
            "school_name",
            "department_name",
            "department_code",
            "head_of_department",
            "head_of_department_name",
            "assistant_hod",
            "assistant_hod_name",
            "description",
            "color_code",
            "budget",
            "member_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SystemSchoolOnboardSerializer(serializers.Serializer):
    # school fields (subset)
    school_name = serializers.CharField(max_length=255)
    county = serializers.CharField(max_length=100)
    school_type = serializers.ChoiceField(choices=SchoolTypeChoices.choices)
    school_category = serializers.ChoiceField(
        choices=SchoolCategoryChoices.choices, required=False
    )
    sub_county = serializers.CharField(required=False, allow_blank=True)
    ward = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    boarding_status = serializers.CharField(required=False)
    capacity = serializers.IntegerField(required=False, min_value=0)
    # principal
    principal_data = PrincipalCreateDataSerializer()
    auto_setup_structures = serializers.BooleanField(default=True)

    def create(self, validated_data):
        request = self.context["request"]
        principal_data = validated_data.pop("principal_data")
        auto_setup = validated_data.pop("auto_setup_structures", True)
        school, principal = SchoolOnboardingService.create_school_with_principal(
            school_data=validated_data,
            principal_data=principal_data,
            creator=request.user,
        )
        if auto_setup:
            SchoolOnboardingService.setup_basic_structures(school, request.user)
        return school
class SystemBulkOnboardSerializer(serializers.Serializer):
    schools = serializers.ListField(child=serializers.DictField(), min_length=1, required=True)


#   SEARCH & REGIONAL ADMIN SERIALIZERS
class SchoolSearchSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True)
    county = serializers.CharField(required=False, allow_blank=True)
    sub_county = serializers.CharField(required=False, allow_blank=True)
    school_type = serializers.ChoiceField(choices=SchoolTypeChoices.choices, required=False, allow_blank=True)
    school_category = serializers.ChoiceField(choices=SchoolCategoryChoices.choices, required=False, allow_blank=True)
    onboarding_status = serializers.ChoiceField(choices=OnboardingStatusChoices.choices, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False, default=None)
    min_enrollment = serializers.IntegerField(required=False, min_value=0)
    max_enrollment = serializers.IntegerField(required=False, min_value=0)
    has_principal = serializers.BooleanField(required=False, default=None)
    ordering = serializers.CharField(required=False, default="-created_at")
    is_active = serializers.BooleanField(required=False, allow_null=True, default=None)
    has_principal = serializers.BooleanField(required=False, allow_null=True, default=None)



class RegionalAdminCreateSchoolSerializer(serializers.ModelSerializer):
    principal_email = serializers.EmailField(write_only=True, required=True)
    principal_full_name = serializers.CharField(write_only=True, required=True, max_length=255)
    auto_create_principal = serializers.BooleanField(default=True, write_only=True)

    class Meta:
        model = School
        fields = [
            "school_name",
            "school_code",
            "school_type",
            "school_category",
            "county",
            "sub_county",
            "ward",
            "address",
            "phone",
            "email",
            "boarding_status",
            "capacity",
            "establishment_year",
            "principal_email",
            "principal_full_name",
            "auto_create_principal",
        ]

    def validate(self, data):
        request = self.context.get("request")
        user = request.user if request else None

        if not user:
            raise serializers.ValidationError("Authentication required.")

        # Only Regional Admins or superusers
        is_regional = user.user_roles.filter(
            is_active=True, role__name__iexact="Regional Admin"
        ).exists()

        if not (user.is_superuser or is_regional):
            raise serializers.ValidationError(
                "Only Regional Admins can use this endpoint."
            )

        return data

    def create(self, validated_data):
        request = self.context["request"]
        email = validated_data.pop("principal_email")
        full_name = validated_data.pop("principal_full_name")
        auto = validated_data.pop("auto_create_principal", True)

        parts = full_name.strip().split(None, 1)
        principal_data = {
            "first_name": parts[0],
            "last_name": parts[1] if len(parts) > 1 else parts[0],
            "email": email,
        }

        school, principal = SchoolOnboardingService.create_school_with_principal(
            school_data=validated_data,
            principal_data=principal_data,
            creator=request.user,
        )
        return school
