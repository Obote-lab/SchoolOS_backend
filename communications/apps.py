from django.apps import AppConfig


class CommunicationsConfig(AppConfig):
    name = 'communications'
    verbose_name = "Communications"

    def ready(self):
        import communications.signals  # noqa
