import hashlib

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from core.choices.identity import AuditActionChoices
from .models import SystemAuditEvent, DataExportLog, SystemHealth
from core.choices.compliance import (
    HealthStatusChoices,
    SyncStatusChoices,
)
from core.choices.identity import AuditActionChoices


def create_audit_log(user, action_type, model_name, record_id=None, field_changed="", old_value="",
    new_value="", reason="", approval_required=False, school=None, user_ip=None,user_device=""):
    if not user or not user.is_authenticated:
        return

    # Determine user role and school
    if hasattr(user, "staff_profile"):
        user_role = "Staff"
        school = school or getattr(user.staff_profile, "school", None)
    elif hasattr(user, "student_profile"):
        user_role = "Student"
        school = school or getattr(user.student_profile, "school", None)
    else:
        user_role = "System"

    # Create checksum
    data_string = f"{user.id}{action_type}{model_name}{record_id}{timezone.now()}"
    checksum = hashlib.sha256(data_string.encode()).hexdigest()

    SystemAuditEvent.objects.create( user=user,user_role=user_role,user_ip=user_ip,user_device=user_device[:500],
        action_type=action_type,model_name=model_name,object_id=record_id,field_changed=field_changed,old_value=str(old_value)[:500],
        new_value=str(new_value)[:500],reason=reason[:200],approval_required=approval_required,school=school,checksum=checksum,)


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    create_audit_log(
        user=user,
        action_type=AuditActionChoices.LOGIN,
        model_name="User",
        record_id=str(user.id),
        reason="User logged in",
        user_ip=request.META.get("REMOTE_ADDR"),
        user_device=request.META.get("HTTP_USER_AGENT", ""),
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user and user.is_authenticated:
        create_audit_log(
            user=user,
            action_type=AuditActionChoices.LOGOUT,
            model_name="User",
            record_id=str(user.id),
            reason="User logged out",
        )


@receiver(post_save, sender=DataExportLog)
def log_data_export(sender, instance, created, **kwargs):
    if created:
        create_audit_log(
            user=instance.exported_by,
            action_type=AuditActionChoices.EXPORT,
            model_name="DataExportLog",
            record_id=str(instance.id),
            reason=f"Exported {instance.export_type} data in {instance.format} format",
        )


@receiver(post_save, sender=SystemHealth)
def check_system_health_status(sender, instance, created, **kwargs):
    """Check system health and log critical issues"""

    critical_issues = []

    if instance.backup_status == HealthStatusChoices.FAILED:
        critical_issues.append("backup_failed")

    if instance.sync_status == SyncStatusChoices.FAILED:
        critical_issues.append("sync_failed")

    if instance.performance_score < 70:
        critical_issues.append("low_performance")

    if instance.storage_available < 1.0:
        critical_issues.append("storage_critical")

    # You can extend this: create alerts, send notifications, etc.
    if critical_issues:
        # Optional: Update the instance or create a separate Alert model
        if not instance.issues_detected:
            instance.issues_detected = []

        for issue in critical_issues:
            if issue not in instance.issues_detected:
                instance.issues_detected.append(issue)

        # Avoid recursion by using update() instead of save()
        SystemHealth.objects.filter(id=instance.id).update(
            issues_detected=instance.issues_detected
        )
