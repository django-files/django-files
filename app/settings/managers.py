from django.db import models


class WebhooksManager(models.Manager):
    def get_request(self, request, **kwargs):
        return self.filter(owner=request.user, **kwargs)
