from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import StaffAttendance, StaffProfile


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = (
        "staff_id",
        "full_name",
        "staff_type",
        "employment_type",
        "department",
        "is_active",
        "date_employed",
        "performance_score_display",
    )
    list_filter = (
        "staff_type",
        "employment_type",
        "is_active",
        "department",
        "school",
    )
    search_fields = (
        "staff_id",
        "user__first_name",
        "user__last_name",
        "user__phone",
        "tsc_number",
        "national_id",
        "job_title",
    )
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("user", "school", "department")
    list_per_page = 25
    ordering = ("staff_id",)

    fieldsets = (
        (_("Personal Info"), {
            "fields": (
                "user",
                "staff_id",
                "staff_type",
                "employment_type",
                "date_employed",
                "job_title",
            )
        }),
        (_("School & Department"), {
            "fields": ("school", "department", "subjects_specialized", "teaching_experience"),
        }),
        (_("Identification"), {
            "fields": (
                "national_id",
                "tsc_number",
                "kra_pin",
                "nssf_number",
                "nhif_number",
            ),
            "classes": ("collapse",),
        }),
        (_("Financial"), {
            "fields": (
                "basic_salary",
                "net_salary",
                "allowances",
                "deductions",
                "bank_details",
            ),
            "classes": ("collapse",),
        }),
        (_("Status & Performance"), {
            "fields": (
                "is_active",
                "exit_date",
                "exit_reason",
                "performance_score",
                "attendance_rate",
            )
        }),
        (_("Emergency & Medical"), {
            "fields": (
                "emergency_contact_name",
                "emergency_contact_phone",
                "medical_conditions",
                "allergies",
            ),
            "classes": ("collapse",),
        }),
        (_("Metadata"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def full_name(self, obj):
        return obj.user.get_full_name()

    full_name.short_description = _("Name")
    full_name.admin_order_field = "user__first_name"

    def performance_score_display(self, obj):
        if obj.performance_score is None:
            return "—"
        color = (
            "green" if obj.performance_score >= 75
            else "orange" if obj.performance_score >= 60
            else "red"
        )
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color,
            obj.performance_score,
        )

    performance_score_display.short_description = _("Performance")
    performance_score_display.admin_order_field = "performance_score"


@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "staff_id_display",
        "staff_name",
        "date",
        "status",
        "recorded_by",
        "created_at",
    )
    list_filter = (
        "status",
        "date",
        "staff__school",
        "staff__staff_type",
    )
    search_fields = (
        "staff__staff_id",
        "staff__user__first_name",
        "staff__user__last_name",
        "notes",
    )
    readonly_fields = ("created_at",)
    raw_id_fields = ("staff", "recorded_by")
    date_hierarchy = "date"
    ordering = ("-date",)
    list_per_page = 30

    def staff_id_display(self, obj):
        return obj.staff.staff_id

    staff_id_display.short_description = _("Staff ID")
    staff_id_display.admin_order_field = "staff__staff_id"

    def staff_name(self, obj):
        return obj.staff.user.get_full_name()

    staff_name.short_description = _("Name")
    staff_name.admin_order_field = "staff__user__first_name"