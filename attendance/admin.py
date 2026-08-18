from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import AttendancePattern, AttendanceRecord, AttendanceSession


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = (
        "session_type_display",
        "date",
        "start_time",
        "expected_count",
        "actual_count",
        "attendance_session_status",
        "conducted_by",
        "school",
    )
    list_filter = (
        "session_type",
        "attendance_session_status",
        "date",
        "school",
        "is_automated",
    )
    search_fields = ("notes", "venue_name", "school__school_name")
    readonly_fields = ("id", "actual_count", "created_at", "updated_at")
    raw_id_fields = (
        "school",
        "academic_year",
        "term",
        "conducted_by",
        "verified_by",
    )
    date_hierarchy = "date"
    ordering = ("-date", "-start_time")

    def session_type_display(self, obj):
        return obj.get_session_type_display()

    session_type_display.short_description = _("Session Type")
    session_type_display.admin_order_field = "session_type"

    fieldsets = (
        (_("Session Info"), {
            "fields": (
                "school",
                "session_type",
                "reference_id",
                "date",
                "start_time",
                "end_time",
                "venue_name",
            )
        }),
        (_("Participants"), {
            "fields": (
                "expected_count",
                "actual_count",
                "conducted_by",
                "verified_by",
            )
        }),
        (_("Status & Details"), {
            "fields": (
                "attendance_session_status",
                "notes",
                "is_automated",
                "device_id",
                "location",
            )
        }),
        (_("Academic Context"), {
            "fields": ("academic_year", "term"),
            "classes": ("collapse",),
        }),
    )


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "student_admission",
        "session",
        "attendance_record_status",
        "check_in_time",
        "check_out_time",
        "device_used",
        "verified_by",
    )
    list_filter = (
        "attendance_record_status",
        "device_used",
        "session__school",
        "session__date",
    )
    search_fields = (
        "student__admission_number",
        "student__user__first_name",
        "student__user__last_name",
        "reason",
    )
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("session", "student", "verified_by")
    ordering = ("-created_at",)

    def student_admission(self, obj):
        return obj.student.admission_number

    student_admission.short_description = _("Student")
    student_admission.admin_order_field = "student__admission_number"

    fieldsets = (
        (_("Record"), {
            "fields": (
                "session",
                "student",
                "attendance_record_status",
                "check_in_time",
                "check_out_time",
            )
        }),
        (_("Details"), {
            "fields": (
                "reason",
                "doctor_note",
                "parent_notified",
                "follow_up_required",
                "follow_up_notes",
            )
        }),
        (_("Device & Verification"), {
            "fields": ("device_used", "location", "photo_evidence", "verified_by"),
        }),
    )


@admin.register(AttendancePattern)
class AttendancePatternAdmin(admin.ModelAdmin):
    list_display = (
        "student_admission",
        "academic_year",
        "term",
        "attendance_rate",
        "consecutive_absent_days",
        "risk_level",
        "last_updated",
    )
    list_filter = ("risk_level", "academic_year", "term", "student__school")
    search_fields = (
        "student__admission_number",
        "student__user__first_name",
        "student__user__last_name",
    )
    readonly_fields = ("id", "last_updated")
    raw_id_fields = ("student", "academic_year", "term")
    ordering = ("-attendance_rate",)

    def student_admission(self, obj):
        return obj.student.admission_number

    student_admission.short_description = _("Student")
    student_admission.admin_order_field = "student__admission_number"

    fieldsets = (
        (_("Pattern"), {
            "fields": (
                "student",
                "academic_year",
                "term",
                "attendance_rate",
                "risk_level",
            )
        }),
        (_("Counts"), {
            "fields": (
                "total_sessions",
                "present_count",
                "late_count",
                "absent_count",
                "excused_count",
            ),
            "classes": ("collapse",),
        }),
        (_("Details"), {
            "fields": (
                "tardiness_rate",
                "consecutive_absent_days",
                "absent_pattern",
            ),
            "classes": ("collapse",),
        }),
    )