from django.db import models


class FilesManager(models.Manager):
    def get_request(self, request):
        return self.filter(user=request.user)
