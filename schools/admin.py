from django.contrib import admin
from django.utils.html import format_html

from .models import AcademicYear, ClassRoom, Department, School, Term


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = (
        "school_name",
        "school_code",
        "county",
        "type",
        "school_category",
        "is_active",
        "enrollment_status",
    )
    list_filter = ("type", "school_category", "boarding_status", "is_active", "county")
    search_fields = ("school_name", "school_code", "nemis_code", "registration_number")
    readonly_fields = (
        "created_at",
        "updated_at",
        "enrollment_percentage",
        "vacancy_count",
    )

    def enrollment_status(self, obj):
        percentage = obj.enrollment_percentage
        if percentage >= 95:
            color = "red"
        elif percentage >= 80:
            color = "orange"
        else:
            color = "green"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, percentage)

    enrollment_status.short_description = "Enrollment"


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = (
        "year",
        "school",
        "start_date",
        "end_date",
        "is_current",
        "term_status",
    )
    list_filter = ("is_current", "school")
    search_fields = ("year", "school__name")
    readonly_fields = ("created_at", "updated_at", "is_active")

    def term_status(self, obj):
        return obj.term_status
        return "Active" if obj.is_active else "Inactive"


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "academic_year",
        "start_date",
        "end_date",
        "term_status",
        "duration",
    )
    list_filter = ("term_status", "academic_year__school")
    search_fields = ("name", "academic_year__year")
    readonly_fields = ("created_at", "updated_at", "duration_days", "days_remaining")

    def duration(self, obj):
        return f"{obj.duration_days} days"


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = (
        "classroom_name",
        "school",
        "class_teacher",
        "capacity",
        "current_enrollment",
        "vacancy",
    )
    list_filter = ("school", "level", "subject_specialization")
    search_fields = ("name", "level", "stream", "school__name")
    readonly_fields = (
        "created_at",
        "updated_at",
        "vacancy_count",
        "occupancy_percentage",
    )

    def vacancy(self, obj):
        return obj.vacancy_count


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = (
        "department_name",
        "school",
        "head_of_department",
        "member_count",
        "budget_display",
    )
    list_filter = ("school",)
    search_fields = ("department_name", "code", "school__name")
    readonly_fields = ("created_at", "updated_at")

    def budget_display(self, obj):
        return f"KES {obj.budget:,.2f}"

    budget_display.short_description = "Budget"
