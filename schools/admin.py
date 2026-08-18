from django.contrib import admin
from django.utils.html import format_html

from .models import AcademicYear, ClassRoom, Department, School, Term


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = (
        "school_name",
        "school_code",
        "county",
        "school_type",
        "school_category",
        "is_active",
        "onboarding_status",
        "enrollment_status",
    )
    list_filter = (
        "school_type",
        "school_category",
        "boarding_status",
        "is_active",
        "onboarding_status",
        "county",
    )
    search_fields = (
        "school_name",
        "school_code",
        "nemis_code",
        "registration_number",
        "system_school_code",
    )
    readonly_fields = (
        "id",
        "system_school_code",
        "created_at",
        "updated_at",
        "enrollment_percentage",
        "vacancy_count",
        "onboarding_progress",
    )
    raw_id_fields = (
        "principal",
        "deputy_academic",
        "deputy_admin",
        "first_principal",
        "onboarded_by",
        "created_by",
        "last_modified_by",
        "current_term",
        "current_academic_year",
    )
    ordering = ("school_name",)

    def enrollment_status(self, obj):
        percentage = obj.enrollment_percentage
        if percentage >= 95:
            color = "red"
        elif percentage >= 80:
            color = "orange"
        else:
            color = "green"
        return format_html(
            '<span style="color: {};">{:.1f}%</span>', color, percentage
        )

    enrollment_status.short_description = "Enrollment"


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = (
        "year",
        "school",
        "start_date",
        "end_date",
        "is_current",
        "is_active_display",
    )
    list_filter = ("is_current", "school")
    search_fields = ("year", "label", "school__school_name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("school", "created_by")
    ordering = ("-start_date",)

    def is_active_display(self, obj):
        return obj.is_active

    is_active_display.boolean = True
    is_active_display.short_description = "Currently Active"


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "academic_year",
        "sequence",
        "start_date",
        "end_date",
        "term_status",
        "duration",
    )
    list_filter = ("term_status", "academic_year__school")
    search_fields = ("name", "academic_year__year", "academic_year__school__school_name")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "duration_days",
        "days_remaining",
    )
    raw_id_fields = ("academic_year",)
    ordering = ("academic_year", "sequence")

    def duration(self, obj):
        return f"{obj.duration_days} days"

    duration.short_description = "Duration"


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = (
        "classroom_name",
        "school",
        "level",
        "stream",
        "class_teacher",
        "capacity",
        "current_enrollment",
        "vacancy",
    )
    list_filter = ("school", "level", "subject_specialization")
    search_fields = (
        "classroom_name",
        "level",
        "stream",
        "school__school_name",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "vacancy_count",
        "occupancy_percentage",
    )
    raw_id_fields = ("school", "class_teacher", "assistant_teacher")
    ordering = ("school", "level", "stream")

    def vacancy(self, obj):
        return obj.vacancy_count

    vacancy.short_description = "Vacancies"


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = (
        "department_name",
        "department_code",
        "school",
        "head_of_department",
        "member_count",
        "budget_display",
    )
    list_filter = ("school", "department_type")
    search_fields = (
        "department_name",
        "department_code",
        "school__school_name",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("school", "head_of_department", "assistant_hod")
    ordering = ("school", "department_name")

    def budget_display(self, obj):
        return f"KES {obj.budget:,.2f}"

    budget_display.short_description = "Budget"