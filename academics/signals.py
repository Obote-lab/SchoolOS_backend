import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from core.audit import create_audit_log
from core.choices.identity import AuditActionChoices

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

logger = logging.getLogger(__name__)

# Helpers
def _school_from_exam(exam: Exam):
    if exam.subject_id:
        return exam.subject.school
    if exam.class_room_id:
        return exam.class_room.school
    return None


def _school_from_framework(framework: AcademicFramework):
    return framework.school if framework else None


# Academic Framework
@receiver(post_save, sender=AcademicFramework)
def audit_academic_framework(sender, instance: AcademicFramework, created: bool, **kwargs):
    create_audit_log(
        actor=instance.created_by,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="AcademicFramework",
        record_id=instance.id,
        school=instance.school,
        reason=f"Academic framework {'created' if created else 'updated'}",
        new_value=(
            f"Framework '{instance.name}' ({instance.code}) | "
            f"Template: {instance.get_template_type_display()} | "
            f"Competencies: {instance.supports_competencies} | "
            f"Active: {instance.is_active}"
        ),
    )
    if created:
        logger.info(
            "New AcademicFramework created: %s (%s) for school %s",
            instance.name,
            instance.code,
            instance.school_id,
        )


# Pathway
@receiver(post_save, sender=Pathway)
def audit_pathway(sender, instance: Pathway, created: bool, **kwargs):
    school = instance.framework.school if instance.framework_id else None
    create_audit_log(
        actor=None,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="Pathway",
        record_id=instance.id,
        school=school,
        reason=f"Pathway {'created' if created else 'updated'}",
        new_value=(
            f"Pathway '{instance.name}' ({instance.code}) in framework "
            f"'{instance.framework.name if instance.framework_id else 'N/A'}' | "
            f"Default: {instance.is_default}"
        ),
    )


# Level
@receiver(post_save, sender=Level)
def audit_level(sender, instance: Level, created: bool, **kwargs):
    school = instance.framework.school if instance.framework_id else None
    create_audit_log(
        actor=None,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="Level",
        record_id=instance.id,
        school=school,
        reason=f"Level {'created' if created else 'updated'}",
        new_value=(
            f"Level '{instance.name}' ({instance.code}) | "
            f"Sequence: {instance.sequence} | "
            f"Pathway: {instance.pathway.name if instance.pathway_id else 'Shared'}"
        ),
    )


# Grading Scheme + Version
@receiver(post_save, sender=GradingScheme)
def audit_grading_scheme(sender, instance: GradingScheme, created: bool, **kwargs):
    create_audit_log(
        actor=None,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="GradingScheme",
        record_id=instance.id,
        school=instance.school,
        reason=f"Grading scheme {'created' if created else 'updated'}",
        new_value=(
            f"Scheme '{instance.name}' ({instance.code}) | "
            f"Default: {instance.is_default} | Active: {instance.is_active}"
        ),
    )


@receiver(post_save, sender=GradingSchemeVersion)
def audit_grading_scheme_version(sender, instance: GradingSchemeVersion, created: bool, **kwargs):
    school = instance.scheme.school if instance.scheme_id else None
    create_audit_log(
        actor=instance.created_by,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="GradingSchemeVersion",
        record_id=instance.id,
        school=school,
        reason=f"Grading scheme version {'created' if created else 'updated'}",
        new_value=(
            f"{instance.scheme.name} v{instance.version_number} | "
            f"Current: {instance.is_current} | "
            f"Reason: {instance.change_reason or 'N/A'}"
        ),
    )
    if created:
        logger.info(
            "New GradingSchemeVersion: %s v%s (School: %s)",
            instance.scheme.name,
            instance.version_number,
            school.id if school else None,
        )


# Assessment Scheme + Version
@receiver(post_save, sender=AssessmentScheme)
def audit_assessment_scheme(sender, instance: AssessmentScheme, created: bool, **kwargs):
    create_audit_log(
        actor=None,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="AssessmentScheme",
        record_id=instance.id,
        school=instance.school,
        reason=f"Assessment scheme {'created' if created else 'updated'}",
        new_value=(
            f"Scheme '{instance.name}' ({instance.code}) | "
            f"Default: {instance.is_default}"
        ),
    )


@receiver(post_save, sender=AssessmentSchemeVersion)
def audit_assessment_scheme_version(sender, instance: AssessmentSchemeVersion, created: bool, **kwargs):
    school = instance.scheme.school if instance.scheme_id else None
    create_audit_log(
        actor=instance.created_by,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="AssessmentSchemeVersion",
        record_id=instance.id,
        school=school,
        reason=f"Assessment scheme version {'created' if created else 'updated'}",
        new_value=(
            f"{instance.scheme.name} v{instance.version_number} | "
            f"Current: {instance.is_current} | "
            f"Reason: {instance.change_reason or 'N/A'}"
        ),
    )


# Competency Graph
@receiver(post_save, sender=LearningArea)
def audit_learning_area(sender, instance: LearningArea, created: bool, **kwargs):
    school = instance.framework.school if instance.framework_id else None
    create_audit_log(
        actor=None,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="LearningArea",
        record_id=instance.id,
        school=school,
        reason=f"Learning area {'created' if created else 'updated'}",
        new_value=f"{instance.code} - {instance.name}",
    )


@receiver(post_save, sender=Strand)
def audit_strand(sender, instance: Strand, created: bool, **kwargs):
    school = None
    if instance.learning_area_id and instance.learning_area.framework_id:
        school = instance.learning_area.framework.school
    create_audit_log(
        actor=None,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="Strand",
        record_id=instance.id,
        school=school,
        reason=f"Strand {'created' if created else 'updated'}",
        new_value=f"{instance.code} - {instance.name}",
    )


@receiver(post_save, sender=SubStrand)
def audit_sub_strand(sender, instance: SubStrand, created: bool, **kwargs):
    school = None
    if (
        instance.strand_id
        and instance.strand.learning_area_id
        and instance.strand.learning_area.framework_id
    ):
        school = instance.strand.learning_area.framework.school
    create_audit_log(
        actor=None,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="SubStrand",
        record_id=instance.id,
        school=school,
        reason=f"Sub-strand {'created' if created else 'updated'}",
        new_value=f"{instance.code} - {instance.name}",
    )


@receiver(post_save, sender=LearningOutcome)
def audit_learning_outcome(sender, instance: LearningOutcome, created: bool, **kwargs):
    school = None
    try:
        school = instance.sub_strand.strand.learning_area.framework.school
    except AttributeError:
        pass
    create_audit_log(
        actor=None,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="LearningOutcome",
        record_id=instance.id,
        school=school,
        reason=f"Learning outcome {'created' if created else 'updated'}",
        new_value=f"{instance.code}: {instance.statement[:80]}...",
    )


@receiver(post_save, sender=CompetencyEvidence)
def audit_competency_evidence(sender, instance: CompetencyEvidence, created: bool, **kwargs):
    school = instance.student.school if instance.student_id else None
    create_audit_log(
        actor=instance.recorded_by,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="CompetencyEvidence",
        record_id=instance.id,
        school=school,
        reason=f"Competency evidence {'recorded' if created else 'updated'}",
        new_value=(
            f"Student {getattr(instance.student, 'admission_number', '')} → "
            f"{instance.learning_outcome.code if instance.learning_outcome_id else 'N/A'} | "
            f"Level: {instance.competency_level or instance.score}"
        ),
    )


# Original models (updated)
@receiver(post_save, sender=Exam)
def audit_exam_lifecycle(sender, instance: Exam, created: bool, **kwargs):
    create_audit_log(
        actor=None,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="Exam",
        record_id=instance.id,
        school=_school_from_exam(instance),
        reason=f"Exam {'created' if created else 'updated'}",
        new_value=(
            f"Exam '{instance.name}' → {instance.get_exam_status_display()} "
            f"on {instance.exam_date}"
        ),
    )


@receiver(post_save, sender=Subject)
def audit_subject_creation(sender, instance: Subject, created: bool, **kwargs):
    if not created:
        # Still audit updates for important curriculum changes
        create_audit_log(
            actor=instance.created_by,
            action=AuditActionChoices.UPDATE,
            model_name="Subject",
            record_id=instance.id,
            school=instance.school,
            reason="Subject updated",
            new_value=f"Subject updated: {instance.code} - {instance.name}",
        )
        return

    create_audit_log(
        actor=instance.created_by,
        action=AuditActionChoices.CREATE,
        model_name="Subject",
        record_id=instance.id,
        school=instance.school,
        reason="New subject added to curriculum",
        new_value=f"Subject created: {instance.code} - {instance.name}",
    )
    logger.info(
        "New subject added: %s - %s (School: %s)",
        instance.code,
        instance.name,
        instance.school_id,
    )


@receiver(post_save, sender=SubjectAssignment)
def audit_assignment_change(sender, instance: SubjectAssignment, created: bool, **kwargs):
    school = instance.subject.school if instance.subject_id else None
    create_audit_log(
        actor=None,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="SubjectAssignment",
        record_id=instance.id,
        school=school,
        reason=f"Subject assignment {'created' if created else 'updated'}",
        new_value=(
            f"{instance.subject.code} → "
            f"{instance.teacher.user.get_full_name()} "
            f"in {instance.class_room}"
        ),
    )


@receiver(post_save, sender=LessonPlan)
def audit_lesson_plan_change(sender, instance: LessonPlan, created: bool, **kwargs):
    school = None
    if instance.subject_assignment_id and instance.subject_assignment.subject_id:
        school = instance.subject_assignment.subject.school

    create_audit_log(
        actor=instance.created_by,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="LessonPlan",
        record_id=instance.id,
        school=school,
        reason=f"Lesson plan {'created' if created else 'updated'}",
        new_value=(
            f"Lesson: {instance.topic} ({instance.date}) → "
            f"{instance.get_lesson_plan_status_display()}"
        ),
    )


@receiver(post_save, sender=ExamResult)
def audit_exam_result(sender, instance: ExamResult, created: bool, **kwargs):
    school = instance.student.school if instance.student_id else None
    create_audit_log(
        actor=instance.marked_by,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="ExamResult",
        record_id=instance.id,
        school=school,
        reason=f"Exam result {'recorded' if created else 'updated'}",
        new_value=(
            f"{getattr(instance.student, 'admission_number', '')} | "
            f"{instance.exam.name if instance.exam_id else 'N/A'} | "
            f"Marks: {instance.marks} | Grade: {instance.grade or 'N/A'}"
        ),
    )


@receiver(post_save, sender=ContinuousAssessment)
def audit_continuous_assessment(sender, instance: ContinuousAssessment, created: bool, **kwargs):
    school = instance.student.school if instance.student_id else None
    create_audit_log(
        actor=instance.marked_by,
        action=AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE,
        model_name="ContinuousAssessment",
        record_id=instance.id,
        school=school,
        reason=f"Continuous assessment {'recorded' if created else 'updated'}",
        new_value=(
            f"{getattr(instance.student, 'admission_number', '')} | "
            f"{instance.title} | "
            f"{instance.marks_obtained}/{instance.maximum_marks}"
        ),
    )