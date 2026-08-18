from django.apps import AppConfig
from django.conf import settings
from PIL import Image


class HomeConfig(AppConfig):
    name = "home"
    verbose_name = "Home"

    def ready(self):
        import home.signals  # noqa: F401

        # Hard backstop for every Image.open in the process (Celery backfill
        # tasks, avatar handling, etc.): Pillow warns above this and raises
        # DecompressionBombError above 2x it. The upload path checks the
        # budget explicitly first, so uploads skip processing gracefully.
        if settings.UPLOAD_MAX_IMAGE_PIXELS:
            Image.MAX_IMAGE_PIXELS = settings.UPLOAD_MAX_IMAGE_PIXELS
