import logging
import os
from typing import Optional

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.core.files.utils import validate_file_name
from django.db import models
from django.db.models.fields.files import FieldFile
from home.util.s3 import S3Bucket, use_s3

log = logging.getLogger("app")

THUMBS_PREFIX = "thumbs/"


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


def file_name_error(name: str) -> Optional[str]:
    """
    Returns an error unless name is a bare file name. The name is used as the
    storage path, so separators or dot segments would write outside MEDIA_ROOT
    or over other stored files (the database lives under MEDIA_ROOT/db).
    """
    # validate_file_name only splits on os.sep; other code treats backslash as a separator
    if "\\" in name or "\x00" in name:
        return f"File name '{name}' includes path elements"
    try:
        validate_file_name(name)
    except SuspiciousFileOperation as error:
        return str(error)
    return None


def file_rename(file, new_file_name: str):
    if error := file_name_error(new_file_name):
        raise SuspiciousFileOperation(error)
    current_file_name = file.file.name
    file.name = new_file_name
    file.file.name = new_file_name
    if file.thumb:
        file.thumb.name = THUMBS_PREFIX + new_file_name
    if use_s3():
        s3 = S3Bucket().connection
        s3.Object(settings.AWS_STORAGE_BUCKET_NAME, new_file_name).copy_from(
            CopySource=f"{settings.AWS_STORAGE_BUCKET_NAME}/{current_file_name}"
        )
        s3.Object(settings.AWS_STORAGE_BUCKET_NAME, current_file_name).delete()
        if file.thumb:
            try:
                s3.Object(settings.AWS_STORAGE_BUCKET_NAME, THUMBS_PREFIX + new_file_name).copy_from(
                    CopySource=f"{settings.AWS_STORAGE_BUCKET_NAME}/thumbs/{current_file_name}"
                )
                s3.Object(settings.AWS_STORAGE_BUCKET_NAME, THUMBS_PREFIX + current_file_name).delete()
            except ClientError:
                log.exception(f"Failed to rename thumb for {current_file_name} to {new_file_name}")
    else:
        os.rename(f"{settings.MEDIA_ROOT}/{current_file_name}", f"{settings.MEDIA_ROOT}/{new_file_name}")
        if file.thumb:
            try:
                os.rename(
                    f"{settings.MEDIA_ROOT}/thumbs/{current_file_name}",
                    f"{settings.MEDIA_ROOT}/thumbs/{new_file_name}",
                )
            except FileNotFoundError:
                log.exception(f"Failed to rename thumb for {current_file_name} to {new_file_name}: not found")
    file.save(update_fields=["name", "file", "thumb"])
    cache.delete(f"file.urlcache.gallery.{file.pk}")
    cache.delete(f"file.urlcache.download.{file.pk}")
    cache.delete(f"file.urlcache.raw.{file.pk}")
    cache.delete(f"file.urlcache.meta_static.{file.pk}")
    return file


def fetch_file(file):
    # fetches the byte contents for the file, this is only currently used in test
    if use_s3():
        s3 = S3Bucket().connection.meta.client
        response = s3.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file.name)
        file_content = response["Body"].read()
        return file_content
    with open(f"{settings.MEDIA_ROOT}/{file.name}", "rb") as f:
        return f.read()


def fetch_raw_file(filename):
    # no s3 use, this is only currently used in test
    with open(f"{settings.MEDIA_ROOT}/{filename}", "rb") as f:
        return f.read()
