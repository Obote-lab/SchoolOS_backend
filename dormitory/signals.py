import logging
from django.db.models import F
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from accounts.models import AuditLog
from compliance.models import SystemAuditEvent
from .models import Dormitory, DormitoryInspection, RoomAllocation
from compliance.models import SystemAuditEvent
from core.choices.compliance import AuditActionTypeChoices

logger = logging.getLogger(__name__)


@receiver(post_save, sender=RoomAllocation)
def sync_dorm_occupancy_on_allocation_save(sender, instance, created, **kwargs):
    """Keep dormitory.current_occupancy accurate."""
    dorm = instance.dormitory
    active_count = RoomAllocation.objects.filter(dormitory=dorm, is_active=True).count()

    if dorm.current_occupancy != active_count:
        dorm.current_occupancy = active_count
        dorm.save(update_fields=["current_occupancy"])


@receiver(post_delete, sender=RoomAllocation)
def decrease_occupancy_on_allocation_delete(sender, instance, **kwargs):
    """Reduce count when allocation deleted."""
    if instance.is_active:
        dorm = instance.dormitory
        dorm.current_occupancy = F("current_occupancy") - 1
        dorm.save(update_fields=["current_occupancy"])


@receiver(post_save, sender=DormitoryInspection)
def log_inspection_and_alert(sender, instance, created, **kwargs):
    """Audit + alert on low scores."""
    if created:
        AuditLog.objects.create(
            user=instance.inspected_by,
            action_type="CREATE",
            model_name="DormitoryInspection",
            record_id=str(instance.id),
            reason=f"New inspection in {instance.dormitory.name} – avg {instance.average_score}",
            school=instance.dormitory.school,
        )

        if instance.average_score < 5:
            logger.info(
                f"[ALERT] Low inspection score ({instance.average_score}) in {instance.dormitory.name}"
            )


@receiver(post_delete, sender=RoomAllocation)
def sync_dorm_occupancy_on_allocation_delete(sender, instance, **kwargs):
    dorm = instance.dormitory
    active_count = RoomAllocation.objects.filter(
        dormitory=dorm, is_active=True
    ).count()
    Dormitory.objects.filter(pk=dorm.pk).update(current_occupancy=active_count)



SystemAuditEvent.objects.create(
    user=instance.inspected_by,
    action_type=AuditActionTypeChoices.CREATE,
    model_name="DormitoryInspection",
    object_id=instance.id,
    reason=f"New inspection in {instance.dormitory.name} – avg {instance.average_score}",
    school=instance.dormitory.school,
)