from django.db import transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.services.user_creation_services import UserCreationService
from ..models import ParentGuardian, StudentProfile, StudentMedicalHistory
from core.choices.students import StudentStatusChoices, StudentCategoryChoices
from core.choices.common import GenderChoices as StudentGenderChoices
from ..utils import validate_age 

#  SIMPLE / NESTED SERIALIZERS
class ParentGuardianSimpleSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta:
        model = ParentGuardian
        fields = [
            "user",
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
    class_name = serializers.CharField(
        source="current_class.classroom_name", read_only=True, allow_null=True
    )
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model = StudentProfile
        fields = [
            "user",
            "admission_number",
            "full_name",
            "class_name",
            "age",
            "gender",
            "student_status",
            "student_category",
            "admission_date",
            "risk_score",
        ]
        read_only_fields = fields


#  MAIN STUDENT SERIALIZERS
class StudentSerializer(serializers.ModelSerializer):
    """Full detail serializer for StudentProfile"""

    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    age = serializers.IntegerField(read_only=True)
    class_name = serializers.CharField(
        source="current_class.classroom_name", read_only=True, allow_null=True
    )
    school_name = serializers.CharField(source="school.school_name", read_only=True)
    parents = ParentGuardianSimpleSerializer(many=True, read_only=True)

    class Meta:
        model = StudentProfile
        fields = [
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
            "talents",
            "learning_style",
            "academic_potential",
            "risk_score",
            "student_status",
            "status_reason",
            "exit_date",
            "exit_notes",
            "parents",
            "current_academic_year",
            "current_term",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
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
        model = StudentProfile
        fields = [
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
        school = getattr(request, "school", None) or creator.school

        if not school and not creator.is_superuser:
            raise serializers.ValidationError(
                {"school": "School context is required."}
            )

        current_class = data.get("current_class")
        if current_class and school and current_class.school_id != school.id:
            raise serializers.ValidationError(
                {"current_class": "Class does not belong to this school."}
            )

        dob = data.get("date_of_birth")
        if dob:
            validate_age(dob)

        return data

    
    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        creator = request.user

        # Prefer school from request context (middleware), fallback to creator.school
        school = getattr(request, "school", None) or creator.school
        if not school:
            raise serializers.ValidationError(
                {"school": "School context is required to create a student."}
            )

        user_data = {
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "email": validated_data.pop("email", None) or None,
            "phone": validated_data.pop("phone", None) or None,
            "user_gender": validated_data.get("gender"),
        }

        # Remove empty strings
        user_data = {k: v for k, v in user_data.items() if v}

        user = UserCreationService.create_user(
            creator=creator,
            school=school,
            user_data=user_data,
            role_name="Student",
            send_email=True,
        )

        student = StudentProfile.objects.create(
            user=user,
            school=school,
            **validated_data,
        )
        # student.sync_identity_fields_to_user()

        # Optional defaults from school
        if not student.current_academic_year and getattr(school, "current_academic_year_id", None):
            student.current_academic_year = school.current_academic_year_id
        if not student.current_term and getattr(school, "current_term_id", None):
            student.current_term= school.current_term_id
        if student.current_academic_year or student.current_term:
            student.save(
                update_fields=["current_academic_year", "current_term"],
                validate=False,
            )

        return student


class StudentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
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


class StudentStatusUpdateSerializer(serializers.Serializer):
    student_status = serializers.ChoiceField(
        choices=StudentStatusChoices.choices
    )
    reason = serializers.CharField(required=False, allow_blank=True)
    exit_date = serializers.DateField(required=False)

    def validate(self, data):
        student = self.context["student"]
        new_status = data["student_status"]

        terminal_statuses = {
            StudentStatusChoices.TRANSFERRED,
            StudentStatusChoices.GRADUATED,
            StudentStatusChoices.EXPELLED,
            StudentStatusChoices.WITHDRAWN,
        }

        if new_status in terminal_statuses and not data.get("exit_date"):
            raise serializers.ValidationError(
                {"exit_date": f"Exit date is required for status {new_status}"}
            )

        if new_status == student.student_status:
            raise serializers.ValidationError("Status is already set to this value")

        return data


#  PARENT GUARDIAN SERIALIZERS 
class ParentGuardianSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = ParentGuardian
        fields = [
            # "id",
            "user",
            "full_name",
            "phone",
            "email",
            "relationship",
            "is_primary",
            "can_pickup",
            "can_consent",
            "alternate_phone",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "full_name", "phone", "email", "created_at", "updated_at"]


class ParentGuardianCreateSerializer(serializers.ModelSerializer):
    """Create Parent + User + link to student(s)"""

    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    phone = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"}, required=False)

    class Meta:
        model = ParentGuardian
        fields = [
            "students",
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
        request = self.context["request"]
        creator = request.user
        students = data.get("students", [])

        if students:
            for student in students:
                if student.school != creator.school and not creator.is_superuser:
                    raise serializers.ValidationError(
                        {"students": "Cannot add parent to student from another school"}
                    )
        return data
    

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        creator = request.user
        school = getattr(request, "school", None) or creator.school

        students = validated_data.pop("students", [])
        password = validated_data.pop("password", None)

        user_data = {
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "email": validated_data.pop("email", None) or None,
            "phone": validated_data.pop("phone"),
        }
        user_data = {k: v for k, v in user_data.items() if v}

        user = UserCreationService.create_user(
            creator=creator,
            school=school,
            user_data=user_data,
            role_name="Parent",
            send_email=True,
        )

        if password:
            user.set_password(password)
            user.save(update_fields=["password"])

        parent = ParentGuardian.objects.create(user=user, **validated_data)

        if students:
            parent.students.set(students)

        return parent


#  MEDICAL HISTORY SERIALIZERS 
class StudentMedicalHistorySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    admission_number = serializers.CharField(source="student.admission_number", read_only=True)
    logged_by_name = serializers.CharField(source="logged_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = StudentMedicalHistory
        fields = [
            # "id",
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
        read_only_fields = ["student_name", "admission_number", "logged_by_name", "created_at"]


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


#  SEARCH SERIALIZER 
class StudentSearchSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True)
    school = serializers.UUIDField(required=False)
    current_class = serializers.UUIDField(required=False)
    student_status = serializers.ChoiceField(
        choices=StudentStatusChoices.choices, required=False
    )
    student_category = serializers.ChoiceField(
        choices=StudentCategoryChoices.choices, required=False
    )
    gender = serializers.ChoiceField(
        choices=StudentGenderChoices.choices, required=False
    )

    def validate(self, data):
        if not any(data.values()):
            raise serializers.ValidationError("Provide at least one search parameter")
        return data


class AssignClassSerializer(serializers.Serializer):
    classroom_id = serializers.UUIDField()  # or IntegerField if PK is int


class LinkParentSerializer(serializers.Serializer):
    parent_id = serializers.IntegerField()  # ParentGuardian pk
    is_primary = serializers.BooleanField(default=False)