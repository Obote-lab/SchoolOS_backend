import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.choices.academic import (
    AppealStatusChoices,
    AssessmentTypeChoices,
    ExamStatusChoices,
    LessonPlanStatusChoices,
    SubjectCategoryChoices,
    SubjectLevelChoices,
    SubjectSpecializationChoices,
    UnderstandingLevelChoices,
    TemplateType,
    TermModel
)


# Helpers
def _same_school(*objs):
    """Return school_id if all non-None objs share one school; else raise."""
    school_ids = []
    for obj in objs:
        if obj is None:
            continue
        sid = getattr(obj, "school_id", None)
        if sid is None and hasattr(obj, "school"):
            sid = getattr(obj.school, "pk", None)
        if sid is not None:
            school_ids.append(sid)
    if not school_ids:
        return None
    if len(set(school_ids)) > 1:
        raise ValidationError(_("All related records must belong to the same school."))
    return school_ids[0]


# 1. Academic Framework (the constitution of a school's academic system)
class AcademicFramework(models.Model):
    """
    Top-level academic system owned by a school.
    Schools normally have one active framework; historical ones are kept
    via effective_from / effective_to for audit and dual-view reporting.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School",on_delete=models.CASCADE, related_name="academic_frameworks",)
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    template_type = models.CharField(max_length=30,choices=TemplateType.choices,default=TemplateType.CUSTOM,)
    term_model = models.CharField(max_length=20,choices=TermModel.choices,default=TermModel.TERM_BASED,)
    supports_competencies = models.BooleanField(default=False,help_text=_("Whether this framework uses the competency/strand graph."),)
    supports_pathways = models.BooleanField(default=True,help_text=_("Whether multiple pathways are allowed inside this framework."),)

    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_template_seeded = models.BooleanField(default=False,help_text=_("True if this framework was created from a system template."),)

    effective_from = models.DateField()
    effective_to = models.DateField(null=True,blank=True,help_text=_("Null means currently active."),)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="created_academic_frameworks",)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Academic Framework")
        verbose_name_plural = _("Academic Frameworks")
        unique_together = [["school", "code"]]
        ordering = ["-effective_from"]
        indexes = [
            models.Index(fields=["school", "is_active"]),
            models.Index(fields=["school", "effective_from", "effective_to"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.school})"

    def clean(self):
        super().clean()
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError(
                {"effective_to": _("Effective to must be on or after effective from.")}
            )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_currently_active(self) -> bool:
        today = timezone.now().date()
        if not self.is_active:
            return False
        if self.effective_from > today:
            return False
        if self.effective_to and self.effective_to < today:
            return False
        return True


# 2. Pathway (multiple allowed inside one framework)
class Pathway(models.Model):
    """
    A track / programme inside a framework.
    Examples: STEM, Social Sciences, Arts & Sports, Cambridge A-Level, residual Form 4, etc.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    framework = models.ForeignKey(AcademicFramework,on_delete=models.CASCADE,related_name="pathways",)

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)

    # null = inherit from framework
    supports_competencies = models.BooleanField(null=True,blank=True,help_text=_("Leave blank to inherit from the parent framework."),)

    is_default = models.BooleanField(default=False)
    sequence = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Pathway")
        verbose_name_plural = _("Pathways")
        unique_together = [["framework", "code"]]
        ordering = ["sequence", "name"]
        indexes = [
            models.Index(fields=["framework", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.framework.name})"

    def clean(self):
        super().clean()
        if self.is_default and self.framework_id:
            qs = Pathway.objects.filter(framework_id=self.framework_id, is_default=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {"is_default": _("Only one default pathway is allowed per framework.")}
                )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)

    @property
    def effective_supports_competencies(self) -> bool:
        if self.supports_competencies is not None:
            return self.supports_competencies
        return self.framework.supports_competencies


# 3. Level (flexible grade / form / year structure)
class Level(models.Model):
    """
    A grade / form / year level.
    Can be shared across all pathways (pathway=null) or specific to one pathway.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    framework = models.ForeignKey(AcademicFramework,on_delete=models.CASCADE,related_name="levels",)
    pathway = models.ForeignKey(Pathway,on_delete=models.CASCADE,null=True,blank=True,related_name="levels",help_text=_("Leave blank to share this level across all pathways."),)

    name = models.CharField(max_length=50)  # "Grade 7", "Form 4", "Year 12", "PP1"
    code = models.CharField(max_length=20)  # "G7", "F4", "Y12", "PP1"
    sequence = models.PositiveSmallIntegerField()
    age_from = models.PositiveSmallIntegerField(null=True, blank=True)
    age_to = models.PositiveSmallIntegerField(null=True, blank=True)

    is_graduation_level = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Level")
        verbose_name_plural = _("Levels")
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["framework", "code"],
                name="unique_level_code_per_framework",
            ),
            models.UniqueConstraint(
                fields=["framework", "pathway", "sequence"],
                name="unique_level_sequence_per_pathway",
            ),
        ]
        indexes = [
            models.Index(fields=["framework", "sequence"]),
            models.Index(fields=["pathway", "sequence"]),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.pathway_id and self.framework_id:
            if self.pathway.framework_id != self.framework_id:
                raise ValidationError(
                    {"pathway": _("Pathway must belong to the same framework.")}
                )
        if self.age_from is not None and self.age_to is not None:
            if self.age_from > self.age_to:
                raise ValidationError(
                    {"age_to": _("Age to must be greater than or equal to age from.")}
                )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)


# 4. Grading Scheme + Versioning
class GradingScheme(models.Model):
    """
    Named grading system. Actual bands live in versions so history is preserved.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School",on_delete=models.CASCADE,related_name="grading_schemes",)
    framework = models.ForeignKey( AcademicFramework,on_delete=models.CASCADE,null=True,blank=True,related_name="grading_schemes",)
    pathway = models.ForeignKey(Pathway,on_delete=models.CASCADE,null=True,blank=True,related_name="grading_schemes",)

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True)

    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Grading Scheme")
        verbose_name_plural = _("Grading Schemes")
        unique_together = [["school", "code"]]
        indexes = [
            models.Index(fields=["school", "is_default"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.school})"

    def clean(self):
        super().clean()
        if self.framework_id and self.school_id:
            if self.framework.school_id != self.school_id:
                raise ValidationError(
                    {"framework": _("Framework must belong to the same school.")}
                )
        if self.pathway_id and self.framework_id:
            if self.pathway.framework_id != self.framework_id:
                raise ValidationError(
                    {"pathway": _("Pathway must belong to the selected framework.")}
                )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)
        if self.is_default and self.school_id:
            type(self).objects.filter(
                school_id=self.school_id, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)


class GradingSchemeVersion(models.Model):
    """
    Immutable version of a grading scheme.
    Changing grades/points creates a new version; old results keep the old version.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheme = models.ForeignKey(GradingScheme,on_delete=models.CASCADE,related_name="versions",)

    version_number = models.PositiveIntegerField()
    # Example:
    # [
    #   {"grade": "A", "min": 80, "max": 100, "points": 12, "label": "Excellent"},
    #   {"grade": "A-", "min": 75, "max": 79.99, "points": 11, "label": "Very Good"},
    #   ...
    # ]
    grade_scale = models.JSONField(default=list)

    # For competency-based frameworks
    # [
    #   {"code": "EE", "label": "Exceeding Expectations", "min": 4, "max": 4},
    #   {"code": "ME", "label": "Meeting Expectations", "min": 3, "max": 3},
    #   ...
    # ]
    competency_levels = models.JSONField(default=list, blank=True)

    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="+",)
    created_at = models.DateTimeField(auto_now_add=True)
    change_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Grading Scheme Version")
        verbose_name_plural = _("Grading Scheme Versions")
        unique_together = [["scheme", "version_number"]]
        ordering = ["-version_number"]
        indexes = [
            models.Index(fields=["scheme", "is_current"]),
        ]

    def __str__(self):
        return f"{self.scheme.name} v{self.version_number}"

    def clean(self):
        super().clean()
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError(
                {"effective_to": _("Must be on or after effective from.")}
            )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)
        if self.is_current:
            type(self).objects.filter(
                scheme_id=self.scheme_id, is_current=True
            ).exclude(pk=self.pk).update(is_current=False)


# 5. Assessment Scheme + Versioning
class AssessmentScheme(models.Model):
    """
    Defines the kinds of assessments a school uses and their default weights.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School",on_delete=models.CASCADE,related_name="assessment_schemes",)
    framework = models.ForeignKey(AcademicFramework,on_delete=models.CASCADE,null=True,blank=True,related_name="assessment_schemes",)
    pathway = models.ForeignKey(Pathway,on_delete=models.CASCADE,null=True,blank=True,related_name="assessment_schemes",)

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True)

    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Assessment Scheme")
        verbose_name_plural = _("Assessment Schemes")
        unique_together = [["school", "code"]]

    def __str__(self):
        return f"{self.name} ({self.school})"

    def clean(self):
        super().clean()
        if self.framework_id and self.school_id:
            if self.framework.school_id != self.school_id:
                raise ValidationError(
                    {"framework": _("Framework must belong to the same school.")}
                )
        if self.pathway_id and self.framework_id:
            if self.pathway.framework_id != self.framework_id:
                raise ValidationError(
                    {"pathway": _("Pathway must belong to the selected framework.")}
                )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)
        if self.is_default and self.school_id:
            type(self).objects.filter(
                school_id=self.school_id, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)


class AssessmentSchemeVersion(models.Model):
    """
    Versioned definition of assessment types and weights.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheme = models.ForeignKey( AssessmentScheme, on_delete=models.CASCADE, related_name="versions",)

    version_number = models.PositiveIntegerField()

    # Example:
    # [
    #   {"type": "exam", "label": "End of Term Exam", "weight": 60, "is_summative": True},
    #   {"type": "ca", "label": "Continuous Assessment", "weight": 40, "is_summative": False},
    #   {"type": "project", "label": "Project", "weight": 0, "is_summative": False},
    # ]
    assessment_types = models.JSONField(default=list)

    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="+",)
    created_at = models.DateTimeField(auto_now_add=True)
    change_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Assessment Scheme Version")
        verbose_name_plural = _("Assessment Scheme Versions")
        unique_together = [["scheme", "version_number"]]
        ordering = ["-version_number"]

    def __str__(self):
        return f"{self.scheme.name} v{self.version_number}"

    def clean(self):
        super().clean()
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError(
                {"effective_to": _("Must be on or after effective from.")}
            )
        # Optional: validate that weights roughly sum to 100
        total = sum(
            Decimal(str(item.get("weight", 0)))
            for item in (self.assessment_types or [])
            if item.get("is_summative", True)
        )
        if total > 100:
            raise ValidationError(
                {"assessment_types": _("Summative weights cannot exceed 100%.")}
            )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)
        if self.is_current:
            type(self).objects.filter(
                scheme_id=self.scheme_id, is_current=True
            ).exclude(pk=self.pk).update(is_current=False)


# 6. Competency Graph (KICD-style + hybrid)
# Only used when framework/pathway.supports_competencies is True
class LearningArea(models.Model):
    """Top-level learning area (e.g. Mathematics, Languages, Science & Technology)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    framework = models.ForeignKey(AcademicFramework,on_delete=models.CASCADE,related_name="learning_areas",)
    pathway = models.ForeignKey(Pathway,on_delete=models.CASCADE,null=True,blank=True,related_name="learning_areas",help_text=_("Leave blank to share this learning area across all pathways."),)

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    sequence = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["framework", "code"]]
        ordering = ["sequence", "name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.pathway_id and self.framework_id:
            if self.pathway.framework_id != self.framework_id:
                raise ValidationError(
                    {"pathway": _("Pathway must belong to the same framework.")}
                )


class Strand(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    learning_area = models.ForeignKey(LearningArea,on_delete=models.CASCADE,related_name="strands",)

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    sequence = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [["learning_area", "code"]]
        ordering = ["sequence", "name"]

    def __str__(self):
        return f"{self.learning_area.code} → {self.name}"


class SubStrand(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    strand = models.ForeignKey(Strand,on_delete=models.CASCADE,related_name="sub_strands",)

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    sequence = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [["strand", "code"]]
        ordering = ["sequence", "name"]

    def __str__(self):
        return f"{self.strand.code} → {self.name}"


class LearningOutcome(models.Model):
    """
    Specific, measurable learning outcome / competency statement.
    This is the leaf node that teachers record evidence against.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sub_strand = models.ForeignKey(SubStrand,on_delete=models.CASCADE,related_name="learning_outcomes",)

    code = models.CharField(max_length=40)
    statement = models.TextField()
    sequence = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    # Optional link to a traditional Subject for hybrid schools
    related_subject = models.ForeignKey("Subject",on_delete=models.SET_NULL,null=True,blank=True,related_name="linked_outcomes",)

    class Meta:
        unique_together = [["sub_strand", "code"]]
        ordering = ["sequence"]

    def __str__(self):
        return f"{self.code}: {self.statement[:60]}..."


class CompetencyEvidence(models.Model):
    """
    Record of a student's performance against a specific LearningOutcome.
    Supports both rubric levels (EE/ME/AE/BE) and numeric scores for hybrid use.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile",on_delete=models.CASCADE,related_name="competency_evidence",)
    learning_outcome = models.ForeignKey( LearningOutcome, on_delete=models.CASCADE,related_name="evidence",)
    term = models.ForeignKey("schools.Term",on_delete=models.CASCADE,null=True,blank=True,)
    academic_year = models.ForeignKey("schools.AcademicYear",on_delete=models.CASCADE,)

    # Rubric level (CBC style)
    competency_level = models.CharField(max_length=10, blank=True)  # EE, ME, AE, BE, etc.

    # Optional numeric score for hybrid schools
    score = models.DecimalField(max_digits=6,decimal_places=2,null=True,blank=True,)
    max_score = models.DecimalField(max_digits=6,decimal_places=2,null=True,blank=True,)

    evidence_notes = models.TextField(blank=True)
    attachments = models.JSONField(default=list, blank=True)

    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name="+",)
    recorded_at = models.DateTimeField(auto_now_add=True)

    # Version stamps for history
    grading_scheme_version = models.ForeignKey(GradingSchemeVersion,on_delete=models.PROTECT,null=True,blank=True,related_name="+",)

    class Meta:
        verbose_name = _("Competency Evidence")
        verbose_name_plural = _("Competency Evidence")
        indexes = [
            models.Index(fields=["student", "learning_outcome"]),
            models.Index(fields=["student", "academic_year"]),
        ]

    def __str__(self):
        return f"{self.student} → {self.learning_outcome.code} ({self.competency_level or self.score})"


# 7. Evolved Subject
class Subject(models.Model):
    """Core subject / course definition – now framework & pathway aware."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey("schools.School",on_delete=models.CASCADE,related_name="subjects",)

    # New flexible links
    framework = models.ForeignKey(AcademicFramework,on_delete=models.PROTECT,null=True,blank=True,related_name="subjects",)
    pathway = models.ForeignKey( Pathway,on_delete=models.SET_NULL,null=True,blank=True,related_name="subjects",)
    level = models.ForeignKey( Level,on_delete=models.SET_NULL,null=True,blank=True,related_name="subjects",)

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    department = models.ForeignKey("schools.Department",on_delete=models.SET_NULL,null=True,blank=True,related_name="subjects",)
    category = models.CharField(max_length=20,choices=SubjectCategoryChoices.choices,default=SubjectCategoryChoices.CORE,)

    # Legacy fields – kept for backward compatibility during migration
    legacy_level = models.CharField(max_length=20,choices=SubjectLevelChoices.choices,blank=True,help_text=_("Deprecated – use the Level FK instead."),)
    stream = models.CharField(max_length=20,choices=SubjectSpecializationChoices.choices,null=True,blank=True,)

    periods_per_week = models.PositiveIntegerField(default=5,validators=[MinValueValidator(1)],)
    recommended_textbooks = models.JSONField(default=list, blank=True)
    exam_weight = models.DecimalField(max_digits=5,decimal_places=2,default=Decimal("60.00"),validators=[MinValueValidator(0), MaxValueValidator(100)],)
    passing_grade = models.CharField(max_length=5, default="D+")
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name="created_subjects",)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["school", "code"]]
        ordering = ["code"]
        indexes = [
            models.Index(fields=["school", "is_active"]),
            models.Index(fields=["framework", "pathway"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        super().clean()
        if self.exam_weight is not None and self.exam_weight > 100:
            raise ValidationError({"exam_weight": _("Cannot exceed 100%")})

        if self.department_id and self.school_id:
            if self.department.school_id != self.school_id:
                raise ValidationError(
                    {"department": _("Department must belong to the same school.")}
                )

        if self.framework_id and self.school_id:
            if self.framework.school_id != self.school_id:
                raise ValidationError(
                    {"framework": _("Framework must belong to the same school.")}
                )

        if self.pathway_id and self.framework_id:
            if self.pathway.framework_id != self.framework_id:
                raise ValidationError(
                    {"pathway": _("Pathway must belong to the selected framework.")}
                )

        if self.level_id and self.framework_id:
            if self.level.framework_id != self.framework_id:
                raise ValidationError(
                    {"level": _("Level must belong to the selected framework.")}
                )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)

# 8. Subject Assignment, Lesson Plan (largely unchanged)
class SubjectAssignment(models.Model):
    """Teacher assigned to teach a subject in a specific class / year / term."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="assignments")
    teacher = models.ForeignKey( "staff.StaffProfile",on_delete=models.CASCADE,related_name="subject_assignments",)
    class_room = models.ForeignKey("schools.ClassRoom",on_delete=models.CASCADE,related_name="subject_assignments",)
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.CASCADE, related_name="subject_assignments")
    term = models.ForeignKey("schools.Term", on_delete=models.SET_NULL, null=True, blank=True )

    is_primary = models.BooleanField(default=True)
    hours_per_week = models.PositiveIntegerField(default=5)
    schedule = models.JSONField(default=list, blank=True)
    resources_assigned = models.JSONField(default=list, blank=True)
    performance_target = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    actual_performance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    student_feedback_score = models.DecimalField(max_digits=4,decimal_places=2,null=True,blank=True,validators=[MinValueValidator(0), MaxValueValidator(5)],help_text=_("Average score from student feedback surveys (0-5)"), )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ["subject", "teacher", "class_room", "academic_year", "term"]
        ]
        indexes = [
            models.Index(fields=["teacher", "academic_year"]),
            models.Index(fields=["class_room"]),
        ]

    def __str__(self):
        return f"{self.subject.code} → {self.teacher.user.get_full_name()} ({self.class_room})"

    def clean(self):
        super().clean()
        subject_school = self.subject.school_id if self.subject_id else None

        if self.teacher_id and subject_school:
            if self.teacher.school_id != subject_school:
                raise ValidationError(
                    {"teacher": _("Teacher must belong to the subject's school.")}
                )
        if self.class_room_id and subject_school:
            if self.class_room.school_id != subject_school:
                raise ValidationError(
                    {"class_room": _("Classroom must belong to the subject's school.")}
                )
        if self.academic_year_id and subject_school:
            if self.academic_year.school_id != subject_school:
                raise ValidationError(
                    {"academic_year": _("Academic year must belong to the subject's school.")}
                )
        if self.term_id and self.academic_year_id:
            if self.term.academic_year_id != self.academic_year_id:
                raise ValidationError(
                    {"term": _("Term must belong to the selected academic year.")}
                )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)


class LessonPlan(models.Model):
    """Weekly / daily lesson plan per subject assignment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject_assignment = models.ForeignKey( SubjectAssignment,on_delete=models.CASCADE,related_name="lesson_plans",)

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
    student_understanding = models.CharField(max_length=20,choices=UnderstandingLevelChoices.choices,null=True,blank=True,)
    attachments = models.JSONField(default=list, blank=True, help_text=_("Files/links"))

    # Optional link to competency outcomes for CBC lesson plans
    linked_outcomes = models.ManyToManyField(LearningOutcome,blank=True,related_name="lesson_plans",)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,)
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

    def clean(self):
        super().clean()
        if self.week_number is not None and self.week_number < 1:
            raise ValidationError({"week_number": _("Week number must be ≥ 1.")})

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)


# 9. Exam + ExamResult (with version stamps)
class Exam(models.Model):
    """Exam / summative assessment scheduling."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)

    term = models.ForeignKey("schools.Term", on_delete=models.CASCADE)
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.CASCADE)
    subject = models.ForeignKey( Subject, on_delete=models.SET_NULL, null=True, blank=True )
    class_room = models.ForeignKey("schools.ClassRoom", on_delete=models.SET_NULL, null=True, blank=True)

    total_marks = models.PositiveIntegerField(default=100)
    passing_marks = models.PositiveIntegerField(default=50)
    weight = models.DecimalField(max_digits=5,decimal_places=2,default=Decimal("0.00"),validators=[MinValueValidator(Decimal("0")), MaxValueValidator(100)],)

    exam_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    venue = models.CharField(max_length=200, blank=True)

    supervisor = models.ForeignKey("staff.StaffProfile",on_delete=models.SET_NULL,null=True,blank=True,related_name="supervised_exams",)
    paper_setter = models.ForeignKey("staff.StaffProfile",on_delete=models.SET_NULL,null=True,blank=True,related_name="set_exams",)
    moderator = models.ForeignKey("staff.StaffProfile",on_delete=models.SET_NULL,null=True,blank=True,related_name="moderated_exams",)

    exam_status = models.CharField(max_length=20,choices=ExamStatusChoices.choices,default=ExamStatusChoices.DRAFT,)
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
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({"end_time": _("Must be after start time")})

        if not self.subject_id and not self.class_room_id:
            raise ValidationError(_("Exam must be linked to a subject or a class."))

        if self.passing_marks and self.total_marks and self.passing_marks > self.total_marks:
            raise ValidationError(
                {"passing_marks": _("Cannot exceed total marks.")}
            )

        if self.term_id and self.academic_year_id:
            if self.term.academic_year_id != self.academic_year_id:
                raise ValidationError(
                    {"term": _("Term must belong to the selected academic year.")}
                )

        school_id = None
        if self.subject_id:
            school_id = self.subject.school_id
        if self.class_room_id:
            if school_id and self.class_room.school_id != school_id:
                raise ValidationError(
                    {"class_room": _("Class must match subject's school.")}
                )
            school_id = school_id or self.class_room.school_id

        if school_id and self.academic_year_id:
            if self.academic_year.school_id != school_id:
                raise ValidationError(
                    {"academic_year": _("Academic year must match subject/class school.")}
                )

        for field in ("supervisor", "paper_setter", "moderator"):
            staff = getattr(self, field, None)
            if staff and school_id and staff.school_id != school_id:
                raise ValidationError(
                    {field: _("Staff must belong to the same school.")}
                )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)


class ExamResult(models.Model):
    """Individual student result for an exam – stores scheme versions for history."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)

    marks = models.DecimalField(max_digits=6, decimal_places=2)
    grade = models.CharField(max_length=10, blank=True)
    points = models.IntegerField(null=True, blank=True, help_text=_("Points under the scheme used at recording time"))

    position_in_class = models.IntegerField(null=True, blank=True)
    position_in_stream = models.IntegerField(null=True, blank=True)
    position_in_school = models.IntegerField(null=True, blank=True)

    remark = models.TextField(blank=True)
    teacher_comment = models.TextField(blank=True)
    parent_acknowledged = models.BooleanField(default=False)
    parent_comment = models.TextField(blank=True)

    marked_by = models.ForeignKey( settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="marked_results",)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="verified_results",)
    marking_date = models.DateTimeField(auto_now_add=True)

    appeal_status = models.CharField(max_length=20,choices=AppealStatusChoices.choices,default=AppealStatusChoices.NONE,)
    appeal_notes = models.TextField(blank=True)
    is_remark = models.BooleanField(default=False)
    previous_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    # Critical: version stamps for dual history view
    grading_scheme_version = models.ForeignKey( GradingSchemeVersion,on_delete=models.PROTECT, null=True, blank=True, related_name="+", help_text=_("Scheme version active when this result was recorded.") )
    assessment_scheme_version = models.ForeignKey( AssessmentSchemeVersion,on_delete=models.PROTECT,null=True,blank=True,related_name="+",)
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
        super().clean()
        if self.exam_id and self.marks is not None:
            if self.marks > self.exam.total_marks:
                raise ValidationError({"marks": _("Cannot exceed total marks")})
            if self.marks < 0:
                raise ValidationError({"marks": _("Marks cannot be negative")})

        if self.student_id and self.subject_id:
            if self.student.school_id != self.subject.school_id:
                raise ValidationError(
                    {"student": _("Student and subject must be in the same school.")}
                )

        if self.exam_id and self.subject_id and self.exam.subject_id:
            if self.exam.subject_id != self.subject_id:
                raise ValidationError(
                    {"subject": _("Subject must match the exam's subject.")}
                )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)

# 10. Continuous Assessment (with version stamps)
class ContinuousAssessment(models.Model):
    """Formative / continuous assessments (homework, classwork, projects, etc.)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.ForeignKey("schools.Term", on_delete=models.CASCADE)

    assessment_type = models.CharField( max_length=20, choices=AssessmentTypeChoices.choices, default=AssessmentTypeChoices.HOMEWORK, )
    title = models.CharField(max_length=200)
    maximum_marks = models.PositiveIntegerField(default=100)
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    weight = models.DecimalField(max_digits=5,decimal_places=2,default=Decimal("0.00"),validators=[MinValueValidator(Decimal("0")), MaxValueValidator(100)],)

    date_assigned = models.DateField()
    date_submitted = models.DateField(null=True, blank=True)
    date_marked = models.DateField(null=True, blank=True)
    teacher_comment = models.TextField(blank=True)
    attachments = models.JSONField(default=list, blank=True, help_text=_("Files/links"))

    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,)

    # Version stamps
    grading_scheme_version = models.ForeignKey(GradingSchemeVersion,on_delete=models.PROTECT,null=True,blank=True,related_name="+", )
    assessment_scheme_version = models.ForeignKey(AssessmentSchemeVersion,on_delete=models.PROTECT,null=True,blank=True,related_name="+",)

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
        super().clean()
        if self.marks_obtained is not None and self.maximum_marks is not None:
            if self.marks_obtained > self.maximum_marks:
                raise ValidationError(
                    {"marks_obtained": _("Cannot exceed maximum marks")}
                )
            if self.marks_obtained < 0:
                raise ValidationError(
                    {"marks_obtained": _("Cannot be negative")}
                )
        if self.weight is not None and self.weight > 100:
            raise ValidationError({"weight": _("Cannot exceed 100%")})

        if self.student_id and self.subject_id:
            if self.student.school_id != self.subject.school_id:
                raise ValidationError(
                    {"student": _("Student and subject must be in the same school.")}
                )

        if self.term_id and self.subject_id:
            if self.term.academic_year.school_id != self.subject.school_id:
                raise ValidationError(
                    {"term": _("Term must belong to the subject's school.")}
                )

    def save(self, *args, **kwargs):
        validate = kwargs.pop("validate", True)
        if validate:
            self.full_clean()
        super().save(*args, **kwargs)