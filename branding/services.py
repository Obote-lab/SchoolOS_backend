"""
BrandingService — single entry point for resolve + mutate.

All writes must go through this service so audit + change-log stay consistent.
"""

from __future__ import annotations

import copy
from typing import Any, Optional
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.audit import create_audit_log
from core.choices.identity import AuditActionChoices

from .models import (
    BrandingChangeLog,
    PlatformModeChoices,
    SchoolBranding,
    SystemBranding,
    ThemePreset,
    _default_colour_tokens,
    _default_typography,
)


def _merge_tokens(base: dict, overlay: dict | None) -> dict:
    """Shallow merge; overlay wins for non-empty values."""
    result = copy.deepcopy(base or {})
    if not overlay:
        return result
    for key, value in overlay.items():
        if value is not None and value != "":
            result[key] = value
    return result


def _absolute_url(request, file_field) -> str | None:
    if not file_field:
        return None
    try:
        url = file_field.url
    except ValueError:
        return None
    if request is not None:
        return request.build_absolute_uri(url)
    return url


class BrandingService:
    """Resolve and mutate branding. Prefer this over direct model access."""

    # Resolve (what every client consumes)

    @classmethod
    def get_resolved(cls,*,school=None,request=None) -> dict[str, Any]:
        """
        Build the flat payload applied by web / mobile / login / PDFs.

        Inheritance:
            system tokens → school tokens (if present and not suppressed)
            system logos  → school logos (if present and not suppressed)
            mode overrides applied last when mode != normal
        """
        system = SystemBranding.get_solo()
        school_branding: SchoolBranding | None = None

        if school is not None:
            school_branding = getattr(school, "branding", None)
            if school_branding is None:
                try:
                    school_branding = SchoolBranding.objects.filter(school=school).first()
                except Exception:
                    school_branding = None

        mode = system.mode
        in_special_mode = mode != PlatformModeChoices.NORMAL

        #  Logos
        system_logo = {
            "light": _absolute_url(request, system.logo_light),
            "dark": _absolute_url(request, system.logo_dark),
            "square": _absolute_url(request, system.logo_square),
            "favicon": _absolute_url(request, system.favicon),
        }

        # Mode can temporarily replace system logo
        if in_special_mode and system.mode_logo_light:
            system_logo["light"] = _absolute_url(request, system.mode_logo_light)
            if system.mode_logo_dark:
                system_logo["dark"] = _absolute_url(request, system.mode_logo_dark)

        school_logo = None
        use_school_visuals = True
        if school_branding:
            if school_branding.use_system_theme:
                use_school_visuals = False
            if in_special_mode and school_branding.suppress_in_exam_mode:
                use_school_visuals = False

            if use_school_visuals:
                school_logo = {
                    "light": _absolute_url(request, school_branding.logo_light),
                    "dark": _absolute_url(request, school_branding.logo_dark),
                    "square": _absolute_url(request, school_branding.logo_square),
                    "favicon": _absolute_url(request, school_branding.favicon),
                }
                if not any(school_logo.values()):
                    school_logo = None

        #  Colour tokens
        tokens = _merge_tokens(_default_colour_tokens(), system.colour_tokens)
        if in_special_mode and system.mode_colour_overrides:
            tokens = _merge_tokens(tokens, system.mode_colour_overrides)

        if school_branding and use_school_visuals and not school_branding.use_system_theme:
            tokens = _merge_tokens(tokens, school_branding.colour_tokens)

        #  Typography / density / radius
        typography = _merge_tokens(_default_typography(), system.typography)
        if school_branding and use_school_visuals and school_branding.typography:
            typography = _merge_tokens(typography, school_branding.typography)

        density = system.density
        if school_branding and use_school_visuals and school_branding.density:
            density = school_branding.density

        border_radius = system.border_radius_px
        if (
            school_branding
            and use_school_visuals
            and school_branding.border_radius_px is not None
        ):
            border_radius = school_branding.border_radius_px

        #  Banner
        banner = None
        if system.banner_enabled and system.banner_text:
            banner = {
                "text": system.banner_text,
                "level": system.banner_level,
                "dismissible": system.banner_dismissible,
                "url": system.banner_url or None,
                "source": "system",
            }
        elif (
            school_branding
            and school_branding.local_banner_enabled
            and school_branding.local_banner_text
        ):
            banner = {
                "text": school_branding.local_banner_text,
                "level": school_branding.local_banner_level,
                "dismissible": True,
                "url": None,
                "source": "school",
            }

        mode_label = system.mode_label or (dict(PlatformModeChoices.choices).get(mode, mode))

        version_stamp = max(
            system.updated_at or timezone.now(),
            (school_branding.updated_at if school_branding else None) or timezone.now(),
        )

        return {
            "version": version_stamp.isoformat(),
            "system_version": system.version,
            "school_version": school_branding.version if school_branding else None,
            "mode": mode,
            "mode_label": mode_label,
            "system_logo": system_logo,
            "school_logo": school_logo,
            "tokens": tokens,
            "typography": typography,
            "density": density,
            "border_radius_px": border_radius,
            "banner": banner,
            "login": {
                "background": _absolute_url(request, system.login_background),
                "welcome_message": system.login_welcome_message
                or (school_branding.welcome_message if school_branding else ""),
                "support_email": system.support_email,
                "support_phone": system.support_phone,
            },
            "school_id": str(school.id) if school else None,
            "school_name": getattr(school, "school_name", None) if school else None,
        }

    # Mutate — System

    @classmethod
    @transaction.atomic
    def update_system(cls,*,actor,data: dict,files: dict | None = None,request=None,) -> SystemBranding:
        if not cls._actor_is_root(actor):
            raise PermissionDenied("Only platform administrators may change system branding.")

        system = SystemBranding.get_solo()
        before = cls._system_snapshot(system)

        for field in (
            "mode",
            "mode_label",
            "colour_tokens",
            "mode_colour_overrides",
            "typography",
            "density",
            "border_radius_px",
            "banner_enabled",
            "banner_text",
            "banner_level",
            "banner_dismissible",
            "banner_url",
            "login_welcome_message",
            "support_email",
            "support_phone",
        ):
            if field in data:
                setattr(system, field, data[field])

        files = files or {}
        for field in (
            "logo_light",
            "logo_dark",
            "logo_square",
            "favicon",
            "mode_logo_light",
            "mode_logo_dark",
            "login_background",
        ):
            if field in files and files[field] is not None:
                setattr(system, field, files[field])

        system.updated_by = actor
        system.full_clean()
        system.save()

        after = cls._system_snapshot(system)
        cls._log_change(
            scope="system",
            school=None,
            actor=actor,
            action="update_system",
            summary=f"System branding updated (mode={system.mode})",
            before=before,
            after=after,
        )
        create_audit_log(
            actor=actor,
            action=AuditActionChoices.UPDATE,
            model_name="SystemBranding",
            record_id=system.id,
            school=None,
            reason=f"System branding v{system.version} (mode={system.mode})",
            new_value=system.mode,
            request=request,
        )
        return system

    # Mutate — School

    @classmethod
    @transaction.atomic
    def update_school(cls,*, actor, school,data: dict,files: dict | None = None,request=None,) -> SchoolBranding:
        if not cls._actor_can_edit_school(actor, school):
            raise PermissionDenied("You may not change branding for this school.")

        branding, _ = SchoolBranding.objects.select_for_update().get_or_create(school=school,defaults={"updated_by": actor},)
        before = cls._school_snapshot(branding)

        for field in (
            "colour_tokens",
            "typography",
            "density",
            "border_radius_px",
            "welcome_message",
            "local_banner_enabled",
            "local_banner_text",
            "local_banner_level",
            "use_system_theme",
            "suppress_in_exam_mode",
        ):
            if field in data:
                setattr(branding, field, data[field])

        files = files or {}
        for field in ("logo_light", "logo_dark", "logo_square", "favicon"):
            if field in files and files[field] is not None:
                setattr(branding, field, files[field])

        branding.updated_by = actor
        branding.full_clean()
        branding.save()

        after = cls._school_snapshot(branding)
        cls._log_change(
            scope="school",
            school=school,
            actor=actor,
            action="update_school",
            summary=f"School branding updated for {getattr(school, 'school_name', school.id)}",
            before=before,
            after=after,
        )
        create_audit_log(
            actor=actor,
            action=AuditActionChoices.UPDATE,
            model_name="SchoolBranding",
            record_id=branding.id,
            school=school,
            reason=f"School branding v{branding.version}",
            request=request,
        )
        return branding

    @classmethod
    @transaction.atomic
    def apply_preset_to_school(cls,*,actor, school, preset: ThemePreset, request=None,) -> SchoolBranding:
        if not preset.is_active:
            raise ValidationError("Preset is not active.")
        if not preset.is_public and not cls._actor_is_root(actor):
            raise PermissionDenied("This preset is restricted.")

        return cls.update_school(
            actor=actor,
            school=school,
            data={"colour_tokens": preset.colour_tokens},
            request=request,
        )

    # Helpers
    @staticmethod
    def _actor_is_root(actor) -> bool:
        if not actor or not getattr(actor, "is_authenticated", False):
            return False
        if getattr(actor, "is_superuser", False):
            return True
        try:
            return actor.user_roles.filter(
                is_active=True,
                role__name__in=["System Root", "Platform Admin", "Super Admin"],
                role__access_level__in=["national"],  # optional extra safety
            ).exists()
        except Exception:
            return False

    @staticmethod
    def _actor_can_edit_school(actor, school) -> bool:
        if BrandingService._actor_is_root(actor):
            return True
        if not actor or not school:
            return False
        try:
            return actor.user_roles.filter(
                is_active=True,
                school=school,
                # role__name__in=[
                #     "Principal",
                #     "Head Teacher",
                #     "Head of School",
                # ],
                role__name__in=[
                        "Principal",
                    ],
            ).exists()
        except Exception:
            return False

    @staticmethod
    def _system_snapshot(obj: SystemBranding) -> dict:
        return {
            "mode": obj.mode,
            "version": obj.version,
            "colour_tokens": obj.colour_tokens,
            "banner_enabled": obj.banner_enabled,
            "banner_text": obj.banner_text,
        }

    @staticmethod
    def _school_snapshot(obj: SchoolBranding) -> dict:
        return {
            "version": obj.version,
            "colour_tokens": obj.colour_tokens,
            "use_system_theme": obj.use_system_theme,
            "local_banner_enabled": obj.local_banner_enabled,
        }

    @staticmethod
    def _log_change(**kwargs):
        BrandingChangeLog.objects.create(**kwargs)