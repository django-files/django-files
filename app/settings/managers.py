from django.db import models


class SiteSettingsManager(models.Manager):
    def settings(self):
        site_settings, created = self.get_or_create(pk=1)
        return site_settings
