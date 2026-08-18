from django.contrib import admin

from .models import Activity, Competition, StudentActivity


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "activity_category",
        "school",
        "current_participants",
        "activity_status",
    )
    list_filter = ("activity_category", "activity_status", "season", "school")
    search_fields = ("name", "description", "school__school_name")
    readonly_fields = ("current_participants", "created_at")
    filter_horizontal = ()


@admin.register(StudentActivity)
class StudentActivityAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "activity",
        "role",
        "student_activity_status",
        "performance_level",
    )
    list_filter = (
        "student_activity_status",
        "role",
        "performance_level",
        "activity__school",
    )
    search_fields = (
        "student__admission_number",
        "student__user__username",
        "activity__name",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ("name", "activity", "competition_level", "date", "venue")
    list_filter = ("competition_level", "date", "activity__school")
    search_fields = ("name", "venue", "organizer", "activity__name")
    readonly_fields = ("created_at",)
