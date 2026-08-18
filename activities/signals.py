import json

from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from core.choices.activities import StudentActivityStatusChoices
from .models import Activity, Competition, StudentActivity


@receiver(pre_save, sender=Activity)
def validate_activity_data(sender, instance, **kwargs):
    """Validate activity data before saving."""
    if instance.max_participants <= 0:
        raise ValidationError("Max participants must be greater than 0.")
    if instance.schedule and not isinstance(instance.schedule, dict):
        try:
            instance.schedule = json.loads(instance.schedule)
        except json.JSONDecodeError:
            raise ValidationError("Schedule must be valid JSON.")
    if instance.achievements and not isinstance(instance.achievements, list):
        try:
            instance.achievements = json.loads(instance.achievements)
        except json.JSONDecodeError:
            raise ValidationError("Achievements must be a valid JSON list.")
    if instance.performance_metrics and not isinstance(
        instance.performance_metrics, dict
    ):
        try:
            instance.performance_metrics = json.loads(instance.performance_metrics)
        except json.JSONDecodeError:
            raise ValidationError("Performance metrics must be valid JSON.")


@receiver(pre_save, sender=StudentActivity)
def validate_student_activity(sender, instance, **kwargs):
    """Validate student activity enrollment."""
    if instance.student.school != instance.activity.school:
        raise ValidationError(
            f"Student {instance.student.admission_number} belongs to "
            f"{instance.student.school.school_name}, but activity {instance.activity.name} "
            f"belongs to {instance.activity.school.school_name}."
        )
    if instance._state.adding:
        if instance.activity.current_participants >= instance.activity.max_participants:
            raise ValidationError(
                f"Activity {instance.activity.name} has reached maximum participants "
                f"({instance.activity.max_participants})."
            )
    if instance.end_date and instance.end_date < instance.start_date:
        raise ValidationError("End date must be after start date.")
    if instance.talent_score and (
        instance.talent_score < 0 or instance.talent_score > 100
    ):
        raise ValidationError("Talent score must be between 0 and 100.")
    if instance.attendance_rate and (
        instance.attendance_rate < 0 or instance.attendance_rate > 100
    ):
        raise ValidationError("Attendance rate must be between 0 and 100.")


@receiver(post_save, sender=StudentActivity)
def update_activity_participant_count(sender, instance, created, **kwargs):
    """Update the activity's participant count"""
    if instance.activity:
        count = StudentActivity.objects.filter(activity=instance.activity,student_activity_status=StudentActivityStatusChoices.ACTIVE,).count()
        Activity.objects.filter(pk=instance.activity.pk).update(current_participants=count)

@receiver(pre_delete, sender=StudentActivity)
def decrement_activity_participant_count(sender, instance, **kwargs):
    if not instance.activity_id:
        return
    count = StudentActivity.objects.filter(
        activity_id=instance.activity_id,
        student_activity_status=StudentActivityStatusChoices.ACTIVE,
    ).exclude(pk=instance.pk).count()
    Activity.objects.filter(pk=instance.activity_id).update(
        current_participants=count
    )

@receiver(pre_save, sender=Competition)
def validate_competition_data(sender, instance, **kwargs):
    """Validate competition data before saving."""
    if instance.activity and instance.created_by:
        if instance.activity.school != instance.created_by.school:
            raise ValidationError(
                "Competition creator must belong to the same school as the activity."
            )
    if instance.results and not isinstance(instance.results, dict):
        try:
            instance.results = json.loads(instance.results)
        except json.JSONDecodeError:
            raise ValidationError("Results must be valid JSON.")
    if instance.participants and not isinstance(instance.participants, list):
        try:
            instance.participants = json.loads(instance.participants)
        except json.JSONDecodeError:
            raise ValidationError("Participants must be a valid JSON list.")
    if instance.media_links and not isinstance(instance.media_links, list):
        try:
            instance.media_links = json.loads(instance.media_links)
        except json.JSONDecodeError:
            raise ValidationError("Media links must be a valid JSON list.")
    if instance.sponsors and not isinstance(instance.sponsors, list):
        try:
            instance.sponsors = json.loads(instance.sponsors)
        except json.JSONDecodeError:
            raise ValidationError("Sponsors must be a valid JSON list.")


@receiver(post_save, sender=Competition)
def log_competition_to_activity(sender, instance, created, **kwargs):
    """Log competition to activity's achievements if it has awards."""

    if created and instance.results and "awards" in instance.results:
        activity = instance.activity
        if activity.achievements is None:
            activity.achievements = []
        achievement = {
            "competition": instance.name,
            "competition_level": instance.competition_level,
            "date": instance.date.isoformat(),
            "awards": instance.results.get("awards", []),
        }

        if achievement not in activity.achievements:
            activity.achievements.append(achievement)
            # Save without triggering signals
            Activity.objects.filter(pk=activity.pk).update(
                achievements=activity.achievements
            )
