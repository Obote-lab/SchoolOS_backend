from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from students.models import StudentProfile
from ..models import (
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


# Helpers
def get_related_display(obj, field_name, attr="name", fallback="Unknown"):
    related = getattr(obj, field_name, None)
    if not related:
        return fallback
    try:
        return getattr(related, attr, str(related))
    except Exception:
        return fallback


def get_current_grading_version(school, framework=None, pathway=None):
    """Return the current GradingSchemeVersion for the given context."""
    qs = GradingSchemeVersion.objects.filter(
        is_current=True,
        scheme__school=school,
        scheme__is_active=True,
    )
    if pathway:
        qs = qs.filter(scheme__pathway=pathway)
    elif framework:
        qs = qs.filter(scheme__framework=framework, scheme__pathway__isnull=True)
    return qs.order_by("-version_number").first()


def get_current_assessment_version(school, framework=None, pathway=None):
    """Return the current AssessmentSchemeVersion for the given context."""
    qs = AssessmentSchemeVersion.objects.filter(
        is_current=True,
        scheme__school=school,
        scheme__is_active=True,
    )
    if pathway:
        qs = qs.filter(scheme__pathway=pathway)
    elif framework:
        qs = qs.filter(scheme__framework=framework, scheme__pathway__isnull=True)
    return qs.order_by("-version_number").first()


# 1. Academic Framework
class AcademicFrameworkListSerializer(serializers.ModelSerializer):
    school_name = serializers.SerializerMethodField()
    pathways_count = serializers.SerializerMethodField()

    class Meta:
        model = AcademicFramework
        fields = [
            "id",
            "school",
            "school_name",
            "name",
            "code",
            "template_type",
            "term_model",
            "supports_competencies",
            "supports_pathways",
            "is_active",
            "is_template_seeded",
            "effective_from",
            "effective_to",
            "pathways_count",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_school_name(self, obj) -> str:
        return get_related_display(obj, "school", "school_name")

    @extend_schema_field(OpenApiTypes.INT)
    def get_pathways_count(self, obj) -> int:
        return obj.pathways.filter(is_active=True).count()


class AcademicFrameworkDetailSerializer(serializers.ModelSerializer):
    school_name = serializers.SerializerMethodField()

    class Meta:
        model = AcademicFramework
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "created_by"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_school_name(self, obj) -> str:
        return get_related_display(obj, "school", "school_name")


class AcademicFrameworkCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicFramework
        fields = [
            "name",
            "code",
            "template_type",
            "term_model",
            "supports_competencies",
            "supports_pathways",
            "description",
            "effective_from",
            "effective_to",
            "is_active",
        ]

    def validate(self, data):
        request = self.context.get("request")
        school = getattr(request, "school", None) or getattr(request.user, "school", None)
        if not school:
            raise serializers.ValidationError({"school": "School context is required."})
        data["school"] = school
        return data

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


# 2. Pathway
class PathwayListSerializer(serializers.ModelSerializer):
    framework_name = serializers.CharField(source="framework.name", read_only=True)
    effective_supports_competencies = serializers.BooleanField(read_only=True)

    class Meta:
        model = Pathway
        fields = [
            "id",
            "framework",
            "framework_name",
            "name",
            "code",
            "description",
            "supports_competencies",
            "effective_supports_competencies",
            "is_default",
            "sequence",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class PathwayDetailSerializer(serializers.ModelSerializer):
    framework_name = serializers.CharField(source="framework.name", read_only=True)
    effective_supports_competencies = serializers.BooleanField(read_only=True)

    class Meta:
        model = Pathway
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class PathwayCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pathway
        fields = [
            "framework",
            "name",
            "code",
            "description",
            "supports_competencies",
            "is_default",
            "sequence",
            "is_active",
        ]

    def validate(self, data):
        framework = data.get("framework")
        request = self.context.get("request")
        school = getattr(request, "school", None)
        if school and framework and framework.school_id != school.id:
            raise serializers.ValidationError(
                {"framework": "Framework must belong to the current school."}
            )
        return data


# 3. Level
class LevelListSerializer(serializers.ModelSerializer):
    framework_name = serializers.CharField(source="framework.name", read_only=True)
    pathway_name = serializers.CharField(source="pathway.name", read_only=True, allow_null=True)

    class Meta:
        model = Level
        fields = [
            "id",
            "framework",
            "framework_name",
            "pathway",
            "pathway_name",
            "name",
            "code",
            "sequence",
            "age_from",
            "age_to",
            "is_graduation_level",
            "is_active",
        ]
        read_only_fields = fields


class LevelDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class LevelCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = [
            "framework",
            "pathway",
            "name",
            "code",
            "sequence",
            "age_from",
            "age_to",
            "is_graduation_level",
            "is_active",
        ]


# 4. Grading Scheme + Version
class GradingSchemeVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradingSchemeVersion
        fields = [
            "id",
            "scheme",
            "version_number",
            "grade_scale",
            "competency_levels",
            "effective_from",
            "effective_to",
            "is_current",
            "change_reason",
            "created_at",
        ]
        read_only_fields = ["id", "version_number", "created_at"]


class GradingSchemeListSerializer(serializers.ModelSerializer):
    school_name = serializers.SerializerMethodField()
    current_version = serializers.SerializerMethodField()

    class Meta:
        model = GradingScheme
        fields = [
            "id",
            "school",
            "school_name",
            "framework",
            "pathway",
            "name",
            "code",
            "is_default",
            "is_active",
            "current_version",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_school_name(self, obj) -> str:
        return get_related_display(obj, "school", "school_name")

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_current_version(self, obj):
        version = obj.versions.filter(is_current=True).first()
        if version:
            return GradingSchemeVersionSerializer(version).data
        return None


class GradingSchemeDetailSerializer(serializers.ModelSerializer):
    versions = GradingSchemeVersionSerializer(many=True, read_only=True)
    school_name = serializers.SerializerMethodField()

    class Meta:
        model = GradingScheme
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_school_name(self, obj) -> str:
        return get_related_display(obj, "school", "school_name")


class GradingSchemeCreateSerializer(serializers.ModelSerializer):
    grade_scale = serializers.ListField(child=serializers.DictField(), required=True)
    competency_levels = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    change_reason = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = GradingScheme
        fields = [
            "framework",
            "pathway",
            "name",
            "code",
            "description",
            "is_default",
            "is_active",
            "grade_scale",
            "competency_levels",
            "change_reason",
        ]

    def validate(self, data):
        request = self.context.get("request")
        school = getattr(request, "school", None)
        if not school:
            raise serializers.ValidationError("School context is required.")
        data["school"] = school
        return data

    @transaction.atomic
    def create(self, validated_data):
        grade_scale = validated_data.pop("grade_scale")
        competency_levels = validated_data.pop("competency_levels", [])
        change_reason = validated_data.pop("change_reason", "Initial version")
        request = self.context.get("request")

        scheme = GradingScheme.objects.create(**validated_data)
        GradingSchemeVersion.objects.create(
            scheme=scheme,
            version_number=1,
            grade_scale=grade_scale,
            competency_levels=competency_levels,
            effective_from=timezone.now().date(),
            is_current=True,
            created_by=request.user if request and request.user.is_authenticated else None,
            change_reason=change_reason,
        )
        return scheme


class GradingSchemeVersionCreateSerializer(serializers.ModelSerializer):
    """Create a new version of an existing grading scheme."""

    class Meta:
        model = GradingSchemeVersion
        fields = [
            "scheme",
            "grade_scale",
            "competency_levels",
            "effective_from",
            "change_reason",
        ]

    @transaction.atomic
    def create(self, validated_data):
        scheme = validated_data["scheme"]
        last = scheme.versions.order_by("-version_number").first()
        next_version = (last.version_number + 1) if last else 1

        # Close previous current version
        scheme.versions.filter(is_current=True).update(
            is_current=False,
            effective_to=validated_data.get("effective_from") or timezone.now().date(),
        )

        request = self.context.get("request")
        return GradingSchemeVersion.objects.create(
            scheme=scheme,
            version_number=next_version,
            grade_scale=validated_data["grade_scale"],
            competency_levels=validated_data.get("competency_levels", []),
            effective_from=validated_data.get("effective_from") or timezone.now().date(),
            is_current=True,
            created_by=request.user if request and request.user.is_authenticated else None,
            change_reason=validated_data.get("change_reason", ""),
        )


# 5. Assessment Scheme + Version
class AssessmentSchemeVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentSchemeVersion
        fields = [
            "id",
            "scheme",
            "version_number",
            "assessment_types",
            "effective_from",
            "effective_to",
            "is_current",
            "change_reason",
            "created_at",
        ]
        read_only_fields = ["id", "version_number", "created_at"]


class AssessmentSchemeListSerializer(serializers.ModelSerializer):
    school_name = serializers.SerializerMethodField()
    current_version = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentScheme
        fields = [
            "id",
            "school",
            "school_name",
            "framework",
            "pathway",
            "name",
            "code",
            "is_default",
            "is_active",
            "current_version",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_school_name(self, obj) -> str:
        return get_related_display(obj, "school", "school_name")

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_current_version(self, obj):
        version = obj.versions.filter(is_current=True).first()
        if version:
            return AssessmentSchemeVersionSerializer(version).data
        return None


class AssessmentSchemeDetailSerializer(serializers.ModelSerializer):
    versions = AssessmentSchemeVersionSerializer(many=True, read_only=True)

    class Meta:
        model = AssessmentScheme
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class AssessmentSchemeCreateSerializer(serializers.ModelSerializer):
    assessment_types = serializers.ListField(child=serializers.DictField(), required=True)
    change_reason = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = AssessmentScheme
        fields = [
            "framework",
            "pathway",
            "name",
            "code",
            "description",
            "is_default",
            "is_active",
            "assessment_types",
            "change_reason",
        ]

    def validate(self, data):
        request = self.context.get("request")
        school = getattr(request, "school", None)
        if not school:
            raise serializers.ValidationError("School context is required.")
        data["school"] = school
        return data

    @transaction.atomic
    def create(self, validated_data):
        assessment_types = validated_data.pop("assessment_types")
        change_reason = validated_data.pop("change_reason", "Initial version")
        request = self.context.get("request")

        scheme = AssessmentScheme.objects.create(**validated_data)
        AssessmentSchemeVersion.objects.create(
            scheme=scheme,
            version_number=1,
            assessment_types=assessment_types,
            effective_from=timezone.now().date(),
            is_current=True,
            created_by=request.user if request and request.user.is_authenticated else None,
            change_reason=change_reason,
        )
        return scheme


class AssessmentSchemeVersionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentSchemeVersion
        fields = [
            "scheme",
            "assessment_types",
            "effective_from",
            "change_reason",
        ]

    @transaction.atomic
    def create(self, validated_data):
        scheme = validated_data["scheme"]
        last = scheme.versions.order_by("-version_number").first()
        next_version = (last.version_number + 1) if last else 1

        scheme.versions.filter(is_current=True).update(
            is_current=False,
            effective_to=validated_data.get("effective_from") or timezone.now().date(),
        )

        request = self.context.get("request")
        return AssessmentSchemeVersion.objects.create(
            scheme=scheme,
            version_number=next_version,
            assessment_types=validated_data["assessment_types"],
            effective_from=validated_data.get("effective_from") or timezone.now().date(),
            is_current=True,
            created_by=request.user if request and request.user.is_authenticated else None,
            change_reason=validated_data.get("change_reason", ""),
        )


# 6. Competency Graph
class LearningOutcomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningOutcome
        fields = [
            "id",
            "sub_strand",
            "code",
            "statement",
            "sequence",
            "is_active",
            "related_subject",
        ]


class SubStrandSerializer(serializers.ModelSerializer):
    learning_outcomes = LearningOutcomeSerializer(many=True, read_only=True)

    class Meta:
        model = SubStrand
        fields = [
            "id",
            "strand",
            "name",
            "code",
            "description",
            "sequence",
            "is_active",
            "learning_outcomes",
        ]


class StrandSerializer(serializers.ModelSerializer):
    sub_strands = SubStrandSerializer(many=True, read_only=True)

    class Meta:
        model = Strand
        fields = [
            "id",
            "learning_area",
            "name",
            "code",
            "description",
            "sequence",
            "is_active",
            "sub_strands",
        ]


class LearningAreaListSerializer(serializers.ModelSerializer):
    framework_name = serializers.CharField(source="framework.name", read_only=True)
    pathway_name = serializers.CharField(source="pathway.name", read_only=True, allow_null=True)
    strands_count = serializers.SerializerMethodField()

    class Meta:
        model = LearningArea
        fields = [
            "id",
            "framework",
            "framework_name",
            "pathway",
            "pathway_name",
            "name",
            "code",
            "sequence",
            "is_active",
            "strands_count",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.INT)
    def get_strands_count(self, obj) -> int:
        return obj.strands.filter(is_active=True).count()


class LearningAreaDetailSerializer(serializers.ModelSerializer):
    strands = StrandSerializer(many=True, read_only=True)

    class Meta:
        model = LearningArea
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class LearningAreaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningArea
        fields = [
            "framework",
            "pathway",
            "name",
            "code",
            "description",
            "sequence",
            "is_active",
        ]


class CompetencyEvidenceListSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.SerializerMethodField()
    outcome_code = serializers.CharField(source="learning_outcome.code", read_only=True)
    outcome_statement = serializers.CharField(source="learning_outcome.statement", read_only=True)

    class Meta:
        model = CompetencyEvidence
        fields = [
            "id",
            "student",
            "student_name",
            "admission_number",
            "learning_outcome",
            "outcome_code",
            "outcome_statement",
            "term",
            "academic_year",
            "competency_level",
            "score",
            "max_score",
            "recorded_at",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_student_name(self, obj) -> str:
        return get_related_display(obj, "student", "full_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_admission_number(self, obj) -> str:
        return get_related_display(obj, "student", "admission_number")


class CompetencyEvidenceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetencyEvidence
        fields = [
            "student",
            "learning_outcome",
            "term",
            "academic_year",
            "competency_level",
            "score",
            "max_score",
            "evidence_notes",
            "attachments",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["recorded_by"] = request.user

        # Stamp current grading scheme version
        student = validated_data["student"]
        version = get_current_grading_version(student.school)
        if version:
            validated_data["grading_scheme_version"] = version

        return super().create(validated_data)


# 7. Evolved Subject
class SubjectListSerializer(serializers.ModelSerializer):
    school_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    framework_name = serializers.CharField(source="framework.name", read_only=True, allow_null=True)
    pathway_name = serializers.CharField(source="pathway.name", read_only=True, allow_null=True)
    level_name = serializers.CharField(source="level.name", read_only=True, allow_null=True)

    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "code",
            "category",
            "framework",
            "framework_name",
            "pathway",
            "pathway_name",
            "level",
            "level_name",
            "legacy_level",
            "stream",
            "periods_per_week",
            "exam_weight",
            "passing_grade",
            "school",
            "school_name",
            "department",
            "department_name",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_school_name(self, obj) -> str:
        return get_related_display(obj, "school", "school_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_department_name(self, obj) -> str | None:
        return obj.department.name if obj.department else None


class SubjectDetailSerializer(serializers.ModelSerializer):
    school_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    framework_name = serializers.CharField(source="framework.name", read_only=True, allow_null=True)
    pathway_name = serializers.CharField(source="pathway.name", read_only=True, allow_null=True)
    level_name = serializers.CharField(source="level.name", read_only=True, allow_null=True)

    class Meta:
        model = Subject
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "created_by"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_school_name(self, obj) -> str:
        return get_related_display(obj, "school", "school_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_department_name(self, obj) -> str:
        return get_related_display(obj, "department", "name")


class SubjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = [
            "name",
            "code",
            "school",
            "department",
            "framework",
            "pathway",
            "level",
            "category",
            "legacy_level",
            "stream",
            "periods_per_week",
            "recommended_textbooks",
            "exam_weight",
            "passing_grade",
        ]
        extra_kwargs = {"school": {"required": False}}

    def validate(self, data):
        request = self.context.get("request")
        school = data.get("school") or getattr(request, "school", None)
        if not school:
            raise serializers.ValidationError({"school": "School context is required."})
        data["school"] = school

        if data.get("exam_weight", 0) > 100:
            raise serializers.ValidationError({"exam_weight": "Cannot exceed 100%"})

        dept = data.get("department")
        if dept and dept.school_id != school.id:
            raise serializers.ValidationError(
                {"department": "Department must belong to this school."}
            )

        framework = data.get("framework")
        if framework and framework.school_id != school.id:
            raise serializers.ValidationError(
                {"framework": "Framework must belong to this school."}
            )

        pathway = data.get("pathway")
        if pathway and framework and pathway.framework_id != framework.id:
            raise serializers.ValidationError(
                {"pathway": "Pathway must belong to the selected framework."}
            )

        return data

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


# 8. SubjectAssignment, LessonPlan, Exam (mostly unchanged + small improvements)
class SubjectAssignmentListSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    teacher_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    academic_year_label = serializers.CharField(source="academic_year.label", read_only=True)
    term_name = serializers.SerializerMethodField(allow_null=True)

    class Meta:
        model = SubjectAssignment
        fields = [
            "id",
            "subject",
            "subject_name",
            "subject_code",
            "teacher",
            "teacher_name",
            "class_room",
            "class_name",
            "academic_year",
            "academic_year_label",
            "term",
            "term_name",
            "is_primary",
            "hours_per_week",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_teacher_name(self, obj) -> str:
        return get_related_display(obj, "teacher", "full_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_class_name(self, obj) -> str:
        return get_related_display(obj, "class_room", "classroom_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_term_name(self, obj) -> str:
        return get_related_display(obj, "term", "name", fallback=None)


class SubjectAssignmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubjectAssignment
        fields = [
            "subject",
            "teacher",
            "class_room",
            "academic_year",
            "term",
            "is_primary",
            "hours_per_week",
            "schedule",
            "performance_target",
        ]

    def validate(self, data):
        subject = data["subject"]
        teacher = data["teacher"]
        class_room = data["class_room"]
        year = data["academic_year"]
        term = data.get("term")

        if teacher.school_id != subject.school_id:
            raise serializers.ValidationError(
                {"teacher": "Teacher must be in the subject's school."}
            )
        if class_room.school_id != subject.school_id:
            raise serializers.ValidationError(
                {"class_room": "Class must be in the subject's school."}
            )
        if year.school_id != subject.school_id:
            raise serializers.ValidationError(
                {"academic_year": "Year must match subject school."}
            )
        if term and term.academic_year_id != year.id:
            raise serializers.ValidationError(
                {"term": "Term must belong to the academic year."}
            )
        return data


class LessonPlanListSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject_assignment.subject.name", read_only=True)
    teacher_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()

    class Meta:
        model = LessonPlan
        fields = [
            "id",
            "topic",
            "sub_topic",
            "week_number",
            "date",
            "duration_minutes",
            "lesson_plan_status",
            "actual_date_taught",
            "student_understanding",
            "subject_assignment",
            "subject_name",
            "teacher_name",
            "class_name",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_teacher_name(self, obj) -> str:
        return get_related_display(obj.subject_assignment, "teacher", "full_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_class_name(self, obj) -> str:
        return get_related_display(obj.subject_assignment, "class_room", "classroom_name")


class LessonPlanDetailSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject_assignment.subject.name", read_only=True)
    teacher_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    linked_outcomes = LearningOutcomeSerializer(many=True, read_only=True)

    class Meta:
        model = LessonPlan
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "created_by"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_teacher_name(self, obj) -> str:
        return get_related_display(obj.subject_assignment, "teacher", "full_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_class_name(self, obj) -> str:
        return get_related_display(obj.subject_assignment, "class_room", "classroom_name")


class LessonPlanCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonPlan
        fields = [
            "subject_assignment",
            "topic",
            "sub_topic",
            "week_number",
            "date",
            "duration_minutes",
            "objectives",
            "materials",
            "procedure",
            "assessment",
            "homework",
            "notes",
            "linked_outcomes",
        ]
        read_only_fields = ["lesson_plan_status", "created_by"]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


class ExamListSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True, allow_null=True)
    class_name = serializers.CharField(source="class_room.classroom_name", read_only=True, allow_null=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    supervisor_name = serializers.SerializerMethodField(allow_null=True)

    class Meta:
        model = Exam
        fields = [
            "id",
            "name",
            "term",
            "term_name",
            "academic_year",
            "subject",
            "subject_name",
            "class_room",
            "class_name",
            "total_marks",
            "passing_marks",
            "weight",
            "exam_date",
            "start_time",
            "end_time",
            "venue",
            "supervisor",
            "supervisor_name",
            "exam_status",
            "publish_date",
            "is_compulsory",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_supervisor_name(self, obj) -> str:
        return get_related_display(obj, "supervisor", "full_name", fallback=None)


class ExamDetailSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True, allow_null=True)
    class_name = serializers.CharField(source="class_room.classroom_name", read_only=True, allow_null=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    supervisor_name = serializers.SerializerMethodField(allow_null=True)
    paper_setter_name = serializers.SerializerMethodField(allow_null=True)
    moderator_name = serializers.SerializerMethodField(allow_null=True)

    class Meta:
        model = Exam
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_supervisor_name(self, obj) -> str:
        return get_related_display(obj, "supervisor", "full_name", fallback=None)

    @extend_schema_field(OpenApiTypes.STR)
    def get_paper_setter_name(self, obj) -> str:
        return get_related_display(obj, "paper_setter", "full_name", fallback=None)

    @extend_schema_field(OpenApiTypes.STR)
    def get_moderator_name(self, obj) -> str:
        return get_related_display(obj, "moderator", "full_name", fallback=None)


class ExamCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = [
            "name",
            "term",
            "academic_year",
            "subject",
            "class_room",
            "total_marks",
            "passing_marks",
            "weight",
            "exam_date",
            "start_time",
            "end_time",
            "venue",
            "supervisor",
            "paper_setter",
            "moderator",
            "is_compulsory",
            "instructions",
        ]

    def validate(self, data):
        if not data.get("subject") and not data.get("class_room"):
            raise serializers.ValidationError("Must specify subject or class_room")
        if (
            data.get("start_time")
            and data.get("end_time")
            and data["start_time"] >= data["end_time"]
        ):
            raise serializers.ValidationError({"end_time": "Must be after start_time"})
        return data


# 9. ExamResult & ContinuousAssessment (with version stamping)
class ExamResultListSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    exam_name = serializers.CharField(source="exam.name", read_only=True)
    grading_scheme_version_number = serializers.IntegerField(
        source="grading_scheme_version.version_number", read_only=True, allow_null=True
    )

    class Meta:
        model = ExamResult
        fields = [
            "id",
            "student",
            "student_name",
            "admission_number",
            "exam",
            "exam_name",
            "subject",
            "subject_name",
            "marks",
            "grade",
            "points",
            "position_in_class",
            "position_in_stream",
            "position_in_school",
            "remark",
            "grading_scheme_version",
            "grading_scheme_version_number",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_student_name(self, obj) -> str:
        return get_related_display(obj, "student", "full_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_admission_number(self, obj) -> str:
        return get_related_display(obj, "student", "admission_number")


class ExamResultDetailSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    exam_name = serializers.CharField(source="exam.name", read_only=True)
    marked_by_name = serializers.SerializerMethodField(allow_null=True)
    verified_by_name = serializers.SerializerMethodField(allow_null=True)

    class Meta:
        model = ExamResult
        fields = "__all__"
        read_only_fields = ["id", "created_at", "marking_date"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_student_name(self, obj) -> str:
        return get_related_display(obj, "student", "full_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_admission_number(self, obj) -> str:
        return get_related_display(obj, "student", "admission_number")

    @extend_schema_field(OpenApiTypes.STR)
    def get_marked_by_name(self, obj) -> str:
        return get_related_display(obj, "marked_by", "get_full_name", fallback=None)

    @extend_schema_field(OpenApiTypes.STR)
    def get_verified_by_name(self, obj) -> str:
        return get_related_display(obj, "verified_by", "get_full_name", fallback=None)


class ExamResultCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamResult
        fields = [
            "student",
            "subject",
            "exam",
            "marks",
            "grade",
            "points",
            "position_in_class",
            "position_in_stream",
            "position_in_school",
            "remark",
            "teacher_comment",
            "parent_acknowledged",
            "parent_comment",
            "appeal_status",
            "appeal_notes",
            "is_remark",
            "previous_marks",
        ]

    def validate(self, data):
        exam = data.get("exam") or getattr(self.instance, "exam", None)
        marks = data.get("marks")
        if exam and marks is not None and marks > exam.total_marks:
            raise serializers.ValidationError(
                {"marks": f"Marks cannot exceed {exam.total_marks}"}
            )
        return data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["marked_by"] = request.user

        student = validated_data["student"]
        subject = validated_data.get("subject")

        # Stamp current scheme versions
        framework = subject.framework if subject else None
        pathway = subject.pathway if subject else None

        grading_version = get_current_grading_version(
            student.school, framework=framework, pathway=pathway
        )
        assessment_version = get_current_assessment_version(
            student.school, framework=framework, pathway=pathway
        )

        if grading_version:
            validated_data["grading_scheme_version"] = grading_version
        if assessment_version:
            validated_data["assessment_scheme_version"] = assessment_version

        return super().create(validated_data)


class ContinuousAssessmentListSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    marked_by_name = serializers.SerializerMethodField(allow_null=True)

    class Meta:
        model = ContinuousAssessment
        fields = [
            "id",
            "student",
            "student_name",
            "admission_number",
            "subject",
            "subject_name",
            "term",
            "term_name",
            "assessment_type",
            "title",
            "maximum_marks",
            "marks_obtained",
            "weight",
            "date_assigned",
            "date_submitted",
            "date_marked",
            "marked_by",
            "marked_by_name",
            "grading_scheme_version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_student_name(self, obj) -> str:
        return get_related_display(obj, "student", "full_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_admission_number(self, obj) -> str:
        return get_related_display(obj, "student", "admission_number")

    @extend_schema_field(OpenApiTypes.STR)
    def get_marked_by_name(self, obj) -> str:
        return get_related_display(obj, "marked_by", "get_full_name", fallback=None)


class ContinuousAssessmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContinuousAssessment
        fields = [
            "student",
            "subject",
            "term",
            "assessment_type",
            "title",
            "maximum_marks",
            "marks_obtained",
            "weight",
            "date_assigned",
            "date_submitted",
            "date_marked",
            "teacher_comment",
            "attachments",
        ]

    def validate_marks_obtained(self, value):
        max_marks = self.initial_data.get("maximum_marks", 100)
        if value > max_marks:
            raise serializers.ValidationError(f"Cannot exceed {max_marks}")
        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["marked_by"] = request.user
            validated_data.setdefault("date_marked", timezone.now().date())

        student = validated_data["student"]
        subject = validated_data.get("subject")
        framework = subject.framework if subject else None
        pathway = subject.pathway if subject else None

        grading_version = get_current_grading_version(student.school, framework=framework, pathway=pathway)
        assessment_version = get_current_assessment_version(student.school, framework=framework, pathway=pathway)

        if grading_version:
            validated_data["grading_scheme_version"] = grading_version
        if assessment_version:
            validated_data["assessment_scheme_version"] = assessment_version

        return super().create(validated_data)


# 10. Bulk Upload
class BulkResultRowSerializer(serializers.Serializer):
    student_admission = serializers.CharField()
    marks = serializers.DecimalField(max_digits=6, decimal_places=2)
    grade = serializers.CharField(required=False, allow_blank=True, default="")
    remark = serializers.CharField(required=False, allow_blank=True, default="")


class BulkExamResultsUploadSerializer(serializers.Serializer):
    exam = serializers.UUIDField()
    subject = serializers.UUIDField()
    results = BulkResultRowSerializer(many=True)

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        school = getattr(request, "school", None) or getattr(user, "school", None)
        if not school:
            raise serializers.ValidationError("School context is required.")

        exam_id = validated_data["exam"]
        subject_id = validated_data["subject"]

        # Get current versions once
        try:
            subject = Subject.objects.get(id=subject_id, school=school)
        except Subject.DoesNotExist:
            raise serializers.ValidationError({"subject": "Subject not found in this school."})

        grading_version = get_current_grading_version(school, framework=subject.framework, pathway=subject.pathway)
        assessment_version = get_current_assessment_version(school, framework=subject.framework, pathway=subject.pathway)

        created, errors = [], []
        for idx, row in enumerate(validated_data["results"], 1):
            admission = row["student_admission"]
            try:
                student = StudentProfile.objects.get(
                    admission_number=admission, school=school
                )
                result, was_created = ExamResult.objects.update_or_create(
                    student=student,
                    exam_id=exam_id,
                    defaults={
                        "subject_id": subject_id,
                        "marks": row["marks"],
                        "grade": row.get("grade") or "",
                        "remark": row.get("remark") or "",
                        "marked_by": user,
                        "grading_scheme_version": grading_version,
                        "assessment_scheme_version": assessment_version,
                    },
                )
                created.append({
                    "row": idx,
                    "student": admission,
                    "marks": str(row["marks"]),
                    "result_id": str(result.id),
                    "created": was_created,
                })
            except StudentProfile.DoesNotExist:
                errors.append({"row": idx, "error": f"Student {admission} not found"})
            except Exception as e:
                errors.append({"row": idx, "error": str(e)})

        return {"created": created, "errors": errors}