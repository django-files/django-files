from django.db import models


class FilesManager(models.Manager):
    def get_request(self, request, **kwargs):
        return self.filter(user=request.user, avatar=False, **kwargs)

    def get_all_request(self, **kwargs):
        return self.all(avatar=False, **kwargs)

    def filtered_request(self, request, **kwargs):
        return self.filter(avatar=False, **kwargs)


class FileStatsManager(models.Manager):
    def get_request(self, request, **kwargs):
        return self.filter(user=request.user, **kwargs)


class ShortURLsManager(models.Manager):
    def get_request(self, request, **kwargs):
        return self.filter(user=request.user, **kwargs)


class AlbumsManager(models.Manager):
    def get_request(self, request, **kwargs):
        return self.filter(user=request.user, **kwargs)

    def get_all_request(self, **kwargs):
        return self.all(**kwargs)

    def filtered_request(self, request, **kwargs):
        return self.filter(**kwargs)
