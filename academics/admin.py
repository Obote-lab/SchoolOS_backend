from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    ContinuousAssessment,
    Exam,
    ExamResult,
    GradingSystem,
    LessonPlan,
    Subject,
    SubjectAssignment,
)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "level",
        "stream",
        "school",
        "is_active",
        "periods_per_week",
    )
    list_filter = ("category", "level", "stream", "is_active", "school")
    search_fields = ("code", "name", "school__school_name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("school", "department", "created_by")
    ordering = ("code",)

    fieldsets = (
        (_("Basic Info"), {
            "fields": (
                "school",
                "name",
                "code",
                "department",
                "category",
                "level",
                "stream",
            )
        }),
        (_("Teaching Details"), {
            "fields": (
                "periods_per_week",
                "exam_weight",
                "passing_grade",
                "recommended_textbooks",
            )
        }),
        (_("Status"), {
            "fields": ("is_active", "created_by", "created_at", "updated_at"),
        }),
    )


@admin.register(SubjectAssignment)
class SubjectAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "teacher",
        "class_room",
        "academic_year",
        "term",
        "is_primary",
        "hours_per_week",
    )
    list_filter = ("is_primary", "academic_year", "term", "subject__school")
    search_fields = (
        "subject__name",
        "subject__code",
        "teacher__user__first_name",
        "teacher__user__last_name",
        "class_room__classroom_name",
    )
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("subject", "teacher", "class_room", "academic_year", "term")
    ordering = ("-created_at",)


@admin.register(LessonPlan)
class LessonPlanAdmin(admin.ModelAdmin):
    list_display = (
        "topic",
        "week_number",
        "date",
        "lesson_plan_status",
        "actual_date_taught",
        "subject_assignment",
    )
    list_filter = (
        "lesson_plan_status",
        "week_number",
        "subject_assignment__subject__school",
    )
    search_fields = ("topic", "sub_topic", "subject_assignment__subject__name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("subject_assignment", "created_by")
    ordering = ("week_number", "date")


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "exam_date",
        "term",
        "exam_status",
        "subject",
        "class_room",
        "total_marks",
    )
    list_filter = ("exam_status", "term", "academic_year", "is_compulsory")
    search_fields = ("name", "subject__name", "class_room__classroom_name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = (
        "term",
        "academic_year",
        "subject",
        "class_room",
        "supervisor",
        "paper_setter",
        "moderator",
    )
    ordering = ("-exam_date",)

    fieldsets = (
        (_("Exam Info"), {
            "fields": (
                "name",
                "term",
                "academic_year",
                "subject",
                "class_room",
                "total_marks",
                "passing_marks",
                "weight",
            )
        }),
        (_("Scheduling"), {
            "fields": ("exam_date", "start_time", "end_time", "venue"),
        }),
        (_("Personnel"), {
            "fields": ("supervisor", "paper_setter", "moderator"),
        }),
        (_("Status"), {
            "fields": ("exam_status", "publish_date", "is_compulsory", "instructions"),
        }),
    )


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "exam",
        "subject",
        "marks",
        "grade",
        "position_in_class",
        "marked_by",
    )
    list_filter = ("exam__exam_status", "subject__school", "appeal_status")
    search_fields = (
        "student__admission_number",
        "student__user__first_name",
        "student__user__last_name",
        "exam__name",
    )
    readonly_fields = ("id", "marking_date", "created_at")
    raw_id_fields = ("student", "subject", "exam", "marked_by", "verified_by")
    ordering = ("-marks",)


@admin.register(ContinuousAssessment)
class ContinuousAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "assessment_type",
        "student",
        "subject",
        "marks_obtained",
        "maximum_marks",
        "date_assigned",
    )
    list_filter = ("assessment_type", "term", "subject__school")
    search_fields = ("title", "student__admission_number")
    readonly_fields = ("id", "date_marked", "created_at", "updated_at")
    raw_id_fields = ("student", "subject", "term", "marked_by")
    ordering = ("-date_assigned",)


@admin.register(GradingSystem)
class GradingSystemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "school",
        "system_type",
        "default_exam_weight",
        "is_active",
    )
    list_filter = ("system_type", "is_active", "school")
    search_fields = ("name", "school__school_name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("school",)
    ordering = ("name",)