import os

import boto3
import logging

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db import models
from django.db.models.fields.files import FieldFile
from home.util.s3 import S3Bucket, use_s3

log = logging.getLogger("app")


class DynamicStorageFieldFile(FieldFile):
    def __init__(self, instance, field, name):
        super(DynamicStorageFieldFile, self).__init__(instance, field, name)
        if use_s3():
            self.storage = S3Bucket()
        else:
            self.storage = default_storage


class StoragesRouterFileField(models.FileField):

    attr_class = DynamicStorageFieldFile

    def pre_save(self, model_instance, add):
        if use_s3():
            self.storage = S3Bucket()
        else:
            self.storage = default_storage
        file = super(StoragesRouterFileField, self).pre_save(model_instance, add)
        return file


def file_rename(file, new_file_name: str):
    current_file_name = file.file.name
    file.name = new_file_name
    file.file.name = new_file_name
    if file.thumb:
        file.thumb.name = "thumbs/" + new_file_name
    if use_s3():
        s3 = boto3.resource("s3")
        s3.Object(settings.AWS_STORAGE_BUCKET_NAME, new_file_name).copy_from(
            CopySource=f"{settings.AWS_STORAGE_BUCKET_NAME}/{current_file_name}"
        )
        s3.Object(settings.AWS_STORAGE_BUCKET_NAME, current_file_name).delete()
        if file.thumb:
            try:
                s3.Object(settings.AWS_STORAGE_BUCKET_NAME, "thumbs/" + new_file_name).copy_from(
                    CopySource=f"{settings.AWS_STORAGE_BUCKET_NAME}/thumbs/{current_file_name}"
                )
                s3.Object(settings.AWS_STORAGE_BUCKET_NAME, "thumbs/" + current_file_name).delete()
            except ClientError as e:
                log.error(f"Failed to rename thumb for {current_file_name} to {new_file_name}: {e}")
    else:
        os.rename(f"{settings.MEDIA_ROOT}/{current_file_name}", f"{settings.MEDIA_ROOT}/{new_file_name}")
        if file.thumb:
            try:
                os.rename(
                    f"{settings.MEDIA_ROOT}/thumbs/{current_file_name}",
                    f"{settings.MEDIA_ROOT}/thumbs/{new_file_name}",
                )
            except FileNotFoundError:
                log.error(f"Failed to rename thumb for {current_file_name} to {new_file_name}: not found")
    file.save(update_fields=["name", "file", "thumb"])
    cache.delete(f"file.urlcache.gallery.{file.pk}")
    cache.delete(f"file.urlcache.download.{file.pk}")
    cache.delete(f"file.urlcache.raw.{file.pk}")
    cache.delete(f"file.urlcache.meta_static.{file.pk}")
    return file


def fetch_file(file):
    # fetches the byte contents for the file, this is only currently used in test
    if use_s3():
        s3 = boto3.client("s3")
        response = s3.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file.name)
        file_content = response["Body"].read()
        return file_content
    with open(f"{settings.MEDIA_ROOT}/{file.name}", "rb") as f:
        return f.read()


def fetch_raw_file(filename):
    # no s3 use, this is only currently used in test
    with open(f"{settings.MEDIA_ROOT}/{filename}", "rb") as f:
        return f.read()
