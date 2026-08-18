"""
Single audit entry-point for the whole platform.

Usage (any app):
    from core.audit import create_audit_log

    create_audit_log(
        actor=request.user,
        action=AuditActionChoices.CREATE,
        model_name="CustomUser",
        record_id=user.id,
        school=school,
        reason="Created teacher",
        new_value=user.login_id,
        request=request,
    )
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Optional
from uuid import UUID
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from compliance.models import SystemAuditEvent

logger = logging.getLogger(__name__)


def _compute_checksum(payload: dict) -> str:
    """Simple tamper-evident checksum. Not cryptographic proof."""
    raw = "|".join(str(payload.get(k, "")) for k in sorted(payload.keys()))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_ip(request) -> Optional[str]:
    if request is None:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _extract_device(request) -> str:
    if request is None:
        return ""
    return (request.META.get("HTTP_USER_AGENT") or "")[:500]


def create_audit_log(
    *,actor=None,action: str,model_name: str = "", record_id: UUID | str | None = None,
    content_object=None,school=None,reason: str = "", field_changed: str = "",old_value: Any = "",
    new_value: Any = "",user_role: str = "",request=None,session_id: str = "",
    approval_required: bool = False,approved_by=None,location: str = "",extra: dict | None = None,) -> "SystemAuditEvent":
    """
    Create one SystemAuditEvent. This is the ONLY function that should
    write audit rows from application code.
    """

    # Resolve role name if not supplied
    if actor and not user_role:
        try:
            highest = actor.get_highest_tier()
            user_role = highest.name if highest else ""
        except Exception:
            user_role = ""

    # Resolve school from actor if missing
    if school is None and actor is not None:
        school = getattr(actor, "school", None)

    # GFK helpers
    content_type = None
    object_id = None
    if content_object is not None:
        content_type = ContentType.objects.get_for_model(content_object)
        object_id = getattr(content_object, "pk", None)
        if not model_name:
            model_name = content_object.__class__.__name__
    elif record_id is not None:
        object_id = record_id if isinstance(record_id, UUID) else str(record_id)

    # Normalise values to strings for storage
    def _to_str(v):
        if v is None:
            return ""
        return str(v)

    payload_for_checksum = {
        "action": action,
        "model_name": model_name,
        "object_id": str(object_id) if object_id else "",
        "old_value": _to_str(old_value),
        "new_value": _to_str(new_value),
        "actor_id": str(getattr(actor, "pk", "")),
        "timestamp": timezone.now().isoformat(),
    }

    event = SystemAuditEvent(
        user=actor,
        user_role=user_role or "",
        user_ip=_extract_ip(request),
        user_device=_extract_device(request),
        action_type=action,
        content_type=content_type,
        object_id=object_id,
        model_name=model_name or "",
        field_changed=field_changed or "",
        old_value=_to_str(old_value),
        new_value=_to_str(new_value),
        reason=reason or "",
        approval_required=approval_required,
        approved_by=approved_by,
        school=school,
        location=location or "",
        session_id=session_id or "",
        checksum=_compute_checksum(payload_for_checksum),
    )

    # Prefer non-atomic save so audit never rolls back the business transaction
    # if the caller is already inside atomic. Callers who need strict coupling
    # can wrap the call themselves.
    try:
        event.save()
    except Exception:
        logger.exception("Failed to write SystemAuditEvent for %s on %s", action, model_name)
        # Do not raise – business operation should still succeed
        return event

    return event