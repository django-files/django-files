import boto3
import os

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.db.models.fields.files import FieldFile
from botocore.exceptions import ClientError

from home.util.s3 import S3Bucket, use_s3


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


def file_rename(current_file_name: str, new_file_name: str, thumb: False) -> bool:
    if use_s3():
        s3 = boto3.resource('s3')
        s3.Object(
            settings.AWS_STORAGE_BUCKET_NAME, new_file_name
            ).copy_from(CopySource=f'{settings.AWS_STORAGE_BUCKET_NAME}/{current_file_name}')
        s3.Object(settings.AWS_STORAGE_BUCKET_NAME, current_file_name).delete()
        if thumb:
            try:
                s3.Object(
                    settings.AWS_STORAGE_BUCKET_NAME, 'thumbs/' + new_file_name
                    ).copy_from(CopySource=f'{settings.AWS_STORAGE_BUCKET_NAME}/thumbs/{current_file_name}')
                s3.Object(settings.AWS_STORAGE_BUCKET_NAME, 'thumbs/' + current_file_name).delete()
            except ClientError:
                # we dont want to fail a rename just because thumbs failed
                pass
    else:
        os.rename(f'{settings.MEDIA_ROOT}/{current_file_name}', f'{settings.MEDIA_ROOT}/{new_file_name}')
        if thumb:
            try:
                os.rename(
                    f'{settings.MEDIA_ROOT}/thumbs/{current_file_name}',
                    f'{settings.MEDIA_ROOT}/thumbs/{new_file_name}')
            except FileNotFoundError:
                pass
    return True


def fetch_file(file):
    # fetches the byte contents for the file
    if use_s3():
        s3 = boto3.client('s3')
        response = s3.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file.name)
        file_content = response['Body'].read()
        return file_content
    with open(f'{settings.MEDIA_ROOT}/{file.name}', 'rb') as f:
        return f.read()
