"""
Single audit entry-point for the whole platform.

Usage (any app):
    from core.audit import create_audit_log
    from core.choices.identity import AuditActionChoices

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

Rules:
- Application code must ONLY write audits through this function.
- Never call SystemAuditEvent.objects.create / AuditLog.objects.create elsewhere.
- Failures are logged and swallowed so business transactions are not rolled back.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Optional
from uuid import UUID

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

logger = logging.getLogger(__name__)


def _compute_checksum(payload: dict) -> str:
    """Simple tamper-evident checksum (not cryptographic proof of history)."""
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


def _extract_session_id(request, session_id: str = "") -> str:
    if session_id:
        return session_id
    if request is None:
        return ""
    try:
        return getattr(request.session, "session_key", None) or ""
    except Exception:
        return ""


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def create_audit_log(
    *,
    actor=None,
    action: str,
    model_name: str = "",
    record_id: UUID | str | int | None = None,
    content_object=None,
    school=None,
    reason: str = "",
    field_changed: str = "",
    old_value: Any = "",
    new_value: Any = "",
    user_role: str = "",
    request=None,
    session_id: str = "",
    approval_required: bool = False,
    approved_by=None,
    location: str = "",
    extra: dict | None = None,
):
    """
    Create one SystemAuditEvent.

    - record_id: always stored as string (works for UUID and integer PKs).
    - object_id: only set when the id is a real UUID (matches UUIDField on the model).
    - content_object: optional; fills content_type, record_id, and model_name when possible.
    """
    # Late import avoids circular imports at startup
    from compliance.models import SystemAuditEvent

    # Resolve role name if not supplied
    if actor is not None and not user_role:
        try:
            highest = actor.get_highest_tier()
            user_role = highest.name if highest else ""
        except Exception:
            user_role = ""

    # Resolve school from actor if missing
    if school is None and actor is not None:
        school = getattr(actor, "school", None)

    content_type = None
    object_id = None  # UUID only, or None
    record_id_str = ""

    if content_object is not None:
        try:
            content_type = ContentType.objects.get_for_model(
                content_object, for_concrete_model=False
            )
        except Exception:
            content_type = None
        pk = getattr(content_object, "pk", None)
        if pk is not None:
            record_id_str = str(pk)
            if isinstance(pk, UUID):
                object_id = pk
        if not model_name:
            model_name = content_object.__class__.__name__
    elif record_id is not None:
        record_id_str = str(record_id)
        if isinstance(record_id, UUID):
            object_id = record_id

    # Optional: fold unstructured extra into reason (avoid silent data loss)
    if extra:
        try:
            extra_bits = "; ".join(f"{k}={v}" for k, v in extra.items())
            reason = f"{reason} | {extra_bits}".strip(" |") if reason else extra_bits
        except Exception:
            pass

    payload_for_checksum = {
        "action": action,
        "model_name": model_name or "",
        "record_id": record_id_str,
        "old_value": _to_str(old_value),
        "new_value": _to_str(new_value),
        "actor_id": str(getattr(actor, "pk", "") or ""),
        "timestamp": timezone.now().isoformat(),
    }

    try:
        event = SystemAuditEvent(
            user=actor if getattr(actor, "pk", None) else None,
            user_role=user_role or "",
            user_ip=_extract_ip(request),
            user_device=_extract_device(request),
            action_type=action,
            content_type=content_type,
            object_id=object_id,
            model_name=model_name or "",
            record_id=record_id_str,
            field_changed=field_changed or "",
            old_value=_to_str(old_value),
            new_value=_to_str(new_value),
            reason=reason or "",
            approval_required=approval_required,
            approved_by=approved_by,
            school=school,
            location=location or "",
            session_id=_extract_session_id(request, session_id),
            checksum=_compute_checksum(payload_for_checksum),
        )
        event.save()
        return event
    except Exception:
        logger.exception(
            "Failed to write SystemAuditEvent for action=%s model=%s record_id=%s",
            action,
            model_name,
            record_id_str,
        )
        return None