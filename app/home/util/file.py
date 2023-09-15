import datetime
import logging
import magic
import mimetypes
import os
import uuid
import tempfile
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
    log.info('name: %s', name)
    log.info('f: %s', f)
    log.info('user_id: %s', user_id)
    log.info('kwargs: %s', kwargs)
    user = CustomUser.objects.get(id=user_id)
    log.info('user: %s', user)
    _format = kwargs.pop('format', user.get_default_upload_name_format_display())
    log.info('_format: %s', _format)
    name = get_formatted_name(name, _format)
    log.info('get_formatted_name: name: %s', name)
    ctx = {}
    if strip_exif := kwargs.pop('strip_exif', None) is not None:
        ctx['strip_exif'] = anytobool(strip_exif)
    if strip_gps := kwargs.pop('strip_gps', None) is not None:
        ctx['strip_gps'] = anytobool(strip_gps)
    if auto_pw := kwargs.pop('auto_pw', None) is not None:
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
        if file_mime and file_mime in ['text/plain', 'application/octet-stream']:
            guess, _ = mimetypes.guess_type(name, strict=False)
            if guess and guess not in ['application/octet-stream']:
                file_mime = guess
        file_mime = file_mime or 'application/octet-stream'
        log.debug('file_mime: %s', file_mime)
        if file_mime in ['image/jpe', 'image/jpg', 'image/jpeg', 'image/webp']:
            processor = ImageProcessor(fp.name, user.remove_exif, user.remove_exif_geo, ctx)
            processor.process_file()
            file.meta = processor.meta
            file.exif = processor.exif
        file.file = File(fp, name=name)
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
    new_file_websocket.delay(file.pk)
    send_discord_message.delay(file.pk)
    return file


def get_formatted_name(name: str, _format: str = '') -> str:
    _format = _format or ''
    log.debug('name: %s', name)
    log.debug('_format: %s', _format)
    ext = os.path.splitext(name)[1]
    log.debug('ext: %s', ext)
    match _format.lower():
        case 'random':
            return rand_string() + ext
        case 'uuid':
            return uuid.uuid4().hex + ext
        case 'date':
            return datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S") + ext
        case _:
            return name
