from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        from .utils import create_default_superuser_if_needed
        create_default_superuser_if_needed()