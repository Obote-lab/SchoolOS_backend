"""
Compliance-domain signals.

Audit writes go only through core.audit.create_audit_log → SystemAuditEvent.
"""

import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.audit import create_audit_log
from core.choices.compliance import HealthStatusChoices, SyncStatusChoices
from core.choices.identity import AuditActionChoices

from .models import DataExportLog, SystemHealth

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Optional: login/logout (remove if accounts.signals already handles these)
# ---------------------------------------------------------------------------
@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    create_audit_log(
        actor=user,
        action=AuditActionChoices.LOGIN,
        model_name="CustomUser",
        record_id=user.pk,
        reason="User logged in",
        request=request,
        school=getattr(user, "school", None),
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if not user or not getattr(user, "is_authenticated", False):
        return
    create_audit_log(
        actor=user,
        action=AuditActionChoices.LOGOUT,
        model_name="CustomUser",
        record_id=user.pk,
        reason="User logged out",
        request=request,
        school=getattr(user, "school", None),
    )


# ---------------------------------------------------------------------------
# Data export trail
# ---------------------------------------------------------------------------
@receiver(post_save, sender=DataExportLog)
def log_data_export(sender, instance, created, **kwargs):
    if not created:
        return
    # Use EXPORT if defined on AuditActionChoices; otherwise CREATE
    action = getattr(AuditActionChoices, "EXPORT", None) or AuditActionChoices.CREATE
    create_audit_log(
        actor=instance.exported_by,
        action=action,
        model_name="DataExportLog",
        record_id=instance.pk,
        reason=f"Exported {instance.export_type} data in {instance.format} format",
        school=getattr(instance, "school", None),
        new_value=str(instance.export_type),
    )


# ---------------------------------------------------------------------------
# System health — flag critical issues without recursive save
# ---------------------------------------------------------------------------
@receiver(post_save, sender=SystemHealth)
def check_system_health_status(sender, instance, created, **kwargs):
    critical_issues = []

    if instance.backup_status == HealthStatusChoices.FAILED:
        critical_issues.append("backup_failed")
    if instance.sync_status == SyncStatusChoices.FAILED:
        critical_issues.append("sync_failed")
    if instance.performance_score is not None and instance.performance_score < 70:
        critical_issues.append("low_performance")
    if instance.storage_available is not None and instance.storage_available < 1.0:
        critical_issues.append("storage_critical")

    if not critical_issues:
        return

    existing = list(instance.issues_detected or [])
    changed = False
    for issue in critical_issues:
        if issue not in existing:
            existing.append(issue)
            changed = True

    if changed:
        SystemHealth.objects.filter(pk=instance.pk).update(issues_detected=existing)