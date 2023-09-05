import logging
from django.apps import AppConfig

log = logging.getLogger('app')


class HomeConfig(AppConfig):
    name = 'home'
    verbose_name = 'Home'

    def ready(self):
        import home.signals  # noqa: F401
        from home.tasks import export_settings  # noqa: F401
        export_settings()
