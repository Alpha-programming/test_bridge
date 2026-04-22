from django.apps import AppConfig


class TopikConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "topik"

    def ready(self):
        import topik.signals