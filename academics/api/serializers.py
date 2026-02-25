from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes

from ..models import (
    Subject,
    SubjectAssignment,
    Exam,
    ExamResult,
    ContinuousAssessment,
    GradingSystem,
)



#   Helper Methods (for related object names)
def get_related_name(obj, field_name, model_path, attr="name"):
    """
    Safe helper to get related object name (e.g. school.name, teacher.full_name)
    Returns None if not found or app not available.
    """
    if not getattr(obj, field_name, None):
        return None
    try:
        model = __import__(model_path, fromlist=[""]).__dict__[model_path.split(".")[-1]]
        related = model.objects.get(id=getattr(obj, field_name))
        return getattr(related, attr, str(related))
    except (ImportError, AttributeError, model.DoesNotExist):
        return None



#   List Serializers
class SubjectListSerializer(serializers.ModelSerializer):
    """Minimal subject list for overview/search"""
    school_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = [
            "id",
            "subject_code",
            "subject_name",
            "category",
            "level",
            "school_id",
            "school_name",
            "department_id",
            "department_name",
            "is_active",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_school_name(self, obj):
        return get_related_name(obj, "school_id", "schools.models", "school_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_department_name(self, obj):
        return get_related_name(obj, "department_id", "schools.models", "name")


class SubjectAssignmentListSerializer(serializers.ModelSerializer):
    """Minimal assignment list"""
    subject_name = serializers.CharField(source="subject.subject_name", read_only=True)
    teacher_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()

    class Meta:
        model = SubjectAssignment
        fields = [
            "id",
            "subject",
            "subject_name",
            "teacher_id",
            "teacher_name",
            "class_room_id",
            "class_name",
            "academic_year_id",
            "term_id",
            "is_primary",
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_teacher_name(self, obj):
        return get_related_name(obj, "teacher_id", "staff.models", "full_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_class_name(self, obj):
        return get_related_name(obj, "class_room_id", "schools.models", "classroom_name")


class ExamListSerializer(serializers.ModelSerializer):
    """Minimal exam list"""
    subject_name = serializers.CharField(source="subject.subject_name", read_only=True, allow_null=True)
    class_name = serializers.CharField(source="class_room.classroom_name", read_only=True, allow_null=True)

    class Meta:
        model = Exam
        fields = [
            "id",
            "name",
            "exam_date",
            "exam_status",
            "total_marks",
            "weight",
            "subject_id",
            "subject_name",
            "class_room_id",
            "class_name",
        ]
        read_only_fields = fields



#   Detail Serializers
class SubjectDetailSerializer(serializers.ModelSerializer):
    """Full subject detail"""
    school_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_school_name(self, obj):
        return get_related_name(obj, "school_id", "schools.models", "school_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_department_name(self, obj):
        return get_related_name(obj, "department_id", "schools.models", "name")


class ExamDetailSerializer(serializers.ModelSerializer):
    """Full exam detail"""
    subject_name = serializers.CharField(source="subject.subject_name", read_only=True, allow_null=True)
    class_name = serializers.CharField(source="class_room.classroom_name", read_only=True, allow_null=True)

    class Meta:
        model = Exam
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        if data.get("end_time") and data.get("start_time") and data["end_time"] <= data["start_time"]:
            raise serializers.ValidationError({"end_time": "End time must be after start time"})
        return data


class ExamResultDetailSerializer(serializers.ModelSerializer):
    """Full exam result detail"""
    student_name = serializers.SerializerMethodField()
    student_admission = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.subject_name", read_only=True)
    exam_name = serializers.CharField(source="exam.name", read_only=True)

    class Meta:
        model = ExamResult
        fields = "__all__"
        read_only_fields = ["id", "created_at"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_student_name(self, obj):
        return get_related_name(obj, "student_id", "students.models", "full_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_student_admission(self, obj):
        return get_related_name(obj, "student_id", "students.models", "admission_number")


#   Create/Update Serializers
class SubjectCreateSerializer(serializers.ModelSerializer):
    """Create new subject"""
    class Meta:
        model = Subject
        fields = [
            "subject_name",
            "subject_code",
            "school_id",
            "category",
            "level",
            "periods_per_week",
            "exam_weight",
        ]

    def validate_exam_weight(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Exam weight must be between 0 and 100")
        return value

    def create(self, validated_data):
        # Optional: auto-set created_by_id if context has request
        if "request" in self.context:
            validated_data["created_by_id"] = self.context["request"].user.id
        return super().create(validated_data)


class ExamCreateSerializer(serializers.ModelSerializer):
    """Create new exam"""
    class Meta:
        model = Exam
        fields = [
            "name",
            "term_id",
            "academic_year_id",
            "subject_id",
            "class_room_id",
            "total_marks",
            "weight",
            "exam_date",
            # "start_time",
            # "end_time",
            "exam_status",
            # "is_compulsory",
        ]

    def validate(self, data):
        if not data.get("subject_id") and not data.get("class_room_id"):
            raise serializers.ValidationError(
                "Exam must be linked to a subject or a class"
            )
        if data.get("end_time") and data.get("start_time") and data["end_time"] <= data["start_time"]:
            raise serializers.ValidationError({"end_time": "End time must be after start time"})
        return data


class ExamResultCreateSerializer(serializers.ModelSerializer):
    """Create/update exam result"""
    class Meta:
        model = ExamResult
        fields = [
            "student_id",
            "exam",
            "subject",
            "marks",
            "grade",
            "remark",
        ]

    def validate_marks(self, value):
        exam = self.initial_data.get("exam") or getattr(self.instance, "exam", None)
        if exam and value > exam.total_marks:
            raise serializers.ValidationError(f"Marks cannot exceed {exam.total_marks}")
        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            # Optional: auto-set marked_by_id
            validated_data["marked_by_id"] = request.user.id
        return super().create(validated_data)



#   Bulk & Action Serializers
class BulkExamResultsUploadSerializer(serializers.Serializer):
    """Bulk upload exam results"""
    exam = serializers.UUIDField()
    subject = serializers.UUIDField()
    results = serializers.ListField(
        child=serializers.DictField(),  
        min_length=1
    )

    @transaction.atomic
    def create(self, validated_data):
        exam_id = validated_data["exam"]
        subject_id = validated_data["subject"]
        results = validated_data["results"]

        created = []
        errors = []

        for idx, res in enumerate(results, 1):
            try:
                student_admission = res["student_admission"]
                marks = float(res["marks"])

                from students.models import Student
                student = Student.objects.get(
                    admission_number=student_admission,
                    school_id=self.context["request"].user.school.id  
                )

                result, _ = ExamResult.objects.update_or_create(
                    student_id=student.id,
                    exam_id=exam_id,
                    subject_id=subject_id,
                    defaults={
                        "marks": marks,
                        "grade": res.get("grade", ""),
                        "remark": res.get("remark", ""),
                        "marked_by_id": self.context["request"].user.id,
                    }
                )
                created.append({"student": student_admission, "marks": marks})
            except Student.DoesNotExist:
                errors.append({"row": idx, "error": f"Student {student_admission} not found"})
            except Exception as e:
                errors.append({"row": idx, "error": str(e)})

        return {"created": created, "errors": errors}
    

class ContinuousAssessmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Continuous Assessment records (CATs, homework, projects, etc.)
    """
    student_name = serializers.SerializerMethodField()
    student_admission = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.subject_name", read_only=True)
    term_name = serializers.SerializerMethodField()
    marked_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ContinuousAssessment
        fields = [
            "id",
            "student",
            "student_name",
            "student_admission",
            "subject",
            "subject_name",
            "term_id",
            "term_name",
            "assessment_type",
            "title",
            "maximum_marks",
            "marks_obtained",
            "date_assigned",
            "date_marked",
            "remark",
            "marked_by",
            "marked_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_student_name(self, obj):
        return get_related_name(obj, "student_id", "students.models", "full_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_student_admission(self, obj):
        return get_related_name(obj, "student_id", "students.models", "admission_number")

    @extend_schema_field(OpenApiTypes.STR)
    def get_term_name(self, obj):
        return get_related_name(obj, "term_id", "schools.models", "name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_marked_by_name(self, obj):
        return get_related_name(obj, "marked_by_id", "accounts.models", "get_full_name")

    def validate_marks_obtained(self, value):
        max_marks = self.initial_data.get("maximum_marks") or getattr(self.instance, "maximum_marks", 100)
        if value > max_marks:
            raise serializers.ValidationError(f"Marks obtained cannot exceed maximum marks ({max_marks})")
        if value < 0:
            raise serializers.ValidationError("Marks obtained cannot be negative")
        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["marked_by_id"] = request.user.id
            if "date_marked" not in validated_data:
                validated_data["date_marked"] = timezone.now().date()
        return super().create(validated_data)
    


class GradingSystemSerializer(serializers.ModelSerializer):
    """
    Serializer for school grading systems (KCSE style, custom, etc.)
    """
    school_name = serializers.SerializerMethodField()

    class Meta:
        model = GradingSystem
        fields = [
            "id",
            "school_id",
            "school_name",
            "name",
            "system_type",
            "grade_scale",
            "default_exam_weight",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_school_name(self, obj):
        return get_related_name(obj, "school_id", "schools.models", "school_name")

    def validate_default_exam_weight(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Default exam weight must be between 0 and 100")
        return value

    def validate(self, data):
       
        return data
    


class SubjectAssignmentDetailSerializer(serializers.ModelSerializer):
    """
    Full detail serializer for subject-teacher-class assignments
    """
    subject_name = serializers.CharField(source="subject.subject_name", read_only=True)
    subject_code = serializers.CharField(source="subject.subject_code", read_only=True)
    teacher_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    academic_year_name = serializers.SerializerMethodField()
    term_name = serializers.SerializerMethodField()

    class Meta:
        model = SubjectAssignment
        fields = [
            "id",
            "subject",
            "subject_name",
            "subject_code",
            "teacher_id",
            "teacher_name",
            "class_room_id",
            "class_name",
            "academic_year_id",
            "academic_year_name",
            "term_id",
            "term_name",
            "is_primary",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_teacher_name(self, obj):
        return get_related_name(obj, "teacher_id", "staff.models", "full_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_class_name(self, obj):
        return get_related_name(obj, "class_room_id", "schools.models", "classroom_name")

    @extend_schema_field(OpenApiTypes.STR)
    def get_academic_year_name(self, obj):
        return get_related_name(obj, "academic_year_id", "schools.models", "year")

    @extend_schema_field(OpenApiTypes.STR)
    def get_term_name(self, obj):
        return get_related_name(obj, "term_id", "schools.models", "name")