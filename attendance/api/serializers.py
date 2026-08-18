from django.db import transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from students.models import StudentProfile
from ..models import AttendancePattern, AttendanceRecord, AttendanceSession
from core.choices.attendance import (
    AttendanceDeviceChoices,
    AttendanceRecordStatusChoices,
    AttendanceRiskLevelChoices,
)


class AttendanceSessionListSerializer(serializers.ModelSerializer):
    session_type_display = serializers.CharField(source="get_session_type_display", read_only=True)
    status_display = serializers.CharField(source="get_attendance_session_status_display", read_only=True)
    conducted_by_name = serializers.CharField(source="conducted_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = AttendanceSession
        fields = [
            "id", "session_type", "session_type_display", "reference_id", "date",
            "start_time", "end_time", "expected_count", "actual_count",
            "attendance_session_status", "status_display", "conducted_by", "conducted_by_name",
            "venue_name", "is_automated", "created_at",
        ]


class AttendanceSessionDetailSerializer(serializers.ModelSerializer):
    session_type_display = serializers.CharField(source="get_session_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    conducted_by_name = serializers.CharField(source="conducted_by.get_full_name", read_only=True, allow_null=True)
    verified_by_name = serializers.CharField( source="verified_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = AttendanceSession
        fields = "__all__"
        read_only_fields = ["id", "actual_count", "created_at", "updated_at"]


class AttendanceSessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceSession
        fields = [
            "session_type", "reference_id", "date", "start_time", "end_time",
            "expected_count", "notes", "venue_name", "location", "is_automated", "device_id",
        ]

    def validate(self, data):
        if data.get("end_time") and data["end_time"] <= data["start_time"]:
            raise serializers.ValidationError({"end_time": "Must be after start_time"})
        return data

    def create(self, validated_data):
        request = self.context["request"]
        school = request.school

        validated_data.update({
            "school": school,
            "academic_year": school.current_academic_year,
            "term": school.current_term,
            "conducted_by": request.user,
        })
        return super().create(validated_data)


class AttendanceRecordListSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    admission_number = serializers.CharField(source="student.admission_number", read_only=True)
    status_display = serializers.CharField(source="get_attendance_record_status_display", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id", "student", "student_name", "admission_number",
            "attendance_record_status", "status_display",
            "check_in_time", "check_out_time", "reason", "device_used", "created_at",
        ]

class AttendanceRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = [
            "session", "student", "attendance_record_status",
            "check_in_time", "check_out_time", "reason", "doctor_note",
            "device_used", "location", "photo_evidence",
        ]

    def validate(self, data):
        if data["session"].school != data["student"].school:
            raise serializers.ValidationError("Student does not belong to this session's school")
        return data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        validated_data["verified_by"] = request.user

        if not validated_data.get("check_in_time") and validated_data.get(
            "attendance_record_status"
        ) in {
            AttendanceRecordStatusChoices.PRESENT,
            AttendanceRecordStatusChoices.LATE,
        }:
            validated_data["check_in_time"] = timezone.now()

        return super().create(validated_data)
class AttendancePatternSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    admission_number = serializers.CharField(source="student.admission_number", read_only=True)

    class Meta:
        model = AttendancePattern
        fields = "__all__"
        read_only_fields = ["id", "last_updated", "risk_level"]


class AttendanceRecordDetailSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    device_used_display = serializers.CharField( source="get_device_used_display", read_only=True)
    verified_by_name = serializers.CharField(source="verified_by.get_full_name", read_only=True, allow_null=True)
    session_info = AttendanceSessionListSerializer(source="session", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_at",
            "session_info",
            "student_name",
            "student_admission",
            "status_display",
            "device_used_display",
            "verified_by_name",
        ]


class AttendanceSessionCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceSession
        fields = [
                "session_type",
                "reference_id",
                "date",
                "start_time",
                "end_time",
                "expected_count",
                "notes",
                "venue_name",
                "location",
                "is_automated",
                "device_id",
            ]
        extra_kwargs = {
            "school": {"read_only": True},
            "academic_year": {"read_only": True},
            "term": {"read_only": True},
            "conducted_by": {"read_only": True},
            "verified_by": {"read_only": True},
            "actual_count": {"read_only": True},
            "attendance_session_status": {"read_only": True},
        }

    def validate(self, data):
        if (
            data.get("end_time")
            and data.get("start_time")
            and data["end_time"] <= data["start_time"]
        ):
            raise serializers.ValidationError(
                {"end_time": "End time must be after start time."}
            )
        return data

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        school = user.school

        validated_data.update(
            {
                "school": school,
                "conducted_by": user,
                "academic_year": school.current_academic_year,
                "term": school.current_term,
                # 'attendance_session_status': AttendanceSession.AttendanceStautsChoices.SCHEDULED,
            }
        )
        return super().create(validated_data)


class AttendanceRecordWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = [
            "session",
            "student",
            "attendance_record_status",
            "check_in_time",
            "check_out_time",
            "reason",
            "doctor_note",
            "device_used",
            "location",
        ]
        extra_kwargs = {
            "verified_by": {"read_only": True},
        }

    def validate(self, data):
        session = data["session"]
        student = data["student"]
        if session.school_id != student.school_id:
            raise serializers.ValidationError(
                "Student does not belong to this session's school."
            )
        return data

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["verified_by"] = request.user
        if not validated_data.get("check_in_time") and validated_data[
            "attendance_record_status"
        ] in ["present", "late"]:
            validated_data["check_in_time"] = timezone.now()
        return super().create(validated_data)


#  Bulk Operations
class BulkAttendanceItemSerializer(serializers.Serializer):
    student = serializers.UUIDField()
    attendance_record_status = serializers.ChoiceField(choices=AttendanceRecordStatusChoices.choices)
    check_in_time = serializers.DateTimeField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True)

class BulkAttendanceCreateSerializer(serializers.Serializer):
    session = serializers.UUIDField()
    records = BulkAttendanceItemSerializer(many=True)

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        school = request.school
        session_id = validated_data["session"]

        session = AttendanceSession.objects.select_for_update().filter(
            id=session_id, school=school
        ).first()
        if not session:
            raise serializers.ValidationError("Session not found or access denied.")

        created = []
        errors = []

        for item in validated_data["records"]:
            try:
                student = StudentProfile.objects.get(id=item["student"], school=school)

                record, _ = AttendanceRecord.objects.update_or_create(
                    session=session,
                    student=student,
                    defaults={
                        "attendance_record_status": item["attendance_record_status"],
                        "check_in_time": item.get("check_in_time"),
                        "reason": item.get("reason", ""),
                        "device_used": AttendanceDeviceChoices.MANUAL,
                        "verified_by": request.user,
                    },
                )
                created.append({
                    "record_id": str(record.id),
                    "student_id": str(student.id),
                    "status": record.attendance_record_status,
                })
            except StudentProfile.DoesNotExist:
                errors.append({"student": item["student"], "error": "Student not found"})
            except Exception as e:
                errors.append({"student": item["student"], "error": str(e)})

        return {"session": str(session.id), "created": created, "errors": errors}


#  SELF CHECK-IN / CHECK-OUT
class StudentCheckInSerializer(serializers.Serializer):
    session = serializers.UUIDField()
    location = serializers.CharField(required=False, allow_blank=True)
    device_used = serializers.ChoiceField(choices=AttendanceDeviceChoices.choices,default=AttendanceDeviceChoices.MOBILE_APP)

    def validate(self, data):
        request = self.context["request"]
        school = getattr(request.user, 'school', None)

        if not AttendanceSession.objects.filter(
            id=data["session"], school=school
        ).exists():
            raise serializers.ValidationError("Invalid or inaccessible session.")
        return data

    def create(self, validated_data):
        request = self.context["request"]
        student = getattr(request.user, "student_profile", None)
        if not student:
            raise serializers.ValidationError("No student profile associated with this user.")

        record, created = AttendanceRecord.objects.get_or_create(
            session_id=validated_data["session"],
            student=student,
            defaults={
                "attendance_record_status": AttendanceRecordStatusChoices.PRESENT,
                "device_used": validated_data.get("device_used", AttendanceDeviceChoices.MOBILE_APP),
                "check_in_time": timezone.now(),
                "location": validated_data.get("location"),
                "verified_by": request.user,
            },
        )

        if not created and not record.check_in_time:
            record.check_in_time = timezone.now()
            record.device_used = validated_data.get("device_used", record.device_used)
            record.location = validated_data.get("location", record.location)
            record.save()

        return record


class StudentCheckOutSerializer(serializers.Serializer):
    session = serializers.UUIDField()

    def validate(self, data):
        request = self.context["request"]
        school = getattr(request.user, 'school', None)

        if not AttendanceSession.objects.filter(
            id=data["session"], school=school
        ).exists():
            raise serializers.ValidationError("Invalid session.")
        return data

    def create(self, validated_data):
        student = getattr(self.context["request"].user, "student_profile", None)
        if not student:
            raise serializers.ValidationError("No student profile.")

        try:
            record = AttendanceRecord.objects.get(
                session_id=validated_data["session"],
                student=student,
            )
            if record.check_out_time:
                raise serializers.ValidationError("Already checked out.")
            record.check_out_time = timezone.now()
            record.save()
            return record
        except AttendanceRecord.DoesNotExist:
            raise serializers.ValidationError("No check-in record found for this session.")


#  REPORT & DASHBOARD SERIALIZERS
class DailyAttendanceStatsSerializer(serializers.Serializer):
    date = serializers.DateField(read_only=True)
    total_sessions = serializers.IntegerField(read_only=True)
    total_records = serializers.IntegerField(read_only=True)
    present = serializers.IntegerField(read_only=True)
    late = serializers.IntegerField(read_only=True)
    absent = serializers.IntegerField(read_only=True)
    excused = serializers.IntegerField(read_only=True)
    attendance_rate = serializers.FloatField(read_only=True)


class StudentDateRangeSummarySerializer(serializers.Serializer):
    student = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, data):
        if data["start_date"] > data["end_date"]:
            raise serializers.ValidationError("start_date cannot be after end_date")
        if (data["end_date"] - data["start_date"]).days > 366:
            raise serializers.ValidationError("Date range cannot exceed 1 year")
        return data


class TodaySchoolAttendanceSerializer(serializers.Serializer):
    date = serializers.DateField(read_only=True)
    total_expected_students = serializers.IntegerField(read_only=True)
    total_checked_in = serializers.IntegerField(read_only=True)
    present = serializers.IntegerField(read_only=True)
    late = serializers.IntegerField(read_only=True)
    absent = serializers.IntegerField(read_only=True)
    excused_or_sick = serializers.IntegerField(read_only=True)
    attendance_percentage = serializers.FloatField(read_only=True)
    most_common_session_type = serializers.CharField(read_only=True, allow_null=True)
    sessions_completed = serializers.IntegerField(read_only=True)
    sessions_ongoing = serializers.IntegerField(read_only=True)


class WeeklyAttendanceTrendSerializer(serializers.Serializer):
    week_start = serializers.DateField(read_only=True)
    week_end = serializers.DateField(read_only=True)
    daily_stats = serializers.ListField(child=serializers.DictField(), read_only=True)
    average_attendance = serializers.FloatField(read_only=True)
    trend_direction = serializers.ChoiceField(choices=[("up", "Improving"), ("down", "Declining"), ("stable", "Stable")], read_only=True,)
    lowest_day = serializers.DictField(read_only=True, allow_null=True)
    highest_day = serializers.DictField(read_only=True, allow_null=True)


class AtRiskStudentsAlertSerializer(serializers.Serializer):
    student_id = serializers.UUIDField(source="student_id", read_only=True)
    admission_number = serializers.CharField(source="student.admission_number", read_only=True)
    full_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    current_term_attendance_rate = serializers.FloatField(source="attendance_rate", read_only=True)
    consecutive_absent_days = serializers.IntegerField(read_only=True)
    total_absent_this_term = serializers.IntegerField(source="absent_count", read_only=True)
    risk_level = serializers.ChoiceField(choices=AttendanceRiskLevelChoices.choices, read_only=True)
    last_absent_date = serializers.SerializerMethodField()
    recommended_action = serializers.SerializerMethodField()
    def get_last_absent_date(self, obj):
        # optional: query last absent record; or return None for now
        return None

    def get_recommended_action(self, obj):
        if obj.risk_level == AttendanceRiskLevelChoices.CRITICAL:
            return "Immediate parent meeting and guidance referral"
        if obj.risk_level == AttendanceRiskLevelChoices.HIGH:
            return "Contact parent and monitor for 1 week"
        return "Monitor attendance"


class ClassDailyAttendanceSummarySerializer(serializers.Serializer):
    date = serializers.DateField(read_only=True)
    class_name = serializers.CharField(read_only=True)
    class_id = serializers.UUIDField(read_only=True)
    total_students = serializers.IntegerField(read_only=True)
    present = serializers.IntegerField(read_only=True)
    late = serializers.IntegerField(read_only=True)
    absent = serializers.IntegerField(read_only=True)
    excused = serializers.IntegerField(read_only=True)
    attendance_rate = serializers.FloatField(read_only=True)
    late_students = serializers.ListField(child=serializers.DictField(), read_only=True, allow_empty=True)
    absent_students = serializers.ListField(child=serializers.DictField(), read_only=True, allow_empty=True)


class MonthlyAttendanceCalendarSerializer(serializers.Serializer):
    year = serializers.IntegerField(read_only=True)
    month = serializers.IntegerField(read_only=True)
    month_name = serializers.CharField(read_only=True)
    total_school_days = serializers.IntegerField(read_only=True)
    days_attended = serializers.IntegerField(read_only=True)
    monthly_rate = serializers.FloatField(read_only=True)
    daily_summary = serializers.ListField(read_only=True)


class AttendanceExportFlatSerializer(serializers.Serializer):
    date = serializers.DateField()
    session_type = serializers.CharField()
    session_start_time = serializers.TimeField()
    student_admission_number = serializers.CharField()
    student_full_name = serializers.CharField()
    class_name = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    status_display = serializers.CharField()
    check_in_time = serializers.DateTimeField(allow_null=True)
    reason = serializers.CharField(allow_blank=True)
    recorded_by = serializers.CharField(allow_null=True)
    verified_by = serializers.CharField(allow_null=True)


class AttendanceReportRequestSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(
        choices=[
            ("daily", "Daily School Summary"),
            ("class_daily", "Class Daily Register"),
            ("student_term", "Student Term Report"),
            ("monthly_calendar", "Monthly Calendar View"),
            ("at_risk_list", "At-Risk Students List"),
            ("export_flat", "Export All Records (CSV/Excel)"),
        ]
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False)
    class_id = serializers.UUIDField(required=False, allow_null=True)
    student_id = serializers.UUIDField(required=False, allow_null=True)
    include_details = serializers.BooleanField(default=False)

    def validate(self, data):
        if data["start_date"] > (data.get("end_date") or timezone.now().date()):
            raise serializers.ValidationError("Start date cannot be after end date.")
        return data