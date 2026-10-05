import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.audit import create_audit_log
from core.choices.identity import AuditActionChoices

from .models import Dormitory, DormitoryInspection, RoomAllocation

logger = logging.getLogger(__name__)


def _recount_occupancy(dormitory_id) -> None:
    if not dormitory_id:
        return
    count = RoomAllocation.objects.filter(
        dormitory_id=dormitory_id,
        is_active=True,
    ).count()
    Dormitory.objects.filter(pk=dormitory_id).update(current_occupancy=count)


@receiver(post_save, sender=RoomAllocation)
def sync_dorm_occupancy_on_allocation_save(sender, instance, **kwargs):
    _recount_occupancy(instance.dormitory_id)


@receiver(post_delete, sender=RoomAllocation)
def sync_dorm_occupancy_on_allocation_delete(sender, instance, **kwargs):
    _recount_occupancy(instance.dormitory_id)


@receiver(post_save, sender=DormitoryInspection)
def log_inspection_and_alert(sender, instance, created, **kwargs):
    if not created:
        return

    school = instance.dormitory.school if instance.dormitory_id else None
    create_audit_log(
        actor=instance.inspected_by,
        action=AuditActionChoices.CREATE,
        model_name="DormitoryInspection",
        record_id=instance.pk,
        school=school,
        reason=(
            f"New inspection in {instance.dormitory.name} "
            f"– avg {instance.average_score}"
        ),
        new_value=str(instance.average_score),
    )

    if instance.average_score < 5:
        logger.warning(
            "Low inspection score (%.1f) in %s",
            instance.average_score,
            instance.dormitory.name,
        )