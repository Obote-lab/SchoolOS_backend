from django.contrib.gis.geos import Point
from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ..models import AcademicYear, ClassRoom, Department, School, Term
from ..services.onboarding import SchoolOnboardingService
from accounts.api.serializers import CustomUserSerializer  
from accounts.models import UserRole

import logging
logger = logging.getLogger(__name__)



#   SCHOOL SERIALIZERS
class SchoolSimpleSerializer(serializers.ModelSerializer):
    """Minimal serializer for lists and search results"""
    class Meta:
        model = School
        fields = [
            "id", "school_name", "school_code", "county",
            "type", "school_category", "is_active"
        ]


class SchoolSerializer(serializers.ModelSerializer):
    """Full school detail serializer"""
    enrollment_percentage = serializers.SerializerMethodField()
    vacancy_count = serializers.SerializerMethodField()
    principal_name = serializers.CharField(source="principal.get_full_name", read_only=True)
    deputy_academic_name = serializers.CharField(source="deputy_academic.get_full_name", read_only=True)
    deputy_admin_name = serializers.CharField(source="deputy_admin.get_full_name", read_only=True)
    gps_coordinates = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Format: "latitude,longitude" e.g. "-1.2921,36.8219"'
    )
    onboarded_by_name = serializers.CharField(source="onboarded_by.get_full_name", read_only=True)
    first_principal_name = serializers.CharField(source="first_principal.get_full_name", read_only=True)
    is_in_trial = serializers.BooleanField(read_only=True)
    trial_days_remaining = serializers.IntegerField(read_only=True)
    needs_onboarding_attention = serializers.BooleanField(read_only=True)
    onboarding_checklist = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = [
            "id", "school_name", "school_code", "type", "school_category",
            "county", "sub_county", "ward", "address", "gps_coordinates",
            "phone", "email",
            "principal", "principal_name",
            "deputy_academic", "deputy_academic_name",
            "deputy_admin", "deputy_admin_name",
            "boarding_status", "capacity", "current_enrollment",
            "establishment_year", "registration_number", "nemis_code",
            "tsc_code", "knec_center_number", "bank_account",
            "school_motto", "vision", "mission", "logo", "banner",
            "school_settings", "is_active",
            "enrollment_percentage", "vacancy_count",
            "created_at", "updated_at", "created_by",
            "onboarding_status", "onboarding_progress",
            "onboarded_by", "onboarded_by_name", "onboarded_date",
            "first_principal", "first_principal_name",
            "trial_start_date", "trial_end_date", "subscription_tier",
            "is_in_trial", "trial_days_remaining",
            "needs_onboarding_attention", "onboarding_checklist",
        ]
        read_only_fields = [
            "id", "enrollment_percentage", "vacancy_count",
            "created_at", "updated_at", "onboarding_status",
            "onboarding_progress", "is_in_trial", "trial_days_remaining",
            "needs_onboarding_attention",
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Consistent GPS string output
        if instance.gps_coordinates:
            ret['gps_coordinates'] = f"{instance.gps_coordinates.y},{instance.gps_coordinates.x}"
        else:
            ret['gps_coordinates'] = None
        return ret

    def validate_gps_coordinates(self, value):
        if value and value.strip():
            try:
                lat, lng = map(float, value.split(","))
                return Point(lng, lat)  # GeoDjango: x=longitude, y=latitude
            except (ValueError, TypeError):
                raise serializers.ValidationError('Must be "latitude,longitude" e.g. "-1.2921,36.8219"')
        return None

    def get_enrollment_percentage(self, obj):
        return obj.enrollment_percentage

    def get_vacancy_count(self, obj):
        return obj.vacancy_count

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_onboarding_checklist(self, obj):
        return SchoolOnboardingService.get_onboarding_checklist(obj)


class SchoolCreateSerializer(serializers.ModelSerializer):
    """Create school + principal in one request"""
    principal_data = serializers.DictField(
        write_only=True,
        required=True,
        help_text="Required keys: first_name, last_name, email, phone, gender, etc."
    )
    auto_setup_structures = serializers.BooleanField(
        default=True,
        write_only=True,
        help_text="Automatically create academic year, terms, sample classrooms"
    )

    class Meta:
        model = School
        fields = [
            "school_name", "school_code", "type", "school_category",
            "county", "sub_county", "ward", "address", "phone", "email",
            "boarding_status", "capacity", "establishment_year",
            "registration_number", "nemis_code",
            "principal_data", "auto_setup_structures"
        ]

    def validate(self, data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        user = request.user
        if not (user.is_system_root or UserRole.objects.filter(
            user=user, role__name="Regional Admin", is_active=True
        ).exists()):
            raise serializers.ValidationError("Only System Root or Regional Admins can create schools.")

        # Regional admin county restriction
        if UserRole.objects.filter(user=user, role__name="Regional Admin").exists():
            allowed_counties = user.managed_counties.values_list("name", flat=True)
            if data.get("county") and data["county"] not in allowed_counties:
                raise serializers.ValidationError({
                    "county": f"Regional Admins can only create schools in: {', '.join(allowed_counties)}"
                })

        return data

    @transaction.atomic
    def create(self, validated_data):
        principal_data = validated_data.pop("principal_data")
        auto_setup = validated_data.pop("auto_setup_structures", True)
        request = self.context.get("request")

        from ..services.onboarding import SchoolOnboardingService

        school, principal_result = SchoolOnboardingService.create_school_with_principal(
            school_data=validated_data,
            principal_data=principal_data,
            creator=request.user if request else None
        )

        if auto_setup:
            SchoolOnboardingService.setup_basic_structures(school, request.user if request else None)

        return school


class SchoolUpdateSerializer(serializers.ModelSerializer):
    """Update basic school information"""

    class Meta:
        model = School
        fields = [
            "school_name", "type", "school_category", "county", "sub_county", "ward",
            "address", "gps_coordinates", "phone", "email",
            "principal", "deputy_academic", "deputy_admin",
            "boarding_status", "capacity",
            "school_motto", "vision", "mission", "logo", "banner",
            "school_settings", "is_active"
        ]

    def validate_principal(self, value):
        if value and value.user_type != "PRN":
            raise serializers.ValidationError("Principal must have user_type 'PRN'")
        return value

    def validate_deputy_academic(self, value):
        if value and value.user_type not in ["PRN", "DEP"]:
            raise serializers.ValidationError("Deputy must have user_type 'PRN' or 'DEP'")
        return value

    def validate_deputy_admin(self, value):
        if value and value.user_type not in ["PRN", "DEP"]:
            raise serializers.ValidationError("Deputy must have user_type 'PRN' or 'DEP'")
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
            "id", "school", "school_name", "year", "label",
            "start_date", "end_date", "is_current", "is_active",
            "terms_count", "holidays", "important_dates",
            "created_at", "updated_at", "created_by", "created_by_name"
        ]
        read_only_fields = ["id", "is_active", "created_at", "updated_at"]

    def get_is_active(self, obj):
        return obj.is_active

    def validate(self, data):
        if data.get("is_current"):
            qs = AcademicYear.objects.filter(school=data["school"], is_current=True)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    "is_current": "Only one academic year can be current per school"
                })
        return data


class TermSerializer(serializers.ModelSerializer):
    duration_days = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    is_current = serializers.SerializerMethodField()
    academic_year_label = serializers.CharField(source="academic_year.label", read_only=True)

    class Meta:
        model = Term
        fields = [
            "id", "academic_year", "academic_year_label", "name", "sequence",
            "start_date", "end_date", "midterm_break_start", "midterm_break_end",
            "fee_due_date", "exam_start_date", "exam_end_date", "term_status",
            "duration_days", "days_remaining", "is_current",
            "created_at", "updated_at"
        ]
        read_only_fields = [
            "id", "duration_days", "days_remaining", "is_current",
            "term_status", "created_at", "updated_at"
        ]

    def get_duration_days(self, obj):
        return obj.duration_days

    def get_days_remaining(self, obj):
        return obj.days_remaining

    def get_is_current(self, obj):
        return obj.is_current


#   CLASSROOM & DEPARTMENT
class ClassRoomSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassRoom
        fields = ["id", "classroom_name", "level", "stream", "capacity", "current_enrollment"]


class ClassRoomSerializer(serializers.ModelSerializer):
    vacancy_count = serializers.SerializerMethodField()
    occupancy_percentage = serializers.SerializerMethodField()
    school_name = serializers.CharField(source="school.school_name", read_only=True)
    class_teacher_name = serializers.CharField(source="class_teacher.get_full_name", read_only=True)
    assistant_teacher_name = serializers.CharField(source="assistant_teacher.get_full_name", read_only=True)

    class Meta:
        model = ClassRoom
        fields = [
            "id", "school", "school_name", "level", "stream", "classroom_name",
            "class_teacher", "class_teacher_name", "assistant_teacher", "assistant_teacher_name",
            "capacity", "current_enrollment", "room_number", "building", "floor",
            "has_smart_board", "has_projector", "subject_specialization",
            "year_group", "average_performance", "attendance_rate",
            "vacancy_count", "occupancy_percentage",
            "created_at", "updated_at"
        ]
        read_only_fields = [
            "id", "vacancy_count", "occupancy_percentage",
            "created_at", "updated_at"
        ]

    def get_vacancy_count(self, obj):
        return obj.vacancy_count

    def get_occupancy_percentage(self, obj):
        return obj.occupancy_percentage


class DepartmentSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.school_name", read_only=True)
    head_of_department_name = serializers.CharField(source="head_of_department.get_full_name", read_only=True)
    assistant_hod_name = serializers.CharField(source="assistant_hod.get_full_name", read_only=True)

    class Meta:
        model = Department
        fields = [
            "id", "school", "school_name", "department_name", "department_code",
            "head_of_department", "head_of_department_name",
            "assistant_hod", "assistant_hod_name",
            "description", "color_code", "budget", "member_count",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]



class SystemSchoolOnboardSerializer(serializers.Serializer):
    school_data = serializers.DictField(required=True)
    principal_data = serializers.DictField(required=True)
    auto_setup_structures = serializers.BooleanField(default=True)

class SystemBulkOnboardSerializer(serializers.Serializer):
    schools = serializers.ListField(
        child=serializers.DictField(),  
        min_length=1,
        required=True
    )





#   SEARCH & REGIONAL ADMIN SERIALIZERS
class SchoolSearchSerializer(serializers.Serializer):
    """
    Query parameters for advanced school search.
    All fields are optional.
    """
    q = serializers.CharField(required=False, allow_blank=True, help_text="General search: name, code, county, sub-county")
    county = serializers.CharField(required=False, allow_blank=True)
    sub_county = serializers.CharField(required=False, allow_blank=True)
    type = serializers.ChoiceField(choices=School.SchoolTypeChoices.choices,required=False,allow_blank=True)
    school_category = serializers.ChoiceField(choices=School.SchoolCategoryChoices.choices,required=False,allow_blank=True )
    onboarding_status = serializers.ChoiceField(choices=School.OnboardingStatusChoices.choices,required=False,allow_blank=True)
    is_active = serializers.BooleanField(required=False, default=None)
    min_enrollment = serializers.IntegerField(required=False, min_value=0)
    max_enrollment = serializers.IntegerField(required=False, min_value=0)
    has_principal = serializers.BooleanField(required=False, default=None)
    ordering = serializers.CharField(required=False,default="-created_at",help_text="e.g. school_name, -current_enrollment, created_at")


class RegionalAdminCreateSchoolSerializer(serializers.ModelSerializer):
    """
    Serializer used by Regional Admins to create a school.
    Enforces county restriction via view logic.
    Principal is created separately or via nested data.
    """
    principal_email = serializers.EmailField(write_only=True,required=True, help_text="Email of the principal (will be used to create/link user)" )
    principal_full_name = serializers.CharField(write_only=True, required=True, max_length=255)
    auto_create_principal = serializers.BooleanField(default=True, write_only=True)

    class Meta:
        model = School
        fields = [
            "school_name", "school_code", "type", "school_category",
            "county", "sub_county", "ward", "address", "phone", "email",
            "boarding_status", "capacity", "establishment_year",
            "principal_email", "principal_full_name", "auto_create_principal"
        ]

    def validate_county(self, value):
        request = self.context.get('request')
        user = request.user if request else None
        if user and not user.is_system_root:
            allowed = user.managed_counties.values_list('name', flat=True)
            if value not in allowed:
                raise serializers.ValidationError(
                    f"Regional admins can only create schools in: {', '.join(allowed)}"
                )
        return value