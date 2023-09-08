from django.db import models


class SiteSettingsManager(models.Manager):
    def settings(self):
        return self.get_or_create(pk=1)[0]
