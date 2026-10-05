"""
Branding signals — keep light.
Heavy side-effects (cache invalidation, CDN purge) can be added later
via DomainEvent or Celery when those paths exist.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import SchoolBranding, SystemBranding

logger = logging.getLogger(__name__)


@receiver(post_save, sender=SystemBranding)
def system_branding_changed(sender, instance: SystemBranding, **kwargs):
    logger.info(
        "SystemBranding updated: v%s mode=%s",
        instance.version,
        instance.mode,
    )


@receiver(post_save, sender=SchoolBranding)
def school_branding_changed(sender, instance: SchoolBranding, **kwargs):
    logger.info(
        "SchoolBranding updated: school=%s v%s",
        instance.school_id,
        instance.version,
    )