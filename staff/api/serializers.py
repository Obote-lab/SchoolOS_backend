from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from accounts.services.user_creation_services import UserCreationService
from ..models import StaffProfile, StaffAttendance



#   List / Simple Serializers
class StaffProfileListSerializer(serializers.ModelSerializer):
    """Minimal serializer for staff lists (dashboard, search, etc.)"""
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta:
        model = StaffProfile
        fields = [
            "id",
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
        ]
        read_only_fields = fields


class StaffAttendanceListSerializer(serializers.ModelSerializer):
    """Minimal serializer for attendance history lists"""
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


#   Detail Serializers
class StaffProfileDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer for individual staff profile"""
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model = StaffProfile
        fields = [
            "id",
            "staff_id",
            "full_name",
            "email",
            "phone",
            "staff_type",
            "employment_type",
            "tsc_number",
            "id_number",
            "date_employed",
            "job_title",
            "department",
            # "date_of_birth",
            "age",
            "profile_pic",
            "subjects_taught",
            "classes_assigned",
            "is_active",
            "exit_date",
            "exit_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "full_name",
            "email",
            "phone",
            "age",
            "created_at",
            "updated_at",
        ]



#   Create / Update Serializers
class StaffProfileCreateSerializer(serializers.ModelSerializer):
    """Create new staff member + linked user account"""
    email = serializers.EmailField(write_only=True, required=True)
    first_name = serializers.CharField(write_only=True, required=True)
    last_name = serializers.CharField(write_only=True, required=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = StaffProfile
        fields = [
            "staff_id",
            "staff_type",
            "employment_type",
            "tsc_number",
            "id_number",
            "date_employed",
            "job_title",
            "department",
            # "date_of_birth",
            "email",
            "first_name",
            "last_name",
            "phone",
        ]

    def validate_staff_id(self, value):
        school = self.context["request"].user.school
        if StaffProfile.objects.filter(school=school, staff_id=value).exists():
            raise serializers.ValidationError("Staff ID already exists in this school")
        return value.strip().upper()

    def validate_date_of_birth(self, value):
        if value and value > timezone.now().date():
            raise serializers.ValidationError("Date of birth cannot be in the future")
        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        creator = request.user
        school = creator.school

        # Extract user creation data
        user_data = {
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "email": validated_data.pop("email"),
            "phone": validated_data.pop("phone", None),
        }

        # Create user via service (generates login_id, etc.)
        result = UserCreationService.create_user(
            creator=creator,
            school=school,
            user_type=validated_data["staff_type"],  
            user_data=user_data
        )
        user = result["user"]

        # Create staff profile
        staff = StaffProfile.objects.create(
            user=user,
            school=school,
            **validated_data
        )

        return staff


class StaffProfileUpdateSerializer(serializers.ModelSerializer):
    """Update existing staff profile (limited fields)"""

    class Meta:
        model = StaffProfile
        fields = [
            "staff_type",
            "employment_type",
            "tsc_number",
            "id_number",
            "job_title",
            "department",
            # "date_of_birth",
            "profile_pic",
            "subjects_taught",
            "classes_assigned",
            "is_active",
            "exit_date",
            "exit_reason",
        ]

    def validate_exit_date(self, value):
        if value and value > timezone.now().date():
            raise serializers.ValidationError("Exit date cannot be in the future")
        return value


#   Attendance Action Serializers
class ClockInSerializer(serializers.Serializer):
    """Simple serializer for clock-in action"""
    staff_id = serializers.CharField(required=True, help_text="Staff ID")

    def validate_staff_id(self, value):
        request = self.context["request"]
        try:
            staff = StaffProfile.objects.get(
                school=request.user.school,
                staff_id=value.strip().upper(),
                is_active=True
            )
            return staff
        except StaffProfile.DoesNotExist:
            raise serializers.ValidationError("Staff not found or inactive")

    def create(self, validated_data):
        staff = validated_data["staff_id"] 
        today = timezone.now().date()

        attendance, created = StaffAttendance.objects.get_or_create(
            staff=staff,
            date=today,
            defaults={
                "status": StaffAttendance.StatusChoices.PRESENT,
                "recorded_by": self.context["request"].user,
            }
        )

        if not created and attendance.status != StaffAttendance.StatusChoices.PRESENT:
            attendance.status = StaffAttendance.StatusChoices.PRESENT
            attendance.recorded_by = self.context["request"].user
            attendance.save()

        return attendance


class ClockOutSerializer(serializers.Serializer):
    """Simple serializer for clock-out action"""
    staff_id = serializers.CharField(required=True, help_text="Staff ID")

    def validate_staff_id(self, value):
        request = self.context["request"]
        try:
            staff = StaffProfile.objects.get(
                school=request.user.school,
                staff_id=value.strip().upper(),
                is_active=True
            )
            return staff
        except StaffProfile.DoesNotExist:
            raise serializers.ValidationError("Staff not found or inactive")

    def create(self, validated_data):
        staff = validated_data["staff_id"]
        today = timezone.now().date()

        try:
            attendance = StaffAttendance.objects.get(staff=staff, date=today)
            if attendance.status not in [StaffAttendance.StatusChoices.PRESENT, StaffAttendance.StatusChoices.LATE]:
                raise serializers.ValidationError("Cannot clock out — no active attendance today")
            attendance.status = StaffAttendance.StatusChoices.PRESENT 
            attendance.recorded_by = self.context["request"].user
            attendance.save()
            return attendance
        except StaffAttendance.DoesNotExist:
            raise serializers.ValidationError("No attendance record found for today")
        



class StaffAttendanceCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new staff attendance record.
    
    - Admins/staff can create records for any staff (with school context check)
    - Automatically sets 'recorded_by' to the current user
    - Prevents duplicate records for the same staff on the same date
    """
    class Meta:
        model = StaffAttendance
        fields = [
            "staff",           
            "date",            
            "status",         
            "notes",           
        ]
        read_only_fields = ["recorded_by"]  

    def validate_staff(self, value):
        """
        Ensure the selected staff belongs to the same school as the requesting user
        (unless superuser/system admin).
        """
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError("Request context missing")

        user = request.user
        if user.is_superuser:
            return value 

        if not hasattr(user, "school") or not user.school:
            raise serializers.ValidationError("User is not associated with any school")

        if value.school != user.school:
            raise serializers.ValidationError(
                "Cannot create attendance record for staff from another school"
            )

        if not value.is_active:
            raise serializers.ValidationError("Cannot record attendance for inactive staff")

        return value

    def validate_date(self, value):
        """Prevent future dates and very old dates (e.g. > 2 years ago)"""
        today = timezone.now().date()
        if value > today:
            raise serializers.ValidationError("Attendance date cannot be in the future")

        two_years_ago = today - timezone.timedelta(days=730)
        if value < two_years_ago:
            raise serializers.ValidationError("Attendance date cannot be more than 2 years in the past")

        return value

    def validate(self, data):
        """
        Prevent duplicate attendance record for the same staff on the same date.
        """
        staff = data.get("staff")
        date = data.get("date") or timezone.now().date()

        if StaffAttendance.objects.filter(staff=staff, date=date).exists():
            raise serializers.ValidationError(
                {"date": f"Attendance record already exists for {staff} on {date}"}
            )

        return data

    @transaction.atomic
    def create(self, validated_data):
        """
        Create the attendance record and auto-set recorded_by.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required to create record")

        validated_data["recorded_by"] = request.user

        # Default to today if date not provided
        if "date" not in validated_data:
            validated_data["date"] = timezone.now().date()

        # Default status to PRESENT if not specified
        if "status" not in validated_data:
            validated_data["status"] = StaffAttendance.StatusChoices.PRESENT

        return super().create(validated_data)