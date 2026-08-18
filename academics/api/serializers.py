from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from students.models import StudentProfile

from ..models import (
    ContinuousAssessment,
    Exam,
    ExamResult,
    GradingSystem,
    LessonPlan,
    Subject,
    SubjectAssignment,
)


# Helper to safely get related object string representation
def get_related_display(obj, field_name, attr="name", fallback="Unknown"):
    """
    Safe way to get string representation of a related object.
    Returns fallback if relation missing or object not found.
    """
    related = getattr(obj, field_name, None)
    if not related:
        return fallback
    try:
        return getattr(related, attr, str(related))
    except Exception:
        return fallback


# List / Summary Serializers
class SubjectListSerializer(serializers.ModelSerializer):
    school_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "code",
            "category",
            "level",
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

    def get_school_name(self, obj) -> str:
        return get_related_display(obj, "school", "school_name")

    def get_department_name(self, obj) -> str:
        return get_related_display(obj, "department", "department_name")


class SubjectAssignmentListSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    teacher_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    academic_year_label = serializers.CharField( source="academic_year.label", read_only=True)
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

    def get_teacher_name(self, obj) -> str:
        return get_related_display(obj, "teacher", "full_name")

    def get_class_name(self, obj) -> str:
        return get_related_display(obj, "class_room", "classroom_name")

    def get_term_name(self, obj) -> str:
        return get_related_display(obj, "term", "name", fallback=None)


class LessonPlanListSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(
        source="subject_assignment.subject.name", read_only=True
    )
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

    def get_teacher_name(self, obj) -> str:
        return get_related_display(obj.subject_assignment, "teacher", "full_name")

    def get_class_name(self, obj) -> str:
        return get_related_display(
            obj.subject_assignment, "class_room", "classroom_name"
        )


class ExamListSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(
        source="subject.name", read_only=True, allow_null=True
    )
    class_name = serializers.CharField(
        source="class_room.classroom_name", read_only=True, allow_null=True
    )
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

    def get_supervisor_name(self, obj) -> str:
        return get_related_display(obj, "supervisor", "full_name", fallback=None)


class ExamResultListSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    exam_name = serializers.CharField(source="exam.name", read_only=True)
    # student_name = serializers.CharField(source="student.full_name", read_only=True)

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
            "created_at",
        ]
        read_only_fields = fields

    def get_student_name(self, obj) -> str:
        return get_related_display(obj, "student", "full_name")

    def get_admission_number(self, obj) -> str:
        return get_related_display(obj, "student", "admission_number")


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
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_student_name(self, obj) -> str:
        return get_related_display(obj, "student", "full_name")

    def get_admission_number(self, obj) -> str:
        return get_related_display(obj, "student", "admission_number")

    def get_marked_by_name(self, obj) -> str:
        return get_related_display(obj, "marked_by", "get_full_name", fallback=None)


class GradingSystemListSerializer(serializers.ModelSerializer):
    school_name = serializers.SerializerMethodField()

    class Meta:
        model = GradingSystem
        fields = [
            "id",
            "school",
            "school_name",
            "name",
            "system_type",
            "default_exam_weight",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields

    def get_school_name(self, obj) -> str:
        return get_related_display(obj, "school", "school_name")


#  Detail Serializers
class SubjectDetailSerializer(serializers.ModelSerializer):
    school_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "created_by"]

    def get_school_name(self, obj) -> str:
        return get_related_display(obj, "school", "school_name")

    def get_department_name(self, obj) -> str:
        return get_related_display(obj, "department", "department_name")


class LessonPlanDetailSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(
        source="subject_assignment.subject.name", read_only=True
    )
    teacher_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()

    class Meta:
        model = LessonPlan
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "created_by"]

    def get_teacher_name(self, obj) -> str:
        return get_related_display(obj.subject_assignment, "teacher", "full_name")

    def get_class_name(self, obj) -> str:
        return get_related_display(
            obj.subject_assignment, "class_room", "classroom_name"
        )


class ExamDetailSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(
        source="subject.name", read_only=True, allow_null=True
    )
    class_name = serializers.CharField(
        source="class_room.classroom_name", read_only=True, allow_null=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    supervisor_name = serializers.SerializerMethodField(allow_null=True)
    paper_setter_name = serializers.SerializerMethodField(allow_null=True)
    moderator_name = serializers.SerializerMethodField(allow_null=True)

    class Meta:
        model = Exam
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_supervisor_name(self, obj) -> str:
        return get_related_display(obj, "supervisor", "full_name", fallback=None)

    def get_paper_setter_name(self, obj) -> str:
        return get_related_display(obj, "paper_setter", "full_name", fallback=None)

    def get_moderator_name(self, obj) -> str:
        return get_related_display(obj, "moderator", "full_name", fallback=None)


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

    def get_student_name(self, obj) -> str:
        return get_related_display(obj, "student", "full_name")

    def get_admission_number(self, obj) -> str:
        return get_related_display(obj, "student", "admission_number")

    def get_marked_by_name(self, obj) -> str:
        return get_related_display(obj, "marked_by", "get_full_name", fallback=None)

    def get_verified_by_name(self, obj) -> str:
        return get_related_display(obj, "verified_by", "get_full_name", fallback=None)


#  Create / Update Serializers
class SubjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = [
            "name",
            "code",
            "school",
            "department",
            "category",
            "level",
            "stream",
            "periods_per_week",
            "recommended_textbooks",
            "exam_weight",
            "passing_grade",
        ]
        read_only_fields = ["created_by"]

    def validate(self, data):
        if data.get("exam_weight", 0) > 100:
            raise serializers.ValidationError({"exam_weight": "Cannot exceed 100%"})
        return data


    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


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
        ]
        read_only_fields = ["lesson_plan_status", "created_by"]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


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

    # def validate_marks(self, value):
    #     exam = self.initial_data.get("exam") or getattr(self.instance, "exam", None)
    #     if exam and value > exam.total_marks:
    #         raise serializers.ValidationError(f"Marks cannot exceed {exam.total_marks}")
    #     return value

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
            validated_data.setdefault("marking_date", timezone.now())
        return super().create(validated_data)


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
        return super().create(validated_data)


class BulkExamResultsUploadSerializer(serializers.Serializer):
    exam = serializers.UUIDField()
    subject = serializers.UUIDField()
    results = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="List of dicts: {'student_admission': str, 'marks': float, 'grade': str, 'remark': str}",
    )

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        school = user.school

        exam_id = validated_data["exam"]
        subject_id = validated_data["subject"]
        results_list = validated_data["results"]

        created = []
        errors = []

        for idx, row in enumerate(results_list, 1):
            try:
                admission = row.get("student_admission")
                marks = float(row["marks"])

                student = StudentProfile.objects.select_related('user').get(
                    admission_number=admission,
                    school=school
                )

                result, was_created = ExamResult.objects.update_or_create(
                    student=student,
                    exam_id=exam_id,
                    subject_id=subject_id,
                    defaults={
                        "marks": marks,
                        "grade": row.get("grade", ""),
                        "remark": row.get("remark", ""),
                        "marked_by": user,
                        "marking_date": timezone.now(),
                    },
                )
                created.append({
                    "row": idx,
                    "student": admission,
                    "marks": marks,
                    "result_id": str(result.id),
                    "created": was_created,
                })
            except StudentProfile.DoesNotExist:
                errors.append({"row": idx, "error": f"Student {admission} not found in school"})
            except ValueError as ve:
                errors.append({"row": idx, "error": f"Invalid marks: {ve}"})
            except Exception as e:
                errors.append({"row": idx, "error": str(e)})
        return {"created": created, "errors": errors}


class GradingSystemSerializer(serializers.ModelSerializer):
    school_name = serializers.SerializerMethodField()

    class Meta:
        model = GradingSystem
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_school_name(self, obj) -> str:
        return get_related_display(obj, "school", "school_name")

    def validate_default_exam_weight(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Weight must be 0–100")
        return value
