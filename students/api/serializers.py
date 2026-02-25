from django.db import transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.services.user_creation_services import UserCreationService
from schools.models import School
from ..models import ParentGuardian, Student, StudentMedicalHistory



#   Utility / Nested Serializers
class ParentGuardianSimpleSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta:
        model = ParentGuardian
        fields = [
            "id",
            "full_name",
            "phone",
            "relationship",
            "is_primary",
            "can_pickup",
            "can_consent",
        ]
        read_only_fields = fields


class StudentSimpleSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    class_name = serializers.CharField(source="current_class.classroom_name", read_only=True, allow_null=True)

    class Meta:
        model = Student
        fields = [
            "id",
            "admission_number",
            "full_name",
            "class_name",
            "gender",
            "student_status",
            "student_category",
            "admission_date",
        ]
        read_only_fields = fields



#   Student Serializers
class StudentSerializer(serializers.ModelSerializer):
    """Full detail serializer for Student"""
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    age = serializers.IntegerField(read_only=True)
    class_name = serializers.CharField(source="current_class.classroom_name", read_only=True, allow_null=True)
    school_name = serializers.CharField(source="school.school_name", read_only=True)
    parents = ParentGuardianSimpleSerializer(source="guardians", many=True, read_only=True)

    class Meta:
        model = Student
        fields = [
            "id",
            "admission_number",
            "user",
            "full_name",
            "school",
            "school_name",
            "current_class",
            "class_name",
            "admission_date",
            "registration_date",
            "date_of_birth",
            "age",
            "gender",
            "nationality",
            "county_of_origin",
            "allergies",
            "emer_contact_name",
            "emer_contact_phone",
            "emer_contact_relation",
            "emer_contact_alternate_phone",
            "previous_school",
            "kcpe_index",
            "boarding_house",
            "student_category",
            "sponsor",
            "student_status",
            "status_reason",
            "exit_date",
            "parents",
            "current_academic_year",
            "current_term",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "full_name",
            "age",
            "class_name",
            "school_name",
            "parents",
            "created_at",
            "updated_at",
        ]


class StudentCreateSerializer(serializers.ModelSerializer):
    """Create a new student + linked user account"""
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Student
        fields = [
            "admission_number",
            "current_class",
            "admission_date",
            "date_of_birth",
            "gender",
            "nationality",
            "county_of_origin",
            "allergies",
            "emer_contact_name",
            "emer_contact_phone",
            "emer_contact_relation",
            "emer_contact_alternate_phone",
            "previous_school",
            "kcpe_index",
            "student_category",
            "sponsor",
            "first_name",
            "last_name",
            "email",
            "phone",
        ]

    def validate(self, data):
        request = self.context["request"]
        creator = request.user
        school = creator.school

        # School must match creator's school (unless system admin)
        if not creator.is_superuser and school != creator.school:
            raise serializers.ValidationError({"school": "Cannot create student for another school"})

        # Class capacity check
        current_class = data.get("current_class")
        if current_class and current_class.school != school:
            raise serializers.ValidationError({"current_class": "Class does not belong to this school"})

        if current_class and current_class.current_enrollment >= current_class.capacity:
            raise serializers.ValidationError({"current_class": "Class is already at full capacity"})

        # Age validation (re-use model logic)
        dob = data.get("date_of_birth")
        if dob:
            from .utils import validate_age
            validate_age(dob)

        return data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        creator = request.user
        school = creator.school

        # Extract user creation fields
        user_data = {
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "email": validated_data.pop("email", None),
            "phone": validated_data.pop("phone", None),
            "gender": validated_data.get("gender"),
        }

        # Create user via service (generates login_id, etc.)
        result = UserCreationService.create_user(
            creator=creator,
            school=school,
            user_type="STU",
            user_data=user_data
        )
        user = result["user"]

        # Create student profile
        student = Student.objects.create(
            user=user,
            school=school,
            **validated_data
        )

        return student


class StudentUpdateSerializer(serializers.ModelSerializer):
    """Update existing student (limited fields)"""

    class Meta:
        model = Student
        fields = [
            "current_class",
            "allergies",
            "emer_contact_name",
            "emer_contact_phone",
            "emer_contact_relation",
            "emer_contact_alternate_phone",
            "previous_school",
            "kcpe_index",
            "boarding_house",
            "student_category",
            "sponsor",
            "student_status",
            "status_reason",
            "exit_date",
        ]

    def validate_current_class(self, value):
        if value and value.current_enrollment >= value.capacity:
            raise serializers.ValidationError("Class is already at full capacity")
        return value

    def validate_exit_date(self, value):
        if value and value > timezone.now().date():
            raise serializers.ValidationError("Exit date cannot be in the future")
        return value


class StudentStatusUpdateSerializer(serializers.Serializer):
    """Dedicated serializer for changing student status"""

    student_status = serializers.ChoiceField(choices=Student.StudentStatusChoices.choices)
    reason = serializers.CharField(required=False, allow_blank=True)
    exit_date = serializers.DateField(required=False)

    def validate(self, data):
        student = self.context["student"]
        new_status = data["student_status"]

        # Basic transition rules (expand as needed)
        terminal_statuses = {
            Student.StudentStatusChoices.TRANSFERRED,
            Student.StudentStatusChoices.GRADUATED,
            Student.StudentStatusChoices.EXPELLED,
            Student.StudentStatusChoices.WITHDRAWN,
        }

        if new_status in terminal_statuses and not data.get("exit_date"):
            raise serializers.ValidationError({
                "exit_date": f"Required when changing to {new_status}"
            })

        if new_status == student.student_status:
            raise serializers.ValidationError("Status is already set to this value")

        return data



#   ParentGuardian Serializers
class ParentGuardianSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = ParentGuardian
        fields = [
            "id",
            "user",
            "full_name",
            "phone",
            "email",
            "student",
            "student_name",
            "relationship",
            "is_primary",
            "can_pickup",
            "can_consent",
            "alternate_phone",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "student_name",
            "created_at",
            "updated_at",
        ]


class ParentGuardianCreateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    phone = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = ParentGuardian
        fields = [
            "student",
            "relationship",
            "is_primary",
            "can_pickup",
            "can_consent",
            "alternate_phone",
            "first_name",
            "last_name",
            "email",
            "phone",
            "password",
        ]

    def validate(self, data):
        student = data["student"]
        creator = self.context["request"].user

        if student.school != creator.school and not creator.is_superuser:
            raise serializers.ValidationError("Cannot add parent to student from another school")

        return data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        creator = request.user
        school = creator.school
        student = validated_data.pop("student")

        user_data = {
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "email": validated_data.pop("email", None),
            "phone": validated_data.pop("phone"),
        }

        result = UserCreationService.create_user(
            creator=creator,
            school=school,
            user_type="PAR",
            user_data=user_data
        )
        user = result["user"]
        user.set_password(validated_data.pop("password"))
        user.save(update_fields=["password"])

        parent = ParentGuardian.objects.create(
            user=user,
            student=student,
            **validated_data
        )

        return parent


#   Medical History Serializers
class StudentMedicalHistorySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    admission_number = serializers.CharField(source="student.admission_number", read_only=True)
    logged_by_name = serializers.CharField(source="logged_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = StudentMedicalHistory
        fields = [
            "id",
            "student",
            "student_name",
            "admission_number",
            "record_type",
            "description",
            "doctor_name",
            "hospital",
            "date",
            "follow_up_date",
            "medication",
            "logged_by",
            "logged_by_name",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "student_name",
            "admission_number",
            "logged_by_name",
            "created_at",
        ]


class MedicalHistoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentMedicalHistory
        fields = [
            "student",
            "record_type",
            "description",
            "doctor_name",
            "hospital",
            "date",
            "follow_up_date",
            "medication",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["logged_by"] = request.user
        return super().create(validated_data)



#   Search / Utility Serializers
class StudentSearchSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True)
    school = serializers.UUIDField(required=False)
    current_class = serializers.UUIDField(required=False)
    student_status = serializers.ChoiceField(
        choices=Student.StudentStatusChoices.choices, required=False
    )
    student_category = serializers.ChoiceField(
        choices=Student.StudentCategoryChoices.choices, required=False
    )
    gender = serializers.ChoiceField(choices=Student.GenderChoices.choices, required=False)

    def validate(self, data):
        if not any(data.values()):
            raise serializers.ValidationError("Provide at least one search parameter")
        return data