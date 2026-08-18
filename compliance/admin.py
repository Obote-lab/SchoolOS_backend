from django.contrib import admin
from django.utils.html import format_html

from .models import SystemAuditEvent, ComplianceCheck, DataExportLog, SystemHealth


@admin.register(SystemAuditEvent)
class SystemAuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "user",
        "action_type",
        "model_name",
        "school",
        "user_ip",
    )
    list_filter = ("action_type", "model_name", "school", "approval_required")
    search_fields = (
        "user__login_id",
        "user__first_name",
        "user__last_name",
        "reason",
        "model_name",
    )
    readonly_fields = ("timestamp", "checksum", "blockchain_hash")
    date_hierarchy = "timestamp"

    fieldsets = (
        (
            "Basic Info",
            {"fields": ("user", "user_role", "action_type", "timestamp", "school")},
        ),
        (
            "Action Details",
            {
                "fields": (
                    "model_name",
                    "field_changed",
                    "old_value",
                    "new_value",
                    "reason",
                )
            },
        ),
        (
            "Security & Metadata",
            {
                "fields": (
                    "user_ip",
                    "user_device",
                    "session_id",
                    "location",
                    "checksum",
                    "blockchain_hash",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Approval",
            {"fields": ("approval_required", "approved_by"), "classes": ("collapse",)},
        ),
    )


@admin.register(DataExportLog)
class DataExportLogAdmin(admin.ModelAdmin):
    list_display = (
        "exported_by",
        "export_type",
        "format",
        "row_count",
        "file_size_mb",
        "created_at",
    )
    list_filter = ("export_type", "format", "approval_required")
    search_fields = ("exported_by__login_id", "purpose", "filters_applied")
    readonly_fields = ("created_at", "file_size_mb")

    def file_size_mb(self, obj):
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return 0.0

    file_size_mb.short_description = "File Size (MB)"


@admin.register(SystemHealth)
class SystemHealthAdmin(admin.ModelAdmin):
    list_display = (
        "school",
        "check_timestamp",
        "performance_score_colored",
        "backup_status",
        "sync_status",
        "storage_usage",
    )
    list_filter = ("backup_status", "sync_status", "school")
    search_fields = ("school__school_name", "issues_detected", "recommendations")
    readonly_fields = ("check_timestamp",)

    def performance_score_colored(self, obj):
        if obj.performance_score >= 90:
            color = "green"
        elif obj.performance_score >= 70:
            color = "orange"
        else:
            color = "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color,
            obj.performance_score,
        )

    performance_score_colored.short_description = "Performance"

    def storage_usage(self, obj):
        total = obj.storage_used + obj.storage_available
        if total > 0:
            percent = round((obj.storage_used / total) * 100, 1)
            return f"{percent}% ({obj.storage_used} / {total} GB)"
        return "-"

    storage_usage.short_description = "Storage Usage"


@admin.register(ComplianceCheck)
class ComplianceCheckAdmin(admin.ModelAdmin):
    list_display = (
        "school",
        "check_type",
        "check_date",
        "system_health_status",
        "score_display",
        "responsible_person",
    )
    list_filter = ("check_type", "system_health_status", "school")
    search_fields = ("school__school_name", "action_plan", "issues_found")
    readonly_fields = ("created_at", "score")

    def score_display(self, obj):
        if obj.score >= 90:
            color = "green"
        elif obj.score >= 70:
            color = "orange"
        else:
            color = "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>', color, obj.score
        )

    score_display.short_description = "Compliance Score"

    fieldsets = (
        (
            "Check Information",
            {"fields": ("school", "check_date", "check_type", "responsible_person")},
        ),
        (
            "Compliance Status",
            {
                "fields": (
                    "system_health_status",
                    "score",
                    "issues_found",
                    "action_plan",
                )
            },
        ),
        (
            "Follow-up",
            {
                "fields": (
                    "deadline",
                    "next_check_date",
                    "verified_by",
                    "verification_date",
                )
            },
        ),
        (
            "Evidence",
            {"fields": ("requirements", "evidence_files"), "classes": ("collapse",)},
        ),
    )
