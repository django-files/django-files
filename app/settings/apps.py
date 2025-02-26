from django.apps import AppConfig


class SettingsConfig(AppConfig):
    name = "settings"
    verbose_name = "Settings"

    def ready(self):
        import settings.signals  # noqa: F401
