from django.apps import AppConfig


class StudentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "students"
    verbose_name = "Students Management"

    def ready(self):
        """Import signals when app is ready"""
        import students.signals
