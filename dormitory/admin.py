from django.contrib import admin
from django.utils.html import format_html
from .models import Dormitory, DormitoryInspection, RoomAllocation


@admin.register(Dormitory)
class DormitoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "dorm_type",
        "capacity",
        "current_occupancy",
        "occupancy_percentage",
        "dorm_status",
        "school",
    )
    list_filter = ("dorm_type", "dorm_status", "school")
    search_fields = ("name", "school__school_name", "building")
    readonly_fields = ("current_occupancy", "created_at", "updated_at")

    def occupancy_percentage(self, obj):
        if obj.capacity > 0:
            percent = round((obj.current_occupancy / obj.capacity) * 100, 1)
            color = "green" if percent <= 85 else "orange" if percent <= 95 else "red"
            return format_html('<span style="color: {};">{}%</span>', color, percent)
        return "0%"

    occupancy_percentage.short_description = "Occupancy %"

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("school", "name", "dorm_type", "building", "floor")},
        ),
        (
            "Capacity & Management",
            {"fields": ("capacity", "current_occupancy", "prefect", "matron")},
        ),
        (
            "Operations",
            {
                "fields": (
                    "curfew_time",
                    "lights_out_time",
                    "rules",
                    "facilities",
                    "rooms",
                )
            },
        ),
        ("Status", {"fields": ("dorm_status", "created_at", "updated_at")}),
    )


@admin.register(DormitoryInspection)
class DormitoryInspectionAdmin(admin.ModelAdmin):
    list_display = (
        "dormitory",
        "inspection_date",
        "average_score_colored",
        "cleanliness_score",
        "orderliness_score",
        "safety_score",
        "follow_up_required",
    )
    list_filter = ("follow_up_required", "dormitory__dorm_type", "dormitory__school")
    search_fields = ("dormitory__name", "issues_found", "actions_taken")
    readonly_fields = ("created_at", "average_score")

    def average_score_colored(self, obj):
        score = obj.average_score
        color = "green" if score >= 7 else "orange" if score >= 5 else "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>', color, score
        )

    average_score_colored.short_description = "Avg Score"

    fieldsets = (
        (
            "Inspection Info",
            {"fields": ("dormitory", "inspected_by", "inspection_date")},
        ),
        (
            "Scores",
            {"fields": ("cleanliness_score", "orderliness_score", "safety_score")},
        ),
        ("Findings", {"fields": ("issues_found", "actions_taken")}),
        (
            "Follow-up",
            {
                "fields": (
                    "follow_up_required",
                    "follow_up_date",
                    "next_inspection_date",
                )
            },
        ),
    )


@admin.register(RoomAllocation)
class RoomAllocationAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "dormitory",
        "room_number",
        "bed_number",
        "is_active",
        "start_date",
        "end_date",
    )
    list_filter = ("is_active", "dormitory__dorm_type", "dormitory__school")
    search_fields = (
        "student__admission_number",
        "student__user__first_name",
        "room_number",
    )
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Allocation",
            {
                "fields": (
                    "student",
                    "dormitory",
                    "room_number",
                    "bed_number",
                    "locker_number",
                )
            },
        ),
        ("Period", {"fields": ("start_date", "end_date", "is_active")}),
        ("Notes", {"fields": ("notes",)}),
    )
