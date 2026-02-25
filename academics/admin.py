# from django.contrib import admin
# from django.utils.translation import gettext_lazy as _

# from .models import (
#     Subject,
#     SubjectAssignment,
#     Exam,
#     ExamResult,
#     ContinuousAssessment,
#     GradingSystem,
# )


# @admin.register(Subject)
# class SubjectAdmin(admin.ModelAdmin):
#     list_display = (
#         "subject_code",
#         "subject_name",
#         "category",
#         "level",
#         "is_active",
#         "school_id",
#     )
#     list_filter = ("category", "level", "is_active")
#     search_fields = ("subject_code", "subject_name")
#     list_per_page = 25

#     fieldsets = (
#         (_("Basic Information"), {
#             "fields": ("subject_name", "subject_code", "school_id")
#         }),
#         (_("Classification"), {
#             "fields": ("category", "level")
#         }),
#         (_("Academic Details"), {
#             "fields": ("periods_per_week", "exam_weight"),
#             "classes": ("collapse",)
#         }),
#         (_("Status & Metadata"), {
#             "fields": ("is_active", "created_at", "updated_at"),
#             "classes": ("collapse",)
#         }),
#     )

#     readonly_fields = ("created_at", "updated_at")


# @admin.register(SubjectAssignment)
# class SubjectAssignmentAdmin(admin.ModelAdmin):
#     list_display = (
#         "subject",
#         "teacher_id",
#         "class_room_id",
#         "academic_year_id",
#         "term_id",
#         "is_primary",
#     )
#     list_filter = ("is_primary", "subject")
#     search_fields = ("subject__subject_name", "teacher_id", "class_room_id")
#     raw_id_fields = ("subject",)
#     readonly_fields = ("created_at",)

#     fieldsets = (
#         (_("Assignment"), {
#             "fields": ("subject", "teacher_id", "class_room_id")
#         }),
#         (_("Academic Period"), {
#             "fields": ("academic_year_id", "term_id")
#         }),
#         (_("Details"), {
#             "fields": ("is_primary",)
#         }),
#         (_("Metadata"), {
#             "fields": ("created_at",),
#             "classes": ("collapse",)
#         }),
#     )





# @admin.register(Exam)
# class ExamAdmin(admin.ModelAdmin):
#     list_display = ("name", "exam_date", "exam_status", "total_marks", "weight")
#     list_filter = ("exam_status", "academic_year_id", "term_id")
#     search_fields = ("name", "subject__subject_name")
#     date_hierarchy = "exam_date"
#     raw_id_fields = ("subject",)
#     readonly_fields = ("created_at", "updated_at")

#     fieldsets = (
#         (_("Basic Info"), {
#             "fields": ("name", "academic_year_id", "term_id")
#         }),
#         (_("Scope"), {
#             "fields": ("subject_id", "class_room_id")
#         }),
#         (_("Details"), {
#             "fields": ("total_marks", "weight")
#         }),
#         (_("Scheduling"), {
#             "fields": ("exam_date", "start_time", "end_time")
#         }),
#         (_("Status"), {
#             "fields": ("exam_status", "is_compulsory")
#         }),
#         (_("Metadata"), {
#             "fields": ("created_at", "updated_at"),
#             "classes": ("collapse",)
#         }),
#     )


# @admin.register(ExamResult)
# class ExamResultAdmin(admin.ModelAdmin):
#     list_display = ("student_id", "subject", "exam", "marks", "grade")
#     list_filter = ("grade", "exam__exam_status")
#     search_fields = ("student_id", "subject__subject_name", "exam__name")
#     raw_id_fields = ("subject", "exam")
#     readonly_fields = ("created_at",)

#     fieldsets = (
#         (_("Core"), {
#             "fields": ("student_id", "exam", "subject")
#         }),
#         (_("Result"), {
#             "fields": ("marks", "grade", "remark")
#         }),
#         (_("Metadata"), {
#             "fields": ("created_at",),
#             "classes": ("collapse",)
#         }),
#     )


# @admin.register(ContinuousAssessment)
# class ContinuousAssessmentAdmin(admin.ModelAdmin):
#     list_display = (
#         "student_id",
#         "subject",
#         "assessment_type",
#         "title",
#         "marks_obtained",
#         "maximum_marks",
#         "date_assigned",
#     )
#     list_filter = ("assessment_type", "date_assigned")
#     search_fields = ("student_id", "subject__subject_name", "title")
#     date_hierarchy = "date_assigned"
#     raw_id_fields = ("subject",)
#     readonly_fields = ("created_at", "updated_at")

#     fieldsets = (
#         (_("Core"), {
#             "fields": ("student_id", "subject", "assessment_type", "title")
#         }),
#         (_("Marks"), {
#             "fields": ("maximum_marks", "marks_obtained")
#         }),
#         (_("Dates"), {
#             "fields": ("date_assigned", "date_marked")
#         }),
#         (_("Metadata"), {
#             "fields": ("created_at", "updated_at"),
#             "classes": ("collapse",)
#         }),
#     )


# @admin.register(GradingSystem)
# class GradingSystemAdmin(admin.ModelAdmin):
#     list_display = ("name", "system_type", "is_active")
#     list_filter = ("system_type", "is_active")
#     search_fields = ("name", "school_id")
#     readonly_fields = ("created_at", "updated_at")

#     fieldsets = (
#         (_("Core"), {
#             "fields": ("name", "system_type", "school_id")
#         }),
#         (_("Configuration"), {
#             "fields": ("grade_scale", "default_exam_weight")
#         }),
#         (_("Status"), {
#             "fields": ("is_active",)
#         }),
#         (_("Metadata"), {
#             "fields": ("created_at", "updated_at"),
#             "classes": ("collapse",)
#         }),
#     )


