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
        if not instance.meta:  # if meta is None we have not processed a file
            self.storage = default_storage
        else:
            if True:  # TODO:  this needs to read site settings or user settings to find out where to go next.
                self.storage = S3Boto3Storage()


class StoragesRouterFileField(models.FileField):

    attr_class = DynamicStorageFieldFile

    def pre_save(self, model_instance, add):
        if not model_instance.meta:  # if meta is None we have not processed a file
            self.storage = default_storage
        else:
            if True:  # TODO:  this needs to read site settings or user settings to find out where to go next.
                self.storage = S3Boto3Storage()
        file = super(StoragesRouterFileField, self
                     ).pre_save(model_instance, add)
        return file
