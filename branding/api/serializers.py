from rest_framework import serializers
from ..models import (
    BannerLevelChoices,
    BrandingChangeLog,
    DensityChoices,
    PlatformModeChoices,
    SchoolBranding,
    SystemBranding,
    ThemePreset,
)


# Resolved payload (read-only, what clients apply)
class ResolvedLogoSerializer(serializers.Serializer):
    light = serializers.URLField(allow_null=True)
    dark = serializers.URLField(allow_null=True)
    square = serializers.URLField(allow_null=True, required=False)
    favicon = serializers.URLField(allow_null=True, required=False)


class ResolvedBannerSerializer(serializers.Serializer):
    text = serializers.CharField()
    level = serializers.ChoiceField(choices=BannerLevelChoices.choices)
    dismissible = serializers.BooleanField()
    url = serializers.URLField(allow_null=True, required=False)
    source = serializers.CharField()


class ResolvedLoginSerializer(serializers.Serializer):
    background = serializers.URLField(allow_null=True)
    welcome_message = serializers.CharField(allow_blank=True)
    support_email = serializers.EmailField(allow_blank=True)
    support_phone = serializers.CharField(allow_blank=True)


class ResolvedBrandingSerializer(serializers.Serializer):
    """Flat contract consumed by every frontend surface."""

    version = serializers.CharField()
    system_version = serializers.IntegerField()
    school_version = serializers.IntegerField(allow_null=True)
    mode = serializers.ChoiceField(choices=PlatformModeChoices.choices)
    mode_label = serializers.CharField()
    system_logo = ResolvedLogoSerializer()
    school_logo = ResolvedLogoSerializer(allow_null=True)
    tokens = serializers.DictField(child=serializers.CharField())
    typography = serializers.DictField()
    density = serializers.ChoiceField(choices=DensityChoices.choices)
    border_radius_px = serializers.IntegerField()
    banner = ResolvedBannerSerializer(allow_null=True)
    login = ResolvedLoginSerializer()
    school_id = serializers.UUIDField(allow_null=True)
    school_name = serializers.CharField(allow_null=True, allow_blank=True)



# System branding (Root)

class SystemBrandingSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source="updated_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = SystemBranding
        fields = [
            "id",
            "logo_light",
            "logo_dark",
            "logo_square",
            "favicon",
            "mode",
            "mode_label",
            "mode_logo_light",
            "mode_logo_dark",
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
            "login_background",
            "login_welcome_message",
            "support_email",
            "support_phone",
            "version",
            "is_active",
            "updated_by",
            "updated_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "version",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class SystemBrandingUpdateSerializer(serializers.ModelSerializer):
    """Writable subset for PATCH by Root."""

    class Meta:
        model = SystemBranding
        fields = [
            "logo_light",
            "logo_dark",
            "logo_square",
            "favicon",
            "mode",
            "mode_label",
            "mode_logo_light",
            "mode_logo_dark",
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
            "login_background",
            "login_welcome_message",
            "support_email",
            "support_phone",
        ]

    def validate_colour_tokens(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Must be an object of token → colour.")
        return value or {}



# School branding

class SchoolBrandingSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.school_name", read_only=True)
    updated_by_name = serializers.CharField(source="updated_by.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = SchoolBranding
        fields = [
            "id",
            "school",
            "school_name",
            "logo_light",
            "logo_dark",
            "logo_square",
            "favicon",
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
            "version",
            "updated_by",
            "updated_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "school",
            "version",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class SchoolBrandingUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolBranding
        fields = [
            "logo_light",
            "logo_dark",
            "logo_square",
            "favicon",
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
        ]

    def validate_colour_tokens(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Must be an object of token → colour.")
        return value or {}



# Presets & change log

class ThemePresetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThemePreset
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "colour_tokens",
            "is_public",
            "is_active",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ApplyPresetSerializer(serializers.Serializer):
    preset_id = serializers.UUIDField()


class BrandingChangeLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.get_full_name", read_only=True, allow_null=True)
    school_name = serializers.CharField(source="school.school_name", read_only=True, allow_null=True)

    class Meta:
        model = BrandingChangeLog
        fields = [
            "id",
            "scope",
            "school",
            "school_name",
            "actor",
            "actor_name",
            "action",
            "summary",
            "before",
            "after",
            "created_at",
        ]
        read_only_fields = fields