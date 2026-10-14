from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    AcademicFramework,
    Pathway,
    Level,
    GradingScheme,
    GradingSchemeVersion,
    AssessmentScheme,
    AssessmentSchemeVersion,
    LearningArea,
    Strand,
    SubStrand,
    LearningOutcome,
    CompetencyEvidence,
    Subject,
    SubjectAssignment,
    LessonPlan,
    Exam,
    ExamResult,
    ContinuousAssessment,
)


# Academic Framework
@admin.register(AcademicFramework)
class AcademicFrameworkAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "school",
        "template_type",
        "term_model",
        "supports_competencies",
        "supports_pathways",
        "is_active",
        "effective_from",
        "effective_to",
    )
    list_filter = (
        "template_type",
        "term_model",
        "supports_competencies",
        "is_active",
        "school",
    )
    search_fields = ("name", "code", "school__school_name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("school", "created_by")
    ordering = ("-effective_from",)

    fieldsets = (
        (_("Basic Info"), {
            "fields": ("school", "name", "code", "template_type", "description"),
        }),
        (_("Behaviour"), {
            "fields": (
                "term_model",
                "supports_competencies",
                "supports_pathways",
                "is_template_seeded",
            ),
        }),
        (_("Lifecycle"), {
            "fields": ("is_active", "effective_from", "effective_to"),
        }),
        (_("Meta"), {
            "fields": ("created_by", "created_at", "updated_at"),
        }),
    )


# Pathway
@admin.register(Pathway)
class PathwayAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "framework",
        "is_default",
        "sequence",
        "supports_competencies",
        "is_active",
    )
    list_filter = ("is_default", "is_active", "framework__school")
    search_fields = ("name", "code", "framework__name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("framework",)
    ordering = ("sequence", "name")


# Level
@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "framework",
        "pathway",
        "sequence",
        "is_graduation_level",
        "is_active",
    )
    list_filter = ("is_graduation_level", "is_active", "framework__school")
    search_fields = ("name", "code", "framework__name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("framework", "pathway")
    ordering = ("sequence",)


# Grading Scheme + Version
class GradingSchemeVersionInline(admin.TabularInline):
    model = GradingSchemeVersion
    extra = 0
    readonly_fields = ("version_number", "is_current", "created_at", "created_by")
    fields = (
        "version_number",
        "effective_from",
        "effective_to",
        "is_current",
        "change_reason",
        "created_by",
        "created_at",
    )
    show_change_link = True


@admin.register(GradingScheme)
class GradingSchemeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "school",
        "framework",
        "pathway",
        "is_default",
        "is_active",
    )
    list_filter = ("is_default", "is_active", "school")
    search_fields = ("name", "code", "school__school_name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("school", "framework", "pathway")
    inlines = [GradingSchemeVersionInline]
    ordering = ("name",)


@admin.register(GradingSchemeVersion)
class GradingSchemeVersionAdmin(admin.ModelAdmin):
    list_display = (
        "scheme",
        "version_number",
        "is_current",
        "effective_from",
        "effective_to",
        "created_at",
    )
    list_filter = ("is_current", "scheme__school")
    search_fields = ("scheme__name", "change_reason")
    readonly_fields = ("id", "version_number", "created_at")
    raw_id_fields = ("scheme", "created_by")
    ordering = ("-version_number",)


# Assessment Scheme + Version
class AssessmentSchemeVersionInline(admin.TabularInline):
    model = AssessmentSchemeVersion
    extra = 0
    readonly_fields = ("version_number", "is_current", "created_at", "created_by")
    fields = (
        "version_number",
        "effective_from",
        "effective_to",
        "is_current",
        "change_reason",
        "created_by",
        "created_at",
    )
    show_change_link = True


@admin.register(AssessmentScheme)
class AssessmentSchemeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "school",
        "framework",
        "pathway",
        "is_default",
        "is_active",
    )
    list_filter = ("is_default", "is_active", "school")
    search_fields = ("name", "code", "school__school_name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("school", "framework", "pathway")
    inlines = [AssessmentSchemeVersionInline]
    ordering = ("name",)


@admin.register(AssessmentSchemeVersion)
class AssessmentSchemeVersionAdmin(admin.ModelAdmin):
    list_display = (
        "scheme",
        "version_number",
        "is_current",
        "effective_from",
        "effective_to",
        "created_at",
    )
    list_filter = ("is_current", "scheme__school")
    search_fields = ("scheme__name", "change_reason")
    readonly_fields = ("id", "version_number", "created_at")
    raw_id_fields = ("scheme", "created_by")
    ordering = ("-version_number",)


# Competency Graph
class StrandInline(admin.TabularInline):
    model = Strand
    extra = 0
    fields = ("name", "code", "sequence", "is_active")
    show_change_link = True


@admin.register(LearningArea)
class LearningAreaAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "framework",
        "pathway",
        "sequence",
        "is_active",
    )
    list_filter = ("is_active", "framework__school")
    search_fields = ("name", "code", "framework__name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("framework", "pathway")
    inlines = [StrandInline]
    ordering = ("sequence", "name")


class SubStrandInline(admin.TabularInline):
    model = SubStrand
    extra = 0
    fields = ("name", "code", "sequence", "is_active")
    show_change_link = True


@admin.register(Strand)
class StrandAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "learning_area", "sequence", "is_active")
    list_filter = ("is_active", "learning_area__framework__school")
    search_fields = ("name", "code", "learning_area__name")
    readonly_fields = ("id",)
    raw_id_fields = ("learning_area",)
    inlines = [SubStrandInline]
    ordering = ("sequence",)


class LearningOutcomeInline(admin.TabularInline):
    model = LearningOutcome
    extra = 0
    fields = ("code", "statement", "sequence", "is_active", "related_subject")
    show_change_link = True


@admin.register(SubStrand)
class SubStrandAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "strand", "sequence", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "strand__name")
    readonly_fields = ("id",)
    raw_id_fields = ("strand",)
    inlines = [LearningOutcomeInline]
    ordering = ("sequence",)


@admin.register(LearningOutcome)
class LearningOutcomeAdmin(admin.ModelAdmin):
    list_display = ("code", "statement_short", "sub_strand", "sequence", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "statement", "sub_strand__name")
    readonly_fields = ("id",)
    raw_id_fields = ("sub_strand", "related_subject")
    ordering = ("sequence",)

    def statement_short(self, obj):
        return (obj.statement[:80] + "...") if len(obj.statement) > 80 else obj.statement
    statement_short.short_description = _("Statement")


@admin.register(CompetencyEvidence)
class CompetencyEvidenceAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "learning_outcome",
        "competency_level",
        "score",
        "academic_year",
        "term",
        "recorded_at",
    )
    list_filter = ("competency_level", "academic_year", "term")
    search_fields = (
        "student__admission_number",
        "learning_outcome__code",
        "learning_outcome__statement",
    )
    readonly_fields = ("id", "recorded_at")
    raw_id_fields = (
        "student",
        "learning_outcome",
        "term",
        "academic_year",
        "recorded_by",
        "grading_scheme_version",
    )
    ordering = ("-recorded_at",)


# Subject (evolved)
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "framework",
        "pathway",
        "level",
        "school",
        "is_active",
        "periods_per_week",
    )
    list_filter = (
        "category",
        "is_active",
        "framework",
        "pathway",
        "school",
    )
    search_fields = ("code", "name", "school__school_name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = (
        "school",
        "department",
        "framework",
        "pathway",
        "level",
        "created_by",
    )
    ordering = ("code",)

    fieldsets = (
        (_("Basic Info"), {
            "fields": (
                "school",
                "name",
                "code",
                "department",
                "category",
            )
        }),
        (_("Flexible Structure"), {
            "fields": (
                "framework",
                "pathway",
                "level",
                "legacy_level",
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


# Subject Assignment
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


# Lesson Plan
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
    filter_horizontal = ("linked_outcomes",)
    ordering = ("week_number", "date")


# Exam
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


# Exam Result
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
        "grading_scheme_version",
    )
    list_filter = ("exam__exam_status", "subject__school", "appeal_status")
    search_fields = (
        "student__admission_number",
        "student__user__first_name",
        "student__user__last_name",
        "exam__name",
    )
    readonly_fields = ("id", "marking_date", "created_at")
    raw_id_fields = (
        "student",
        "subject",
        "exam",
        "marked_by",
        "verified_by",
        "grading_scheme_version",
        "assessment_scheme_version",
    )
    ordering = ("-marks",)


# Continuous Assessment
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
        "grading_scheme_version",
    )
    list_filter = ("assessment_type", "term", "subject__school")
    search_fields = ("title", "student__admission_number")
    readonly_fields = ("id", "date_marked", "created_at", "updated_at")
    raw_id_fields = (
        "student",
        "subject",
        "term",
        "marked_by",
        "grading_scheme_version",
        "assessment_scheme_version",
    )
    ordering = ("-date_assigned",)