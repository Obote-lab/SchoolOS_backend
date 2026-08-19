import logging
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from core.choices.attendance import AttendanceRecordStatusChoices
from .models import AttendancePattern, AttendanceRecord

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AttendanceRecord)
@receiver(post_delete, sender=AttendanceRecord)
def refresh_session_actual_count(sender, instance: AttendanceRecord, **kwargs):
    if instance.session_id:
        try:
            instance.session.update_actual_count()
        except Exception as e:
            logger.warning("Failed to refresh session count: %s", e)


@receiver(post_save, sender=AttendanceRecord)
@receiver(post_delete, sender=AttendanceRecord)
def refresh_pattern(sender, instance, **kwargs):
    session = instance.session
    pattern, _ = AttendancePattern.objects.get_or_create(
        student=instance.student,
        academic_year=session.academic_year,
        term=session.term,
    )
    pattern.recalculate()


# Pattern updates
@receiver(post_save, sender=AttendanceRecord)
def update_student_attendance_pattern(
    sender, instance: AttendanceRecord, created: bool, **kwargs
):
    """
    Lightweight incremental update of AttendancePattern.
    Prefer a periodic Celery job calling pattern.recalculate() for accuracy.
    """
    if not instance.session_id or not created:
        # Only increment on new records (status edits need full recalculate)
        return

    try:
        pattern, _ = AttendancePattern.objects.get_or_create(
            student=instance.student,
            academic_year=instance.session.academic_year,
            term=instance.session.term,
            defaults={
                "total_sessions": 0,
                "present_count": 0,
                "late_count": 0,
                "absent_count": 0,
                "excused_count": 0,
            },
        )

        status = instance.attendance_record_status
        if status == AttendanceRecordStatusChoices.PRESENT:
            pattern.present_count += 1
        elif status == AttendanceRecordStatusChoices.LATE:
            pattern.late_count += 1
        elif status == AttendanceRecordStatusChoices.ABSENT:
            pattern.absent_count += 1
        elif status == AttendanceRecordStatusChoices.EXCUSED:
            pattern.excused_count += 1
        # sick / suspended can be counted as absent or tracked separately later

        pattern.total_sessions += 1

        if pattern.total_sessions > 0:
            pattern.attendance_rate = (
                (pattern.present_count + pattern.late_count)
                / pattern.total_sessions
                * 100
            )
            pattern.tardiness_rate = (
                pattern.late_count / pattern.total_sessions * 100
            )

        pattern.save(
            update_fields=[
                "present_count",
                "late_count",
                "absent_count",
                "excused_count",
                "total_sessions",
                "attendance_rate",
                "tardiness_rate",
                "last_updated",
            ]
        )

        # Parent alert (log only for now — avoid recursive save)
        if status in {
            AttendanceRecordStatusChoices.ABSENT,
            AttendanceRecordStatusChoices.SICK,
        } and not instance.parent_notified:
            logger.info(
                "[Attendance Alert] Parent notification needed for %s (%s)",
                instance.student.admission_number,
                status,
            )
            AttendanceRecord.objects.filter(pk=instance.pk).update(
                parent_notified=True
            )

    except Exception as e:
        logger.error(
            "Failed to update attendance pattern for student %s: %s",
            instance.student_id,
            e,
        )


@receiver(post_delete, sender=AttendanceRecord)
def decrement_pattern_on_delete(sender, instance: AttendanceRecord, **kwargs):
    if not instance.session_id:
        return

    try:
        pattern = AttendancePattern.objects.filter(
            student=instance.student,
            academic_year=instance.session.academic_year,
            term=instance.session.term,
        ).first()
        if not pattern:
            return

        status = instance.attendance_record_status
        if status == AttendanceRecordStatusChoices.PRESENT:
            pattern.present_count = max(0, pattern.present_count - 1)
        elif status == AttendanceRecordStatusChoices.LATE:
            pattern.late_count = max(0, pattern.late_count - 1)
        elif status == AttendanceRecordStatusChoices.ABSENT:
            pattern.absent_count = max(0, pattern.absent_count - 1)
        elif status == AttendanceRecordStatusChoices.EXCUSED:
            pattern.excused_count = max(0, pattern.excused_count - 1)

        pattern.total_sessions = max(0, pattern.total_sessions - 1)

        if pattern.total_sessions > 0:
            pattern.attendance_rate = (
                (pattern.present_count + pattern.late_count)
                / pattern.total_sessions
                * 100
            )
            pattern.tardiness_rate = (
                pattern.late_count / pattern.total_sessions * 100
            )
        else:
            pattern.attendance_rate = 0
            pattern.tardiness_rate = 0

        pattern.save(
            update_fields=[
                "present_count",
                "late_count",
                "absent_count",
                "excused_count",
                "total_sessions",
                "attendance_rate",
                "tardiness_rate",
                "last_updated",
            ]
        )
    except Exception as e:
        logger.error("Failed to decrement attendance pattern: %s", e)