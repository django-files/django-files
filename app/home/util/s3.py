import os

from django.conf import settings
from storages.backends.s3 import S3Storage


def use_s3():
    if os.getenv("AWS_STORAGE_BUCKET_NAME", False):
        return True
    return False


class S3Bucket(S3Storage):
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    def url(self, name, parameters=None, expire=None, http_method=None):
        url = super().url(name, parameters, expire, http_method)
        if settings.AWS_S3_CDN_URL:
            return url.replace(f"https://s3.amazonaws.com/{self.bucket_name}", settings.AWS_S3_CDN_URL)
        return url
