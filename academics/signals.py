import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.audit import create_audit_log
from core.choices.identity import AuditActionChoices 
from .models import Exam, LessonPlan, Subject, SubjectAssignment

logger = logging.getLogger(__name__)


def _school_from_exam(exam: Exam):
    if exam.subject_id:
        return exam.subject.school
    if exam.class_room_id:
        return exam.class_room.school
    return None


@receiver(post_save, sender=Exam)
def audit_exam_lifecycle(sender, instance: Exam, created: bool, **kwargs):
    create_audit_log(
        actor=None,  # set actor from service/view when you have request.user
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