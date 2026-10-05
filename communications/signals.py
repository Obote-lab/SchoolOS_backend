from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from core.audit import create_audit_log
from core.choices.identity import AuditActionChoices
from core.choices.communications import (
    AnnouncementStatusChoices,
    FeedbackPriorityChoices,
    FeedbackStatusChoices,
    NotificationCategoryChoices,
    NotificationPriorityChoices,
)
from .models import Announcement, Feedback, Notification, ParentTeacherMeeting

User = get_user_model()


# FEEDBACK SIGNALS
@receiver(pre_save, sender=Feedback)
def feedback_pre_save(sender, instance, **kwargs):
    """
    Capture previous values for comparison
    """
    if instance.pk:
        try:
            instance._old = Feedback.objects.get(pk=instance.pk)
        except Feedback.DoesNotExist:
            instance._old = None


@receiver(post_save, sender=Feedback)
def feedback_post_save(sender, instance, created, **kwargs):
    """
    Handle feedback notifications
    """
    #  Assigned-to changed
    if not created and instance._old:
        if instance._old.assigned_to != instance.assigned_to and instance.assigned_to:
            Notification.objects.create(
                user=instance.assigned_to,
                sender=instance.submitted_by,
                notification_category=NotificationCategoryChoices.SYSTEM,
                priority=(
                    NotificationPriorityChoices.HIGH
                    if instance.priority in [FeedbackPriorityChoices.HIGH, FeedbackPriorityChoices.URGENT]
                    else NotificationPriorityChoices.NORMAL
                ),
                title=f"New Feedback Assigned",
                message=f"You have been assigned feedback: {instance.title}",
                action_url=f"/feedback/{instance.id}/",
            )
    #  Feedback resolved
    if instance.feedback_status == FeedbackStatusChoices.RESOLVED and instance.resolved_by:
        Notification.objects.create(
            user=instance.submitted_by,
            sender=instance.resolved_by,
            notification_category=NotificationCategoryChoices.SYSTEM,
            priority=NotificationPriorityChoices.NORMAL,
            title="Feedback Resolved",
            message=f"Your feedback '{instance.title}' has been resolved.",
            action_url=f"/feedback/{instance.id}/",
        )


# ANNOUNCEMENT SIGNALS
@receiver(pre_save, sender=Announcement)
def announcement_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old = Announcement.objects.get(pk=instance.pk)
        except Announcement.DoesNotExist:
            instance._old = None


@receiver(post_save, sender=Announcement)
def announcement_post_save(sender, instance, created, **kwargs):
    """
    Notify ONLY when status transitions to PUBLISHED
    """
    if instance.announcement_status == AnnouncementStatusChoices.PUBLISHED:
        if created or (
            instance._old
            and instance._old.announcement_status != AnnouncementStatusChoices.PUBLISHED
        ):
            Notification.objects.create(
                user=instance.created_by,
                sender=instance.created_by,
                notification_category=NotificationCategoryChoices.EVENT,
                priority=instance.priority,
                title="Announcement Published",
                message=f"Your announcement '{instance.title}' is now live.",
                action_url=f"/announcements/{instance.id}/",
            )


# MEETING SIGNALS
@receiver(post_save, sender=ParentTeacherMeeting)
def send_meeting_invites(sender, instance, created, **kwargs):
    """
    Send meeting invitations ON CREATION ONLY
    """
    if not created or not instance.invitees:
        return

    for user_id in instance.invitees:
        try:
            user = User.objects.get(id=user_id)
            Notification.objects.create(
                user=user,
                sender=instance.organizer,
                notification_category=NotificationCategoryChoices.EVENT,
                priority=NotificationPriorityChoices.NORMAL,
                title="Meeting Invitation",
                message=f"You are invited to '{instance.title}' on {instance.date}.",
                action_url=f"/meetings/{instance.id}/",
            )
        except User.DoesNotExist:
            continue


@receiver(post_save, sender=Feedback)
def log_feedback_resolution(sender, instance, created, **kwargs):
    if not created and instance.feedback_status == FeedbackStatusChoices.RESOLVED:
            create_audit_log(
                actor=instance.resolved_by,
                action=AuditActionChoices.UPDATE,
                model_name="Feedback",
                record_id=instance.id,
                school=(
                    instance.related_to_student.school
                    if instance.related_to_student_id
                    else getattr(instance, "school", None)
                ),
                reason="Feedback resolution recorded",
                new_value=f"Resolved: {instance.title}",
            )
