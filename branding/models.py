
"""
Branding domain models for SchoolOS.

Hierarchy (authority):
    SystemBranding  →  optional CountyBranding (future)  →  SchoolBranding

Clients never invent colours or logos. They call the resolved endpoint
and apply the flat token payload.
"""

from __future__ import annotations

import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import choices, timezone
from django.utils.translation import gettext_lazy as _


# Choices (kept local so branding stays self-contained; can move to core later)
class PlatformModeChoices(models.TextChoices):
    NORMAL = "normal", _("Normal operations")
    EXAM_SEASON = "exam_season", _("National / exam season")
    MAINTENANCE = "maintenance", _("Maintenance window")
    CAMPAIGN = "campaign", _("National campaign / awareness")
    EMERGENCY = "emergency", _("Emergency / crisis mode")
    NATIONAL_HOLIDAY = "national_holiday", _("National holiday")
    OPENING_SEASON = "opening_season", _("opening season")
    HALF_TERM = "half_term", _("Half term")
    CLOSING_SEASON = "closing_season", _("closing_ eason")
    GAMES_SEASON = "games_season", _("Games season")
    MUSIC_FESTIVAL = "Music_festival", _("Music festival")



class DensityChoices(models.TextChoices):
    COMPACT = "compact", _("Compact")
    COMFORTABLE = "comfortable", _("Comfortable")
    SPACIOUS = "spacious", _("Spacious")


class BannerLevelChoices(models.TextChoices):
    INFO = "info", _("Info")
    SUCCESS = "success", _("Success")
    WARNING = "warning", _("Warning")
    DANGER = "danger", _("Danger")


def _logo_upload_to(instance, filename: str) -> str:
    prefix = "system" if isinstance(instance, SystemBranding) else f"schools/{getattr(instance, 'school_id', 'unknown')}"
    return f"branding/{prefix}/logos/{timezone.now():%Y/%m}/{filename}"


def _default_colour_tokens() -> dict:
    """Safe default palette (accessible blues). Schools inherit these when null."""
    return {
        "primary": "#0B5FFF",
        "primary_foreground": "#FFFFFF",
        "secondary": "#1E293B",
        "secondary_foreground": "#F8FAFC",
        "accent": "#06B6D4",
        "accent_foreground": "#FFFFFF",
        "success": "#16A34A",
        "warning": "#D97706",
        "danger": "#DC2626",
        "background": "#F8FAFC",
        "surface": "#FFFFFF",
        "text_primary": "#0F172A",
        "text_muted": "#64748B",
        "border": "#E2E8F0",
        "ring": "#0B5FFF",
    }


def _default_typography() -> dict:
    return {
        "font_family_sans": "Inter, system-ui, -apple-system, sans-serif",
        "font_family_display": "Inter, system-ui, sans-serif",
        "base_size_px": 16,
        "scale_ratio": 1.25,
    }


#
# System (platform-wide) branding — Root only
#

class SystemBranding(models.Model):
    """
    Singleton-style platform branding.
    Only System Root / platform admins may mutate this.
    Soft-versioned via `version` + `updated_at` for cache busting.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Logos
    logo_light = models.ImageField(upload_to=_logo_upload_to,blank=True,null=True,validators=[FileExtensionValidator(["png", "jpg", "jpeg", "svg", "webp"])],help_text=_("Primary logo for light backgrounds"))
    logo_dark = models.ImageField(upload_to=_logo_upload_to,blank=True,null=True,validators=[FileExtensionValidator(["png", "jpg", "jpeg", "svg", "webp"])], help_text=_("Logo for dark backgrounds / dark mode"), )
    logo_square = models.ImageField(upload_to=_logo_upload_to,blank=True,null=True, validators=[FileExtensionValidator(["png", "jpg", "jpeg", "svg", "webp"])],help_text=_("Square mark / app icon source"),)
    favicon = models.ImageField(upload_to=_logo_upload_to, blank=True,null=True,validators=[FileExtensionValidator(["png", "ico", "svg"])],help_text=_("Favicon"),)

    # Mode (exam season, maintenance, etc.)
    mode = models.CharField(max_length=20,choices=PlatformModeChoices.choices,default=PlatformModeChoices.NORMAL,db_index=True,)
    mode_label = models.CharField( max_length=120,blank=True,help_text=_("Optional human label shown in banner during special modes"),)
    mode_logo_light = models.ImageField( upload_to=_logo_upload_to,blank=True,null=True,help_text=_("Temporary logo override while mode is active (e.g. exam season),"))
    mode_logo_dark = models.ImageField( upload_to=_logo_upload_to,blank=True,null=True,)

    # Colour & layout tokens
    colour_tokens = models.JSONField(default=_default_colour_tokens,blank=True,help_text=_("CSS-variable style colour map"),)
    mode_colour_overrides = models.JSONField( default=dict, blank=True, help_text=_("Token overrides applied only while a special mode is active"),)
    typography = models.JSONField(default=_default_typography, blank=True)
    density = models.CharField( max_length=20,choices=DensityChoices.choices, default=DensityChoices.COMFORTABLE,)
    border_radius_px = models.PositiveSmallIntegerField(default=8)

    # Global banner / notice
    banner_enabled = models.BooleanField(default=False)
    banner_text = models.CharField(max_length=500, blank=True)
    banner_level = models.CharField(max_length=20, choices=BannerLevelChoices.choices,default=BannerLevelChoices.INFO,)
    banner_dismissible = models.BooleanField(default=True)
    banner_url = models.URLField(blank=True, help_text=_("Optional link from banner"))

    # Login / public surfaces
    login_background = models.ImageField( upload_to=_logo_upload_to,blank=True,null=True, )
    login_welcome_message = models.TextField(blank=True)
    support_email = models.EmailField(blank=True)
    support_phone = models.CharField(max_length=30, blank=True)

    # Meta
    version = models.PositiveIntegerField(default=1, editable=False)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL, null=True,blank=True,related_name="system_branding_updates",)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("System Branding")
        verbose_name_plural = _("System Branding")
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"System Branding v{self.version} ({self.mode})"

    def clean(self):
        super().clean()
        if self.banner_enabled and not self.banner_text.strip():
            raise ValidationError({"banner_text": _("Banner text is required when banner is enabled.")})

    def save(self, *args, **kwargs):
        if self.pk:
            self.version = (self.version or 0) + 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls) -> "SystemBranding":
        """Return the single active SystemBranding, creating defaults if missing."""
        obj = cls.objects.filter(is_active=True).order_by("-updated_at").first()
        if obj is None:
            obj = cls.objects.create()
        return obj


# School-level branding — Principal / school admin

class SchoolBranding(models.Model):
    """
    Per-school visual identity.
    Null / empty token fields inherit from SystemBranding.
    Schools cannot change system logo or platform mode.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.OneToOneField("schools.School",on_delete=models.CASCADE,related_name="branding",)

    # Logos
    logo_light = models.ImageField(upload_to=_logo_upload_to,blank=True,null=True,validators=[FileExtensionValidator(["png", "jpg", "jpeg", "svg", "webp"])],)
    logo_dark = models.ImageField( upload_to=_logo_upload_to, blank=True, null=True, validators=[FileExtensionValidator(["png", "jpg", "jpeg", "svg", "webp"])], )
    logo_square = models.ImageField(upload_to=_logo_upload_to,blank=True,null=True,validators=[FileExtensionValidator(["png", "jpg", "jpeg", "svg", "webp"])],)
    favicon = models.ImageField(upload_to=_logo_upload_to, blank=True,null=True,validators=[FileExtensionValidator(["png", "ico", "svg"])],)

    # Tokens (null/empty key → inherit system)
    colour_tokens = models.JSONField(default=dict,blank=True,help_text=_("Partial map; missing keys inherit from system"),)
    typography = models.JSONField(default=dict, blank=True)
    density = models.CharField( max_length=20,choices=DensityChoices.choices, blank=True, help_text=_("Blank = inherit system density"), )
    border_radius_px = models.PositiveSmallIntegerField(null=True, blank=True,help_text=_("Blank = inherit system"),)

    # Local chrome
    welcome_message = models.TextField(blank=True)
    local_banner_enabled = models.BooleanField(default=False)
    local_banner_text = models.CharField(max_length=500, blank=True)
    local_banner_level = models.CharField(max_length=20,choices=BannerLevelChoices.choices,default=BannerLevelChoices.INFO,)

    # Behaviour flags
    use_system_theme = models.BooleanField(default=False,help_text=_("If true, ignore school colour tokens and always use system theme"),)
    suppress_in_exam_mode = models.BooleanField( default=True, help_text=_("When system is in exam_season, prefer system logo/tokens"),)

    # Meta
    version = models.PositiveIntegerField(default=1, editable=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="school_branding_updates",)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("School Branding")
        verbose_name_plural = _("School Branding")
        ordering = ["school__school_name"]

    def __str__(self) -> str:
        return f"Branding – {self.school}"

    def save(self, *args, **kwargs):
        if self.pk:
            self.version = (self.version or 0) + 1
        super().save(*args, **kwargs)


# Optional: reusable presets (Root publishes, schools may pick)

class ThemePreset(models.Model):
    """
    Curated colour palettes published by Root.
    Schools can apply a preset instead of hand-picking every token.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    colour_tokens = models.JSONField(default=_default_colour_tokens)
    is_public = models.BooleanField(default=True,help_text=_("If false, only Root can assign it"),)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


# Optional: explicit change log (complements SystemAuditEvent)

class BrandingChangeLog(models.Model):
    """
    Lightweight history of branding mutations for quick UI timelines.
    Full forensic trail still lives in SystemAuditEvent.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(max_length=20,choices=[("system", "System"), ("school", "School")],)
    school = models.ForeignKey("schools.School",on_delete=models.CASCADE, null=True, blank=True,related_name="branding_changes",)
    actor = models.ForeignKey( settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name="branding_changes",)
    action = models.CharField(max_length=50)  # e.g. update_tokens, set_mode, upload_logo
    summary = models.CharField(max_length=255)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["scope", "created_at"]),
            models.Index(fields=["school", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.scope}: {self.summary}"