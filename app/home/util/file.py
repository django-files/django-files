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
from typing import BinaryIO
from django.core.exceptions import ObjectDoesNotExist

from home.models import Files
from home.util.image import ImageProcessor
from home.util.rand import rand_string
from home.util.misc import anytobool
from home.util.quota import increment_storage_usage
from home.tasks import send_discord_message, new_file_websocket
from oauth.models import CustomUser


log = logging.getLogger('app')


def process_file(name: str, f: BinaryIO, user_id: int, **kwargs) -> Files:
    """
    Process File Uploads
    :param name: String: name of the file
    :param f: File Object: The file to upload
    :param user_id: Integer: user ID
    :param kwargs: Extra Files Object Values
    :return: Files: The created Files object
    """
    processed_thumb = False
    log.debug('name: %s', name)
    log.debug('f: %s', f)
    log.debug('user_id: %s', user_id)
    log.debug('kwargs: %s', kwargs)
    user = CustomUser.objects.get(id=user_id)
    log.debug('user: %s', user)
    log.debug('user.default_upload_name_format: %s', user.default_upload_name_format)
    _format = kwargs.pop('format', user.default_upload_name_format)
    log.debug('_format: %s', _format)
    name = get_formatted_name(name, _format)
    log.debug('get_formatted_name: name: %s', name)
    ctx = {}
    if strip_exif := kwargs.pop('strip_exif', None) is not None:
        ctx['strip_exif'] = anytobool(strip_exif)
    if strip_gps := kwargs.pop('strip_gps', None) is not None:
        ctx['strip_gps'] = anytobool(strip_gps)
    if auto_password := kwargs.pop('auto_password', None) is not None:
        if anytobool(auto_password):
            kwargs['password'] = rand_string()
    else:
        if user.default_file_password:
            kwargs['password'] = rand_string()
    # we want to use a temporary local file to support cloud storage cases
    # this allows us to modify the file before upload
    if kwargs.get("avatar") == "True":
        log.debug('This is an avatar upload.')
        # avatar should never expire
        kwargs.pop('expr', None)
        try:
            # if user avatar already exists for the user delete it
            file = Files.objects.get(user=user, avatar=True)
            file.delete()
        except ObjectDoesNotExist:
            pass
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
            processed_thumb = True
            processor.process_file()
            file.meta = processor.meta
            file.exif = processor.exif
        file.file = File(fp, name=name)
        file.mime = file_mime
        log.debug('file.mime: %s', file.mime)
        file.size = file.file.size
        log.debug('file.size: %s', file.size)
        if (meta_preview := kwargs.get('meta_preview')) is not None:
            file.meta_preview = anytobool(meta_preview)
        else:
            file.meta_preview = user.show_exif_preview
        if (private := kwargs.get('private')) is not None:
            file.private = anytobool(private)
        else:
            file.private = user.default_file_private
        file.save()
    log.debug('file.file.name: %s', file.file.name)
    file.name = file.file.name
    file.save()
    increment_storage_usage(file)
    new_file_websocket.apply_async(args=[file.pk], priority=0)
    send_discord_message.delay(file.pk)
    if processed_thumb:
        with open(processor.tmp_thumb, 'rb') as thumb:
            file.thumb = File(thumb, name=name)
            file.save()
        os.remove(processor.tmp_thumb)
    return file


def get_formatted_name(name: str, _format: str = '') -> str:
    # TODO: Handle names without a . by using mime-type
    log.debug('name: %s', name)
    ext = os.path.splitext(name)[1]
    log.debug('ext: %s', ext)
    log.debug('_format: %s', _format)
    if _format:
        match _format.lower():
            case 'rand':
                return rand_string() + ext
            case 'uuid':
                return uuid.uuid4().hex + ext
            case 'date':
                # TODO: Look into removing the : from filenames
                return datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S") + ext
    return name
