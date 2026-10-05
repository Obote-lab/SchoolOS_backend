from django.contrib import admin
from django.utils.html import format_html
from .models import CounselingSession, DisciplineIncident, SickBayRecord, WellnessCheck


@admin.register(DisciplineIncident)
class DisciplineIncidentAdmin(admin.ModelAdmin):
    list_display = (
        "incident_code",
        "student",
        "discipline_category",
        "severity",
        "discipline_status",
        "date_occurred",
        "reported_by",
    )
    list_filter = (
        "discipline_category",
        "severity",
        "discipline_status",
        "school",
        "recurring_pattern",
    )
    search_fields = (
        "incident_code",
        "description",
        "student__admission_number",
        "location",
    )
    readonly_fields = ("created_at", "updated_at", "incident_code")

    fieldsets = (
        (
            "Incident Details",
            {
                "fields": (
                    "incident_code",
                    "student",
                    "school",
                    "discipline_category",
                    "severity",
                    "description",
                    "location",
                    "date_occurred",
                )
            },
        ),
        ("Evidence & Witnesses", {"fields": ("witnesses", "evidence")}),
        (
            "Resolution",
            {
                "fields": (
                    "discipline_status",
                    "action_taken",
                    "action_by",
                    "resolution_date",
                    "parent_notified",
                    "parent_response",
                )
            },
        ),
        (
            "Follow-up",
            {
                "fields": (
                    "follow_up_required",
                    "follow_up_date",
                    "follow_up_notes",
                    "counseling_recommended",
                    "counseling_scheduled",
                )
            },
        ),
    )

    def student(self, obj):
        return obj.student.admission_number

    student.admin_order_field = "student__admission_number"


@admin.register(SickBayRecord)
class SickBayRecordAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "date",
        "complaint",
        "is_contagious",
        "referred_to_hospital",
        "class_excused",
        "attended_by",
    )
    list_filter = (
        "is_contagious",
        "referred_to_hospital",
        "class_excused",
        "isolation_required",
        "school",
    )
    search_fields = (
        "student__admission_number",
        "complaint",
        "diagnosis",
        "hospital_name",
    )
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Visit Info",
            {
                "fields": (
                    "student",
                    "school",
                    "date",
                    "complaint",
                    "diagnosis",
                    "treatment",
                )
            },
        ),
        (
            "Medical Details",
            {
                "fields": (
                    "medication_given",
                    "vital_signs",
                    "is_contagious",
                    "isolation_required",
                    "isolation_end_date",
                )
            },
        ),
        (
            "Actions",
            {
                "fields": (
                    "referred_to_hospital",
                    "hospital_name",
                    "doctor_seen",
                    "doctor_name",
                    "class_excused",
                    "class_excuse_days",
                )
            },
        ),
        (
            "Follow-up",
            {
                "fields": (
                    "parent_notified",
                    "parent_response",
                    "follow_up_required",
                    "follow_up_date",
                )
            },
        ),
    )


@admin.register(CounselingSession)
class CounselingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        # "get_counseling_session_type_display",
        "session_type",
        "date",
        "duration_minutes",
        "counseling_status",
        "counselor",
    )
    list_filter = (
        # "get_counseling_session_type_display",
        "session_type",
        "counseling_status",
        "parent_involved",
        "referral_made",
        "school",
    )
    search_fields = ("student__admission_number", "reason", "notes", "recommendations")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Session Info",
            {
                "fields": (
                    "student",
                    "school",
                    "counselor",
                    # "get_counseling_session_type_display",
                    "session_type",
                    "date",
                    "duration_minutes",
                    "location",
                )
            },
        ),
        ("Content", {"fields": ("reason", "notes", "recommendations")}),
        (
            "Follow-up",
            {
                "fields": (
                    "follow_up_required",
                    "follow_up_date",
                    "parent_involved",
                    "parent_feedback",
                    "referral_made",
                    "referral_to",
                )
            },
        ),
    )


@admin.register(WellnessCheck)
class WellnessCheckAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "check_date",
        "academic_stress_level",
        "mental_wellbeing_score",
        "physical_wellbeing_score",
        "social_wellbeing_score",
        "checked_by",
    )
    list_filter = (
        "academic_stress_level",
        "nutrition_quality",
        "exercise_frequency",
        "follow_up_planned",
        "school",
    )
    search_fields = ("student__admission_number", "concerns_raised", "support_provided")
    readonly_fields = ("created_at", "updated_at", "overall_wellness")

    fieldsets = (
        ("Check Info", {"fields": ("student", "school", "checked_by", "check_date")}),
        (
            "Wellness Scores",
            {
                "fields": (
                    "mental_wellbeing_score",
                    "physical_wellbeing_score",
                    "social_wellbeing_score",
                )
            },
        ),
        (
            "Lifestyle",
            {
                "fields": (
                    "academic_stress_level",
                    "sleep_hours_nightly",
                    "nutrition_quality",
                    "exercise_frequency",
                )
            },
        ),
        (
            "Notes & Follow-up",
            {
                "fields": (
                    "concerns_raised",
                    "support_provided",
                    "follow_up_planned",
                    "next_check_date",
                )
            },
        ),
    )
