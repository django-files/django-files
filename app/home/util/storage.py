from storages.backends.s3boto3 import S3Boto3Storage
from django.core.files.storage import default_storage
from django.db import models
from django.db.models.fields.files import FieldFile


# def storage_router(initial_upload=False, *args, **kwargs):
#     if initial_upload:
#         return default_storage
#     elif True:  # this eventually needs to be based on if s3 is configured, but circular import issue stopping 
#         return S3Boto3Storage(*args, **kwargs)


class DynamicStorageFieldFile(FieldFile):
    def __init__(self, instance, field, name):
        super(DynamicStorageFieldFile, self).__init__(
           instance, field, name
        )
        if True:  # TODO:  this needs to read site settings or user settings to find out where to go next.
            self.storage = S3Bucket()


class StoragesRouterFileField(models.FileField):

    attr_class = DynamicStorageFieldFile

    def pre_save(self, model_instance, add):
        if True:  # TODO:  this needs to read site settings or user settings to find out where to go next.
            self.storage = S3Bucket()
        file = super(StoragesRouterFileField, self
                     ).pre_save(model_instance, add)
        return file


class S3Bucket(S3Boto3Storage):
    bucket_name = 'i.luac.es'