from django.core.cache import cache
from django.db import models

CACHE_KEY = "site_settings_obj"


class SiteSettingsManager(models.Manager):
    def settings(self):
        obj = cache.get(CACHE_KEY)
        if obj is None:
            obj = self.get_or_create(pk=1)[0]
            cache.set(CACHE_KEY, obj)
        return obj
