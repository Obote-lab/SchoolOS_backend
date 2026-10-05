from django.db import models
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from ..models import CounselingSession, DisciplineIncident, SickBayRecord, WellnessCheck
from core.choices.welfare import  DisciplineStatusChoices
from core.choices.welfare import CounselingSessionStatusChoices


#  LIST SERIALIZERS
class DisciplineIncidentListSerializer(serializers.ModelSerializer):
    """Simple incident list"""

    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    category_display = serializers.CharField(source="get_discipline_category_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField( source="get_discipline_status_display", read_only=True)

    class Meta:
        model = DisciplineIncident
        fields = [
            "id",
            "incident_code",
            "student",
            "student_name",
            "student_admission",
            "discipline_category",
            "category_display",
            "severity",
            "severity_display",
            "date_occurred",
            "discipline_status",
            "status_display",
        ]


class SickBayRecordListSerializer(serializers.ModelSerializer):
    """Simple sick bay record list"""

    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    attended_by_name = serializers.CharField(source="attended_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = SickBayRecord
        fields = [
            "id",
            "student",
            "student_name",
            "student_admission",
            "complaint",
            "date",
            "attended_by",
            "attended_by_name",
            "is_contagious",
            "class_excused",
        ]


#  DETAIL SERIALIZERS
class DisciplineIncidentDetailSerializer(serializers.ModelSerializer):
    """Full incident details"""

    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    category_display = serializers.CharField(source="get_discipline_category_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_discipline_status_display", read_only=True)
    reported_by_name = serializers.CharField(source="reported_by.get_full_name", read_only=True, allow_null=True)
    action_by_name = serializers.CharField(source="action_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = DisciplineIncident
        fields = "__all__"
        read_only_fields = ["id", "incident_code", "created_at", "updated_at"]

    def validate_date_occurred(self, value):
        if value > timezone.now():
            raise serializers.ValidationError("Incident date cannot be in the future")
        return value


class SickBayRecordDetailSerializer(serializers.ModelSerializer):
    """Full sick bay record details"""

    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    attended_by_name = serializers.CharField(source="attended_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = SickBayRecord
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_date(self, value):
        if value > timezone.now():
            raise serializers.ValidationError("Record date cannot be in the future")
        return value


class CounselingSessionDetailSerializer(serializers.ModelSerializer):
    """Full counseling session details"""

    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    counselor_name = serializers.CharField(source="counselor.get_full_name", read_only=True)
    # session_type_display = serializers.CharField(source="get_counseling_session_type_display", read_only=True)
    session_type_display = serializers.CharField(source="get_session_type_display", read_only=True)
    status_display = serializers.CharField(source="get_counseling_status_display", read_only=True)

    class Meta:
        model = CounselingSession
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_date(self, value):
        if self.instance is None and value < timezone.now():
            raise serializers.ValidationError("Session date cannot be in the past")
        return value


class WellnessCheckDetailSerializer(serializers.ModelSerializer):
    """Full wellness check details"""

    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    student_admission = serializers.CharField(source="student.admission_number", read_only=True)
    checked_by_name = serializers.CharField(source="checked_by.get_full_name", read_only=True, allow_null=True)
    academic_stress_level_display = serializers.CharField(source="get_academic_stress_level_display", read_only=True, allow_null=True)
    nutrition_quality_display = serializers.CharField(source="get_nutrition_quality_display", read_only=True, allow_null=True)
    exercise_frequency_display = serializers.CharField(source="get_exercise_frequency_display", read_only=True, allow_null=True)
    overall_wellness = serializers.SerializerMethodField()

    class Meta:
        model = WellnessCheck
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "overall_wellness"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_overall_wellness(self, obj) -> str:
        return obj.overall_wellness or "N/A"

#  CREATE/UPDATE SERIALIZERS
class DisciplineIncidentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisciplineIncident
        fields = [
            "student",
            "discipline_category",
            "severity",
            "description",
            "location",
            "witnesses",
            "evidence",
            "date_occurred",
            "action_taken",
        ]

    def create(self, validated_data):
        request = self.context["request"]
        student = validated_data["student"]
        school = getattr(request, "school", None) or student.school
        if student.school_id != school.id:
            raise serializers.ValidationError(
                {"student": "Student does not belong to this school."}
            )
        validated_data["school"] = school
        return super().create(validated_data)

class SickBayRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SickBayRecord
        fields = [
            "student",
            "complaint",
            "diagnosis",
            "treatment",
            "medication_given",
            "vital_signs",
            "referred_to_hospital",
            "hospital_name",
            "doctor_seen",
            "doctor_name",
            "duration_minutes",
            "is_contagious",
            "isolation_required",
            "class_excused",
            "class_excuse_days",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        student = validated_data["student"]
        if request and request.user.is_authenticated:
            validated_data["attended_by"] = request.user
        validated_data["school"] = (
            getattr(request, "school", None) or student.school
        )
        return super().create(validated_data)

class CounselingSessionCreateSerializer(serializers.ModelSerializer):
    """Create counseling session"""

    class Meta:
        model = CounselingSession
        fields = [
            "student",
            # "counseling_session_type",
            # "get_counseling_session_type_display",
            "session_type",
            "date",
            "duration_minutes",
            "location",
            "reason",
            "follow_up_required",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        student = validated_data["student"]
        if request and request.user.is_authenticated:
            validated_data["counselor"] = request.user
        validated_data["school"] = (
            getattr(request, "school", None) or student.school
        )
        return super().create(validated_data)


#  ACTION SERIALIZERS
class ResolveIncidentSerializer(serializers.Serializer):
    action_taken = serializers.CharField(required=True)
    resolution_date = serializers.DateField(required=False)
    parent_notified = serializers.BooleanField(default=False)
    parent_response = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        instance.discipline_status = DisciplineStatusChoices.RESOLVED
        instance.action_taken = validated_data["action_taken"]
        instance.resolution_date = validated_data.get("resolution_date", timezone.now().date())
        instance.parent_notified = validated_data["parent_notified"]
        instance.parent_response = validated_data.get("parent_response", "")
        instance.action_by = self.context["request"].user
        instance.save()
        return instance


class ScheduleFollowUpSerializer(serializers.Serializer):
    """Schedule follow-up for incident"""

    follow_up_date = serializers.DateField(required=True)
    follow_up_notes = serializers.CharField(required=False, allow_blank=True)
    counseling_recommended = serializers.BooleanField(default=False)
    counseling_scheduled = serializers.DateField(required=False, allow_null=True)

    def update(self, instance, validated_data):
        instance.follow_up_required = True
        instance.follow_up_date = validated_data["follow_up_date"]
        instance.follow_up_notes = validated_data.get("follow_up_notes", "")
        instance.counseling_recommended = validated_data["counseling_recommended"]
        instance.counseling_scheduled = validated_data.get("counseling_scheduled")
        instance.save()
        return instance


class CompleteSessionSerializer(serializers.Serializer):
    """Complete a counseling session"""

    notes = serializers.CharField(required=False, allow_blank=True)
    recommendations = serializers.CharField(required=False, allow_blank=True)
    parent_involved = serializers.BooleanField(default=False)
    parent_feedback = serializers.CharField(required=False, allow_blank=True)
    referral_made = serializers.BooleanField(default=False)
    referral_to = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        instance.counseling_status = CounselingSessionStatusChoices.COMPLETED
        instance.notes = validated_data.get("notes", "")
        instance.recommendations = validated_data.get("recommendations", "")
        instance.parent_involved = validated_data["parent_involved"]
        instance.parent_feedback = validated_data.get("parent_feedback", "")
        instance.referral_made = validated_data["referral_made"]
        instance.referral_to = validated_data.get("referral_to", "")
        instance.save()
        return instance


#  STATISTICS SERIALIZERS
class WelfareStatisticsSerializer(serializers.Serializer):
    """Welfare statistics"""

    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)

    def validate(self, data):
        if data["start_date"] > data["end_date"]:
            raise serializers.ValidationError("Start date cannot be after end date")
        return data

    def get_statistics(self):
        start_date = self.validated_data["start_date"]
        end_date = self.validated_data["end_date"]
        incidents = DisciplineIncident.objects.filter(date_occurred__date__range=[start_date, end_date])
        sick_records = SickBayRecord.objects.filter(date__date__range=[start_date, end_date])
        sessions = CounselingSession.objects.filter(date__date__range=[start_date, end_date])
        wellness_checks = WellnessCheck.objects.filter(check_date__range=[start_date, end_date])

        stats = {
            "period": f"{start_date} to {end_date}",
            "total_incidents": incidents.count(),
            "incidents_by_category": incidents.values("discipline_category").annotate(count=models.Count("id")),
            "incidents_by_severity": incidents.values("severity").annotate(count=models.Count("id")),
            "total_sick_visits": sick_records.count(),
            "contagious_cases": sick_records.filter(is_contagious=True).count(),
            "hospital_referrals": sick_records.filter(referred_to_hospital=True).count(),
            "total_counseling_sessions": sessions.count(),
            "sessions_by_type": sessions.values("session_type").annotate(count=models.Count("id")),
            "total_wellness_checks": wellness_checks.count(),
            "average_wellness_score": wellness_checks.aggregate(
                avg=models.Avg(
                    (
                        models.F("mental_wellbeing_score")
                        + models.F("physical_wellbeing_score")
                        + models.F("social_wellbeing_score")
                    )
                    / 3
                )
            )["avg"]
            or 0,
        }

        return stats


class StudentWelfareSummarySerializer(serializers.Serializer):
    student_id = serializers.UUIDField(required=True)

    def get_summary(self, student_id):
        from students.models import StudentProfile

        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            raise serializers.ValidationError("Student not found")

        incidents = DisciplineIncident.objects.filter(student=student).order_by("-date_occurred")
        sick_records = SickBayRecord.objects.filter(student=student).order_by("-date")
        sessions = CounselingSession.objects.filter(student=student).order_by("-date")
        wellness_checks = WellnessCheck.objects.filter(student=student).order_by("-check_date")

        summary = {
            "student": {
                "name": student.user.get_full_name(),
                "admission_number": student.admission_number,
                "class": (
                    student.current_class.classroom_name
                    if student.current_class
                    else "N/A"
                ),
            },
            "recent_incidents": DisciplineIncidentListSerializer(incidents[:5], many=True).data,
            "total_incidents": incidents.count(),
            "open_incidents": incidents.filter(
                discipline_status__in=[DisciplineStatusChoices.REPORTED, DisciplineStatusChoices.INVESTIGATING]
            ).count(),
            "recent_sick_visits": SickBayRecordListSerializer(sick_records[:5], many=True).data,
            "total_sick_visits": sick_records.count(),
            "recent_counseling": CounselingSessionDetailSerializer(sessions[:5], many=True).data,
            "total_counseling_sessions": sessions.count(),
            "wellness_history": WellnessCheckDetailSerializer(wellness_checks[:5], many=True).data,
            "average_wellness_score": self.calculate_average_wellness(wellness_checks),
        }

        return summary

    def calculate_average_wellness(self, wellness_checks):
        if not wellness_checks.exists():
            return None

        total = 0
        count = 0
        for check in wellness_checks:
            score = check.calculate_overall_score()
            if score is not None:
                total += score
                count += 1

        return round(total / count, 1) if count > 0 else None

#  DASHBOARD SERIALIZER
class TodayStatsSerializer(serializers.Serializer):
    """Serializer for today's statistics"""

    date = serializers.DateField()
    incidents_today = serializers.IntegerField()
    open_incidents = serializers.IntegerField()
    sick_visits = serializers.IntegerField()
    contagious_cases = serializers.IntegerField()
    counseling_sessions = serializers.IntegerField()


class WelfareDashboardSerializer(serializers.Serializer):
    """Serializer for welfare dashboard"""

    today_stats = TodayStatsSerializer()
    recent_incidents = serializers.ListField(child=serializers.DictField())
    today_sick_visits = serializers.ListField(child=serializers.DictField())
    upcoming_sessions = serializers.ListField(child=serializers.DictField())
    critical_wellness = serializers.ListField(child=serializers.DictField())


#  REPORT SERIALIZER
class WelfareReportSerializer(serializers.Serializer):
    """Serializer for welfare report request"""

    type = serializers.ChoiceField(
        choices=[
            ("incidents", "Incidents Report"),
            ("health", "Health Report"),
            ("counseling", "Counseling Report"),
            ("wellness", "Wellness Report"),
        ]
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    student = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, data):
        if data["start_date"] > data["end_date"]:
            raise serializers.ValidationError("Start date cannot be after end date")
        return data


#  ALERT SERIALIZER
class WelfareAlertSerializer(serializers.Serializer):
    """Serializer for a single alert"""
    type = serializers.CharField()
    message = serializers.CharField()
    priority = serializers.CharField()

class WelfareAlertsSerializer(serializers.Serializer):
    """Serializer for list of alerts"""
    alerts = serializers.ListField(child=WelfareAlertSerializer())