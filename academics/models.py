import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.choices.academic import (
    AppealStatusChoices,
    AssessmentTypeChoices,
    SubjectSpecializationChoices,
    SubjectCategoryChoices,
    SubjectLevelChoices,
    LessonPlanStatusChoices,
    UnderstandingLevelChoices,
    ExamStatusChoices,
)

class Subject(models.Model):
    """Core subject/course definition"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey( "schools.School",on_delete=models.CASCADE, related_name="subjects",)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    department = models.ForeignKey( "schools.Department",  on_delete=models.SET_NULL,null=True,blank=True, related_name="subjects",  )
    category = models.CharField(max_length=20, choices=SubjectCategoryChoices.choices, default=SubjectCategoryChoices.CORE)
    level = models.CharField(max_length=20, choices=SubjectLevelChoices.choices)
    stream = models.CharField(max_length=20,choices=SubjectSpecializationChoices.choices,null=True,blank=True)
    periods_per_week = models.PositiveIntegerField( default=5, validators=[MinValueValidator(1)] )
    recommended_textbooks = models.JSONField(default=list, blank=True)
    exam_weight = models.DecimalField( max_digits=5, decimal_places=2,default=Decimal("60.00"), validators=[MinValueValidator(0), MaxValueValidator(100)],)
    passing_grade = models.CharField(max_length=5, default="D+")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,null=True,related_name="created_subjects",)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["school", "code"]]
        ordering = ["code"]
        indexes = [
            models.Index(fields=["school", "is_active"]),
            models.Index(fields=["code"]),
            models.Index(fields=["category", "level"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        super().clean()
        if self.exam_weight > 100:
            raise ValidationError({"exam_weight": _("Cannot exceed 100%")})


class SubjectAssignment(models.Model):
    """Teacher assigned to teach subject in a specific class/year/term"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="assignments")
    teacher = models.ForeignKey( "staff.StaffProfile", on_delete=models.CASCADE, related_name="subject_assignments")
    class_room = models.ForeignKey( "schools.ClassRoom",on_delete=models.CASCADE,related_name="subject_assignments",)
    academic_year = models.ForeignKey( "schools.AcademicYear", on_delete=models.CASCADE)
    term = models.ForeignKey("schools.Term", on_delete=models.SET_NULL, null=True, blank=True)
    is_primary = models.BooleanField(default=True)
    hours_per_week = models.PositiveIntegerField(default=5)
    schedule = models.JSONField(default=list, blank=True)
    resources_assigned = models.JSONField(default=list, blank=True)
    performance_target = models.DecimalField( max_digits=5, decimal_places=2, null=True, blank=True)
    actual_performance = models.DecimalField( max_digits=5, decimal_places=2, null=True, blank=True)
    student_feedback_score = models.DecimalField( max_digits=4, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(5)], help_text=_("Average score from student feedback surveys (0-5)"),)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["subject", "teacher", "class_room", "academic_year", "term"]]
        indexes = [
            models.Index(fields=["teacher", "academic_year"]),
            models.Index(fields=["class_room"]),
        ]

    def __str__(self):
        return f"{self.subject.code} → {self.teacher.user.get_full_name()} ({self.class_room})"

class LessonPlan(models.Model):
    """Weekly/daily lesson plan per subject assignment"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject_assignment = models.ForeignKey(SubjectAssignment, on_delete=models.CASCADE, related_name="lesson_plans" )
    topic = models.CharField(max_length=200)
    sub_topic = models.CharField(max_length=200, blank=True)
    week_number = models.PositiveIntegerField()
    date = models.DateField()
    duration_minutes = models.PositiveIntegerField(default=40)
    objectives = models.TextField()
    materials = models.TextField(blank=True)
    procedure = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    homework = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    lesson_plan_status = models.CharField(max_length=20,choices=LessonPlanStatusChoices.choices,default=LessonPlanStatusChoices.PLANNED,)
    actual_date_taught = models.DateField(null=True, blank=True)
    student_understanding = models.CharField(max_length=20, choices=UnderstandingLevelChoices.choices, null=True, blank=True)
    attachments = models.JSONField(default=list, blank=True, help_text=_("Files/links"))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["week_number", "date"]
        indexes = [
            models.Index(fields=["subject_assignment", "date"]),
            models.Index(fields=["lesson_plan_status"]),
        ]

    def __str__(self):
        return f"Week {self.week_number} - {self.topic} ({self.date})"


class Exam(models.Model):
    """Exam / assessment scheduling"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    term = models.ForeignKey("schools.Term", on_delete=models.CASCADE)
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.CASCADE)
    subject = models.ForeignKey( Subject, on_delete=models.SET_NULL, null=True, blank=True)
    class_room = models.ForeignKey("schools.ClassRoom", on_delete=models.SET_NULL, null=True, blank=True )
    total_marks = models.PositiveIntegerField(default=100)
    passing_marks = models.PositiveIntegerField(default=50)
    weight = models.DecimalField( max_digits=5, decimal_places=2, default=Decimal("0.00"),validators=[MinValueValidator(Decimal("0")), MaxValueValidator(100)],)
    exam_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    venue = models.CharField(max_length=200, blank=True)
    supervisor = models.ForeignKey("staff.StaffProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="supervised_exams",)
    paper_setter = models.ForeignKey("staff.StaffProfile",on_delete=models.SET_NULL,  null=True, blank=True,related_name="set_exams", )
    moderator = models.ForeignKey("staff.StaffProfile",on_delete=models.SET_NULL,null=True,blank=True, related_name="moderated_exams", )
    exam_status = models.CharField(max_length=20, choices=ExamStatusChoices.choices, default=ExamStatusChoices.DRAFT,)
    publish_date = models.DateField(null=True, blank=True)
    is_compulsory = models.BooleanField(default=True)
    instructions = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["exam_date", "start_time"]
        indexes = [
            models.Index(fields=["term", "academic_year", "exam_status"]),
            models.Index(fields=["subject", "class_room"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.exam_date})"

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({"end_time": _("Must be after start time")})
        if not self.subject and not self.class_room:
            raise ValidationError(_("Exam must be linked to subject or class"))


class ExamResult(models.Model):
    """Individual student result for an exam"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    marks = models.DecimalField(max_digits=6, decimal_places=2)
    grade = models.CharField(max_length=10, blank=True)
    points = models.IntegerField(null=True, blank=True, help_text=_("KCSE points equivalent"))
    position_in_class = models.IntegerField(null=True, blank=True)
    position_in_stream = models.IntegerField(null=True, blank=True)
    position_in_school = models.IntegerField(null=True, blank=True)
    remark = models.TextField(blank=True)
    teacher_comment = models.TextField(blank=True)
    parent_acknowledged = models.BooleanField(default=False)
    parent_comment = models.TextField(blank=True)
    marked_by = models.ForeignKey( settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,related_name="marked_results")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,null=True, blank=True,related_name="verified_results")
    marking_date = models.DateTimeField(auto_now_add=True)
    appeal_status = models.CharField(max_length=20, choices=AppealStatusChoices.choices, default=AppealStatusChoices.NONE,)
    appeal_notes = models.TextField(blank=True)
    is_remark = models.BooleanField(default=False)
    previous_marks = models.DecimalField( max_digits=6, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["student", "exam"]]
        ordering = ["-marks"]
        indexes = [
            models.Index(fields=["student", "exam"]),
            models.Index(fields=["marks"]),
        ]

    def __str__(self):
        return f"{self.student.admission_number} - {self.exam.name} ({self.marks})"

    def clean(self):
        if self.marks > self.exam.total_marks:
            raise ValidationError({"marks": _("Cannot exceed total marks")})


class ContinuousAssessment(models.Model):
    """Formative/continuous assessments (homework, classwork, projects, etc.)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.ForeignKey("schools.Term", on_delete=models.CASCADE)
    assessment_type = models.CharField(max_length=20, choices=AssessmentTypeChoices.choices)
    title = models.CharField(max_length=200)
    maximum_marks = models.PositiveIntegerField(default=100)
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    weight = models.DecimalField( max_digits=5, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0")), MaxValueValidator(100)],)
    date_assigned = models.DateField()
    date_submitted = models.DateField(null=True, blank=True)
    date_marked = models.DateField(null=True, blank=True)
    teacher_comment = models.TextField(blank=True)
    attachments = models.JSONField(default=list, blank=True, help_text=_("Files/links"))
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_assigned"]
        indexes = [
            models.Index(fields=["student", "subject", "term"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.marks_obtained}/{self.maximum_marks}"

    def clean(self):
        if self.marks_obtained > self.maximum_marks:
            raise ValidationError({"marks_obtained": _("Cannot exceed maximum marks")})
        if self.weight > 100:
            raise ValidationError({"weight": _("Cannot exceed 100%")})

class GradingSystem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey( "schools.School", on_delete=models.CASCADE, related_name="grading_systems", )
    name = models.CharField(max_length=100)
    system_type = models.CharField(max_length=20, default="kcse")
    grade_scale = models.JSONField(default=list)
    default_exam_weight = models.DecimalField(max_digits=5, decimal_places=2, default=60)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["school", "name"]]

    def __str__(self):
        return f"{self.name} ({self.school})"

    def clean(self):
        super().clean()
        if self.default_exam_weight > 100:
            raise ValidationError({"default_exam_weight": "Cannot exceed 100"})
