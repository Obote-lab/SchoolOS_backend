import logging

from django.core.exceptions import ValidationError
from django.db.models import Avg
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from accounts.models import AuditLog
from core.choices import AuditActionChoices
from core.choices.academic import ExamStatusChoices, LessonPlanStatusChoices
from .models import (
    ContinuousAssessment,
    Exam,
    ExamResult,
    LessonPlan,
    Subject,
    SubjectAssignment,
)

logger = logging.getLogger(__name__)


def _get_user_role_name(user):
    if not user:
        return ""
    highest = getattr(user, "get_highest_tier", lambda: None)()
    return highest.name if highest else ""


# Exam lifecycle
@receiver(pre_save, sender=Exam)
def update_exam_status_and_validate(sender, instance: Exam, **kwargs):
    """
    Auto-update exam status based on dates/times and validate constraints.
    """
    now = timezone.now()
    today = now.date()

    if instance.exam_date > today:
        instance.exam_status = ExamStatusChoices.SCHEDULED
    elif instance.exam_date == today:
        if instance.start_time and now.time() < instance.start_time:
            instance.exam_status = ExamStatusChoices.SCHEDULED
        elif instance.start_time and instance.end_time:
            if instance.start_time <= now.time() <= instance.end_time:
                instance.exam_status = ExamStatusChoices.IN_PROGRESS
            else:
                instance.exam_status = ExamStatusChoices.MARKING
        else:
            instance.exam_status = ExamStatusChoices.IN_PROGRESS
    else:
        # Past exam
        if instance.publish_date and instance.publish_date <= today:
            instance.exam_status = ExamStatusChoices.PUBLISHED
        elif ExamResult.objects.filter(exam=instance).exists():
            instance.exam_status = ExamStatusChoices.COMPLETED
        else:
            instance.exam_status = ExamStatusChoices.MARKING

    if (
        instance.start_time
        and instance.end_time
        and instance.start_time >= instance.end_time
    ):
        raise ValidationError({"end_time": "End time must be after start time"})


@receiver(post_save, sender=Exam)
def audit_exam_lifecycle(sender, instance: Exam, created: bool, **kwargs):
    action = AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE
    school = instance.subject.school if instance.subject else None

    AuditLog.objects.create(
        user=None,
        user_role="",
        action_type=action,
        model_name="Exam",
        record_id=instance.id,
        new_value=f"Exam '{instance.name}' → {instance.get_exam_status_display()} on {instance.exam_date}",
        reason=f"Exam {'created' if created else 'updated'}",
        school=school,
    )


# Subject & Assignment
@receiver(post_save, sender=Subject)
def audit_subject_creation(sender, instance: Subject, created: bool, **kwargs):
    if not created:
        return

    AuditLog.objects.create(
        user=instance.created_by,
        user_role=_get_user_role_name(instance.created_by),
        action_type=AuditActionChoices.CREATE,
        model_name="Subject",
        record_id=instance.id,
        new_value=f"Subject created: {instance.code} - {instance.name}",
        reason="New subject added to curriculum",
        school=instance.school,
    )
    logger.info(
        "New subject added: %s - %s (School: %s)",
        instance.code,
        instance.name,
        instance.school,
    )


@receiver(post_save, sender=SubjectAssignment)
def audit_assignment_change(sender, instance: SubjectAssignment, created: bool, **kwargs):
    action = AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE
    school = instance.subject.school if instance.subject else None

    AuditLog.objects.create(
        user=None,
        user_role="",
        action_type=action,
        model_name="SubjectAssignment",
        record_id=instance.id,
        new_value=(
            f"{instance.subject.code} → "
            f"{instance.teacher.user.get_full_name()} "
            f"in {instance.class_room}"
        ),
        reason=f"Subject assignment {'created' if created else 'updated'}",
        school=school,
    )


# Result / Assessment → performance cache
@receiver(post_save, sender=ExamResult)
@receiver(post_save, sender=ContinuousAssessment)
def update_assignment_performance_cache(sender, instance, **kwargs):
    """
    Lightweight update of SubjectAssignment.actual_performance.
    (Can be moved to Celery later for heavy load.)
    """
    student = instance.student
    subject = instance.subject
    class_room = getattr(student, "current_class", None)

    if not class_room:
        return

    if isinstance(instance, ExamResult):
        academic_year = instance.exam.academic_year
        assignments = SubjectAssignment.objects.filter(
            subject=subject,
            class_room=class_room,
            academic_year=academic_year,
        )
        avg_marks = (
            ExamResult.objects.filter(
                student=student,
                subject=subject,
                exam__academic_year=academic_year,
            ).aggregate(avg=Avg("marks"))["avg"]
            or 0
        )
    else:
        assignments = SubjectAssignment.objects.filter(
            subject=subject,
            class_room=class_room,
        )
        avg_marks = (
            ContinuousAssessment.objects.filter(
                student=student,
                subject=subject,
            ).aggregate(avg=Avg("marks_obtained"))["avg"]
            or 0
        )

    for assignment in assignments:
        assignment.actual_performance = avg_marks
        assignment.save(update_fields=["actual_performance"])


# Lesson Plan
@receiver(pre_save, sender=LessonPlan)
def update_lesson_status_based_on_date(sender, instance: LessonPlan, **kwargs):
    """Auto-set lesson plan status based on planned vs actual date."""
    today = timezone.now().date()

    if instance.actual_date_taught:
        if instance.actual_date_taught == instance.date:
            instance.lesson_plan_status = LessonPlanStatusChoices.TAUGHT
        elif instance.actual_date_taught > instance.date:
            instance.lesson_plan_status = LessonPlanStatusChoices.POSTPONED
    elif instance.date < today:
        instance.lesson_plan_status = LessonPlanStatusChoices.POSTPONED
    # else leave as planned / existing status


@receiver(post_save, sender=LessonPlan)
def audit_lesson_plan_change(sender, instance: LessonPlan, created: bool, **kwargs):
    action = AuditActionChoices.CREATE if created else AuditActionChoices.UPDATE
    school = None
    if instance.subject_assignment and instance.subject_assignment.subject:
        school = instance.subject_assignment.subject.school

    AuditLog.objects.create(
        user=instance.created_by,
        user_role=_get_user_role_name(instance.created_by),
        action_type=action,
        model_name="LessonPlan",
        record_id=instance.id,
        new_value=(
            f"Lesson: {instance.topic} ({instance.date}) → "
            f"{instance.get_lesson_plan_status_display()}"
        ),
        reason=f"Lesson plan {'created' if created else 'updated'}",
        school=school,
    )