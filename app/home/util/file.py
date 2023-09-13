import logging
import magic
import os
import uuid
import tempfile
from datetime import datetime
# from django.conf import settings
from django.core.files import File
# from pathlib import Path
from typing import IO

from home.models import Files
from home.util.image import ImageProcessor
from home.util.rand import rand_string
from home.util.misc import anytobool
from home.tasks import send_discord_message, new_file_websocket
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
    ctx = {}
    user = CustomUser.objects.get(id=user_id)
    log.info('user: %s', user)
    # process name first
    name = get_formatted_name(user, name, kwargs.pop('format', None))
    if (strip_exif := kwargs.pop('strip_exif', None)) is not None:
        ctx['strip_exif'] = anytobool(strip_exif)
    if (strip_gps := kwargs.pop('strip_gps', None) is not None):
        ctx['strip_gps'] = anytobool(strip_gps)
    if (auto_pw := kwargs.pop('auto_pw', None) is not None):
        if anytobool(auto_pw):
            kwargs['password'] = rand_string()
    else:
        if user.default_file_password:
            kwargs['password'] = rand_string()
    # we want to use a temporary local file to support cloud storage cases
    # this allows us to modify the file before upload
    file = Files(user=user, **kwargs)
    with tempfile.NamedTemporaryFile(suffix=os.path.basename(name)) as fp:
        fp.write(f.read())
        fp.seek(0)
        log.debug('fp.name: %s', fp.name)
        file_mime = magic.from_file(fp.name, mime=True)
        file_mime = file_mime or 'application/octet-stream'
        if file_mime in ['image/jpe', 'image/jpg', 'image/jpeg', 'image/webp']:
            processor = ImageProcessor(fp.name, user.remove_exif, user.remove_exif_geo, ctx)
            processor.process_file()
            file.meta = processor.meta
            file.exif = processor.exif
        file.file = File(fp, name=name)
        log.info('name: %s', name)
        file.mime = file_mime
        log.info('file.mime: %s', file.mime)
        file.size = file.file.size
        log.info('file.size: %s', file.size)
        if (meta_preview := kwargs.get('meta_preview')) is not None:
            file.meta_preview = anytobool(meta_preview)
        else:
            file.meta_preview = user.show_exif_preview
        if (private := kwargs.get('private')) is not None:
            file.private = anytobool(private)
        else:
            file.private = user.default_file_private
        file.save()
    log.info('file.file.name: %s', file.file.name)
    file.name = file.file.name
    file.save()
    new_file_websocket(file.pk)
    send_discord_message.delay(file.pk)
    return file


def get_formatted_name(user: CustomUser, name_input: str, format_name: str = ''):
    if not format_name:
        format_name = user.get_default_upload_name_format_display()
    match format_name.lower():
        case 'random':
            name = rand_string()
        case 'uuid':
            name = str(uuid.uuid4())
        case 'date':
            name = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        case _:
            name = name_input
    if name != name_input:
        name = name + os.path.splitext(name_input)[1]
    return name
