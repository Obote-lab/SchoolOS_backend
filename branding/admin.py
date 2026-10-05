from django.contrib import admin
from .models import BrandingChangeLog, SchoolBranding, SystemBranding, ThemePreset


@admin.register(SystemBranding)
class SystemBrandingAdmin(admin.ModelAdmin):
    list_display = ("id", "mode", "version", "banner_enabled", "updated_at", "updated_by")
    readonly_fields = ("version", "created_at", "updated_at")
    fieldsets = (
        ("Logos", {"fields": ("logo_light", "logo_dark", "logo_square", "favicon")}),
        (
            "Mode",
            {
                "fields": (
                    "mode",
                    "mode_label",
                    "mode_logo_light",
                    "mode_logo_dark",
                    "mode_colour_overrides",
                )
            },
        ),
        ("Tokens & layout", {"fields": ("colour_tokens", "typography", "density", "border_radius_px")}),
        (
            "Banner",
            {
                "fields": (
                    "banner_enabled",
                    "banner_text",
                    "banner_level",
                    "banner_dismissible",
                    "banner_url",
                )
            },
        ),
        (
            "Login / support",
            {
                "fields": (
                    "login_background",
                    "login_welcome_message",
                    "support_email",
                    "support_phone",
                )
            },
        ),
        ("Meta", {"fields": ("is_active", "version", "updated_by", "created_at", "updated_at")}),
    )


@admin.register(SchoolBranding)
class SchoolBrandingAdmin(admin.ModelAdmin):
    list_display = ("school", "version", "use_system_theme", "updated_at", "updated_by")
    list_filter = ("use_system_theme", "suppress_in_exam_mode")
    search_fields = ("school__school_name", "school__school_code")
    readonly_fields = ("version", "created_at", "updated_at")
    raw_id_fields = ("school", "updated_by")


@admin.register(ThemePreset)
class ThemePresetAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_public", "is_active", "sort_order")
    list_editable = ("is_public", "is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(BrandingChangeLog)
class BrandingChangeLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "scope", "school", "actor", "action", "summary")
    list_filter = ("scope", "action")
    readonly_fields = [f.name for f in BrandingChangeLog._meta.fields]
    ordering = ("-created_at",)