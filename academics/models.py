import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Subject(models.Model):
    """Core subject/course definition"""

    class CategoryChoices(models.TextChoices):
        CORE = "core", _("Core")
        ELECTIVE = "elective", _("Elective")
        COMPULSORY = "compulsory", _("Compulsory")

    class LevelChoices(models.TextChoices):
        PRIMARY = "primary", _("Primary")
        SECONDARY = "secondary", _("Secondary")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_id = models.UUIDField()
    subject_name = models.CharField(max_length=200)
    subject_code = models.CharField(max_length=20)
    department_id = models.UUIDField(null=True, blank=True)
    category = models.CharField(max_length=20, choices=CategoryChoices.choices, default=CategoryChoices.CORE)
    level = models.CharField(max_length=20, choices=LevelChoices.choices)
    periods_per_week = models.PositiveIntegerField(default=5)
    exam_weight = models.DecimalField(max_digits=5, decimal_places=2, default=60,validators=[MinValueValidator(0), MaxValueValidator(100)])
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["school_id", "subject_code"]]
        ordering = ["subject_code"]
        indexes = [
            models.Index(fields=["school_id", "is_active"]),
            models.Index(fields=["subject_code"]),
        ]

    def __str__(self):
        return f"{self.subject_code} - {self.subject_name}"


class SubjectAssignment(models.Model):
    """Links teacher to subject + class + academic period"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher_id = models.UUIDField()
    class_room_id = models.UUIDField()
    academic_year_id = models.UUIDField()
    term_id = models.UUIDField(null=True, blank=True)
    is_primary = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["subject", "teacher_id", "class_room_id", "academic_year_id", "term_id"]]
        indexes = [
            models.Index(fields=["teacher_id", "academic_year_id"]),
            models.Index(fields=["class_room_id"]),
        ]

    def __str__(self):
        return f"{self.subject.subject_code} - Teacher({self.teacher_id})"


class Exam(models.Model):
    """Exam / test scheduling"""

    class StatusChoices(models.TextChoices):
        DRAFT = "draft", _("Draft")
        SCHEDULED = "scheduled", _("Scheduled")
        COMPLETED = "completed", _("Completed")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)  # e.g. "Mid-Term Exam", "CAT 1"
    term_id = models.UUIDField()
    academic_year_id = models.UUIDField()
    subject_id = models.UUIDField(null=True, blank=True)
    class_room_id = models.UUIDField(null=True, blank=True)
    total_marks = models.PositiveIntegerField(default=100)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    exam_date = models.DateField()
    exam_status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["exam_date"]
        indexes = [
            models.Index(fields=["exam_date", "exam_status"]),
            models.Index(fields=["subject_id"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.exam_date})"

    def clean(self):
        if not self.subject_id and not self.class_room_id:
            raise ValidationError("Exam must be linked to a subject or class")


class ExamResult(models.Model):
    """Student results for an exam"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student_id = models.UUIDField()
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    marks = models.DecimalField(max_digits=6, decimal_places=2)
    grade = models.CharField(max_length=10, blank=True)
    remark = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["student_id", "exam"]]
        ordering = ["-marks"]
        indexes = [
            models.Index(fields=["student_id", "exam"]),
        ]

    def __str__(self):
        return f"{self.student_id} - {self.exam.name} ({self.marks})"

    def clean(self):
        if self.marks > self.exam.total_marks:
            raise ValidationError({"marks": "Cannot exceed total marks"})


class ContinuousAssessment(models.Model):
    """Ongoing assessments (CATs, homework, projects)"""

    class TypeChoices(models.TextChoices):
        HOMEWORK = "homework", _("Homework")
        CLASSWORK = "classwork", _("Classwork")
        TEST = "test", _("Test/CAT")
        PROJECT = "project", _("Project")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.Student", null=True, on_delete=models.CASCADE) 
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term_id = models.UUIDField()
    assessment_type = models.CharField(max_length=20, choices=TypeChoices.choices)
    title = models.CharField(max_length=200)
    maximum_marks = models.PositiveIntegerField(default=100)
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    date_assigned = models.DateField()
    marked_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True)
    date_marked = models.DateField(null=True, blank=True)
    remark = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_assigned"]
        indexes = [
            models.Index(fields=["student_id", "subject"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.marks_obtained}/{self.maximum_marks}"

    def clean(self):
        if self.marks_obtained > self.maximum_marks:
            raise ValidationError({"marks_obtained": "Cannot exceed maximum marks"})


class GradingSystem(models.Model):
    """School-level grading configuration"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_id = models.UUIDField()
    name = models.CharField(max_length=100)
    system_type = models.CharField(max_length=20, default="kcse")
    grade_scale = models.JSONField(default=list)  # e.g. [{"min": 80, "grade": "A"}]
    default_exam_weight = models.DecimalField(max_digits=5, decimal_places=2, default=60)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["school_id", "name"]]

    def __str__(self):
        return self.name

    def clean(self):
        if self.default_exam_weight > 100:
            raise ValidationError("Default exam weight cannot exceed 100")