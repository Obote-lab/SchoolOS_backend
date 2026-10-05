from django.apps import AppConfig


class BrandingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "branding"
    verbose_name = "Branding & Appearance"

    def ready(self):
        try:
            import branding.signals  # noqa: F401
        except ImportError:
            pass