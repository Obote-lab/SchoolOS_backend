from django.db import transaction
from rest_framework import serializers

from accounts.services.user_creation_services import UserCreationService
from core.choices.staff import StaffTypeChoices, EmploymentTypeChoices
from ..models import StaffAttendance, StaffProfile
from ..utils import generate_staff_id


# List / Simple
class StaffProfileListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta:
        model = StaffProfile
        fields = [
            "user",
            "staff_id",
            "full_name",
            "email",
            "phone",
            "staff_type",
            "job_title",
            "employment_type",
            "department",
            "is_active",
            "date_employed",
            "performance_score",
            "attendance_rate",
        ]
        read_only_fields = fields


# Detail
class StaffProfileDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta:
        model = StaffProfile
        fields = [
            "user",
            "staff_id",
            "full_name",
            "email",
            "phone",
            "staff_type",
            "employment_type",
            "national_id",
            "tsc_number",
            "kra_pin",
            "nssf_number",
            "nhif_number",
            "date_employed",
            "job_title",
            "department",
            "qualifications",
            "subjects_specialized",
            "teaching_experience",
            "basic_salary",
            "net_salary",
            "performance_score",
            "attendance_rate",
            "emergency_contact_name",
            "emergency_contact_phone",
            "medical_conditions",
            "allergies",
            "signature",
            "is_active",
            "exit_date",
            "exit_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "full_name",
            "email",
            "phone",
            "created_at",
            "updated_at",
        ]


# Create
class StaffProfileCreateSerializer(serializers.ModelSerializer):
    """Create a new staff member + linked user account."""

    first_name = serializers.CharField(write_only=True, required=True)
    last_name = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = StaffProfile
        fields = [
            "staff_type",
            "employment_type",
            "tsc_number",
            "national_id",
            "date_employed",
            "job_title",
            "department",
            "first_name",
            "last_name",
            "email",
            "phone",
        ]

    def validate(self, data):
        request = self.context["request"]
        creator = request.user
        school = getattr(request, "school", None) or creator.school

        if not school and not creator.is_superuser:
            raise serializers.ValidationError(
                {"school": "School context is required to create staff."}
            )

        return data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        creator = request.user
        school = getattr(request, "school", None) or creator.school

        staff_type = validated_data["staff_type"]
        staff_id = generate_staff_id(school, staff_type)

        user_data = {
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "email": validated_data.pop("email", None) or None,
            "phone": validated_data.pop("phone", None) or None,
        }
        user_data = {k: v for k, v in user_data.items() if v}

        # Map staff_type → Role name
        role_mapping = {
            StaffTypeChoices.TEACHER: "Teacher",
            StaffTypeChoices.PRINCIPAL: "Principal",
            StaffTypeChoices.DEPUTY: "Deputy Principal",
            StaffTypeChoices.HOD: "Head of Department",
            StaffTypeChoices.ADMIN: "Administrator",
            StaffTypeChoices.MATRON: "Matron",
            StaffTypeChoices.SECURITY: "Security Officer",
            StaffTypeChoices.DRIVER: "Driver",
            StaffTypeChoices.COOK: "Cook",
            StaffTypeChoices.NURSE: "Nurse",
            StaffTypeChoices.LIBRARIAN: "Librarian",
            StaffTypeChoices.LAB_TECH: "Lab Technician",
            StaffTypeChoices.OTHER: "Support Staff",
        }
        role_name = role_mapping.get(staff_type, "Support Staff")

        user = UserCreationService.create_user(
            creator=creator,
            school=school,
            user_data=user_data,
            role_name=role_name,
            send_email=True,
        )

        staff = StaffProfile.objects.create(
            user=user,
            school=school,
            staff_id=staff_id,
            **validated_data,
        )
        return staff


# Update
class StaffProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffProfile
        fields = [
            "staff_type",
            "employment_type",
            "tsc_number",
            "national_id",
            "job_title",
            "department",
            "basic_salary",
            "net_salary",
            "is_active",
            "exit_date",
            "exit_reason",
            "emergency_contact_name",
            "emergency_contact_phone",
            "medical_conditions",
            "allergies",
        ]


# Attendance
class StaffAttendanceListSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.user.get_full_name", read_only=True)
    staff_id = serializers.CharField(source="staff.staff_id", read_only=True)

    class Meta:
        model = StaffAttendance
        fields = [
            "id",
            "staff",
            "staff_id",
            "staff_name",
            "date",
            "status",
            "notes",
            "recorded_by",
            "created_at",
        ]
        read_only_fields = ["id", "staff_name", "staff_id", "created_at"]


class StaffAttendanceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffAttendance
        fields = ["staff", "date", "status", "notes"]

    def validate(self, data):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        staff = data["staff"]
        school = getattr(request, "school", None) or request.user.school

        if school and staff.school_id != school.id and not request.user.is_superuser:
            raise serializers.ValidationError(
                "Cannot record attendance for staff from another school."
            )

        if StaffAttendance.objects.filter(staff=staff, date=data["date"]).exists():
            raise serializers.ValidationError(
                "Attendance record already exists for this date."
            )

        return data

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["recorded_by"] = request.user
        return super().create(validated_data)


class StaffDeactivateSerializer(serializers.Serializer):
    exit_date = serializers.DateField(required=False)
    exit_reason = serializers.CharField(required=False, allow_blank=True)