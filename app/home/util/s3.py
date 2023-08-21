
import os
from storages.backends.s3boto3 import S3Boto3Storage


def use_s3():
    if os.getenv("AWS_STORAGE_BUCKET_NAME", False):
        return True
    return False


class S3Bucket(S3Boto3Storage):
    bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME", False)
