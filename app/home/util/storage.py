
from django.core.files.storage import default_storage
from home.util.s3 import S3Bucket, use_s3

from django.db import models
from django.db.models.fields.files import FieldFile


class DynamicStorageFieldFile(FieldFile):
    def __init__(self, instance, field, name):
        super(DynamicStorageFieldFile, self).__init__(
           instance, field, name
        )
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
        file = super(StoragesRouterFileField, self
                     ).pre_save(model_instance, add)
        return file
