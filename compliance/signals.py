from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.utils import timezone
from .models import AuditLog, DataExportLog, SystemHealth
import hashlib


def create_audit_log( user,
    action_type,  model_name,
    record_id=None, field_changed='',
    old_value='', new_value='',
    reason='',approval_required=False,school=None,
    user_ip=None,user_device=''
):
    if not user or not user.is_authenticated:
        return
    # Determine user role
    if hasattr(user, 'staffprofile'):
        user_role = 'Staff'
        school = school or user.staffprofile.school
    elif hasattr(user, 'student'):
        user_role = 'Student'
        school = school or user.student.school
    else:
        user_role = 'System'

    # Create checksum
    data_string = f"{user.id}{action_type}{model_name}{record_id}{timezone.now()}"
    checksum = hashlib.sha256(data_string.encode()).hexdigest()

    AuditLog.objects.create(
        user=user,
        user_role=user_role,
        user_ip=user_ip,
        user_device=user_device[:500],
        action_type=action_type,
        model_name=model_name,
        record_id=record_id,
        field_changed=field_changed,
        old_value=str(old_value)[:500],
        new_value=str(new_value)[:500],
        reason=reason[:200],
        approval_required=approval_required,
        school=school,
        checksum=checksum
    )


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log user login."""
    create_audit_log(
        user=user,
        action_type=AuditLog.LOGIN,
        model_name='User',
        record_id=user.id,
        reason='User logged in',
        user_ip=request.META.get('REMOTE_ADDR'),
        user_device=request.META.get('HTTP_USER_AGENT', '')
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log user logout."""
    if user and user.is_authenticated:
        create_audit_log(
            user=user,
            action_type=AuditLog.LOGOUT,
            model_name='User',
            record_id=user.id,
            reason='User logged out'
        )


@receiver(post_save, sender=DataExportLog)
def log_data_export(sender, instance, created, **kwargs):
    """Log data export creation."""
    if created:
        create_audit_log(
            user=instance.exported_by,
            action_type=AuditLog.EXPORT,
            model_name='DataExportLog',
            record_id=instance.id,
            reason=f"Exported {instance.export_type} data in {instance.format} format"
        )


@receiver(post_save, sender=SystemHealth)
def check_system_health_status(sender, instance, **kwargs):
    """Check system health status and create alerts if needed."""
    
    # Check for critical issues
    critical_issues = []
    
    if instance.backup_status == SystemHealth.FAILED:
        critical_issues.append('backup_failed')
    
    if instance.sync_status == SystemHealth.SYNC_FAILED:
        critical_issues.append('sync_failed')
    
    if instance.performance_score < 70:
        critical_issues.append('low_performance')
    
    if instance.storage_available < 1.0:  # Less than 1GB available
        critical_issues.append('storage_critical')
