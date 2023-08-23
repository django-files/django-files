import logging
import mimetypes
import os
# from django.conf import settings
from django.core.files import File
# from pathlib import Path
from typing import IO

from home.models import Files
from home.util.processors import ImageProcessor
from home.util.s3 import use_s3
from home.tasks import send_discord_message
from oauth.models import CustomUser

log = logging.getLogger('app')


def process_file(name: str, f: IO, user_id: int, **kwargs) -> Files:
    """
    Process File Uploads
    :param name: String: name of the file
    :param f: File Object: The file to upload
    :param user_id: Integer: user ID
    :param kwargs: Extra Files Object Values
    :return: Files: The created Files object
    """
    log.info('process_file_upload: name: %s', name)
    user = CustomUser.objects.get(id=user_id)
    log.info('user: %s', user)
    file = Files.objects.create(file=File(f, name=name), user=user, **kwargs)
    file.name = os.path.basename(file.file.name)
    log.info('file.name: %s', file.name)
    file.mime, _ = mimetypes.guess_type(file.file.path, strict=False)
    if not file.mime:
        file.mime, _ = mimetypes.guess_type(file.file.name, strict=False)
    file.mime = file.mime or 'application/octet-stream'
    log.info('file.mime: %s', file.mime)
    file.size = file.file.size
    log.info('file.size: %s', file.size)
    log.info('file.file.path: %s', file.file.path)
    if file.mime in ['image/jpe', 'image/jpg', 'image/jpeg', 'image/webp']:
        processor = ImageProcessor(file, file.file.path)
        processor.process_file()
    file.save()
    send_discord_message.delay(file.pk)
    # TODO: Why are we not just using django.conf.settings to check this?
    if use_s3():
        # TODO: This should probably async
        os.remove(file.file.path)
    return file
