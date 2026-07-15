import contextlib
import datetime
import logging
import mimetypes
import os
import pathlib
import shutil
import tempfile
import uuid
from typing import BinaryIO, Union

import magic
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import transaction
from home.models import Albums, Files
from home.tasks import dispatch_webhook_event, generate_video_thumb, new_file_websocket
from home.util.image import ImageProcessor, thumbnail_processor
from home.util.misc import anytobool
from home.util.quota import increment_storage_usage
from home.util.rand import rand_string
from home.util.tags import attach_file_tags, sync_file_tags
from home.util.video import video_metadata_processor
from home.util.webhooks import EVENT_FILE_UPLOAD, build_file_payload
from oauth.models import CustomUser

log = logging.getLogger("app")

OCTET_STREAM = "application/octet-stream"
IMAGE_THUMB_MIMES = ("image/jpe", "image/jpg", "image/jpeg", "image/webp")


class LocalFile:
    """
    Marks a server-owned file already on disk that process_file may consume
    directly — no temp copy — and mutate in place (EXIF stripping). Trust is
    carried by this type on purpose: callers that accept client-controlled
    kwargs (websocket consumers, parse_headers) can never trigger the
    path-reuse branch with a string, only server code that constructs this
    wrapper can.
    """

    def __init__(self, path: str):
        self.path = path

    def __str__(self):
        return f"LocalFile({self.path})"


def process_file(name: str, f: Union[BinaryIO, LocalFile], user_id: int, **kwargs) -> Files:
    """
    Process File Uploads
    :param name: String: name of the file
    :param f: File Object or LocalFile: The file to upload
    :param user_id: Integer: user ID
    :param kwargs: Extra Files Object Values
    :return: Files: The created Files object
    """
    log.debug("name: %s", name)
    log.debug("f: %s", f)
    log.debug("user_id: %s", user_id)
    log.debug("kwargs: %s", kwargs)
    user = CustomUser.objects.get(id=user_id)
    log.debug("user: %s", user)
    log.debug("user.default_upload_name_format: %s", user.default_upload_name_format)
    _format = kwargs.pop("format", user.default_upload_name_format)
    log.debug("_format: %s", _format)
    name = get_formatted_name(name, _format)
    log.debug("get_formatted_name: name: %s", name)
    ctx = {}
    if (strip_exif := kwargs.pop("strip_exif", None)) is not None:
        ctx["strip_exif"] = anytobool(strip_exif)
    if (strip_gps := kwargs.pop("strip_gps", None)) is not None:
        ctx["strip_gps"] = anytobool(strip_gps)
    if (auto_password := kwargs.pop("auto_password", None)) is not None:
        if anytobool(auto_password):
            kwargs["password"] = rand_string()
    elif user.default_file_password and not kwargs.get("password"):
        kwargs["password"] = rand_string()
    # we want to use a temporary local file to support cloud storage cases
    # this allows us to modify the file before upload
    if kwargs.get("avatar") == "True":
        log.debug("This is an avatar upload.")
        # avatar should never expire
        kwargs.pop("expr", None)
        try:
            # if user avatar already exists for the user delete it
            file = Files.objects.get(user=user, avatar=True)
            file.delete()
        except ObjectDoesNotExist:
            pass

    albums = None
    if "albums" in kwargs:
        albums = kwargs.pop("albums")
    log.debug("albums: %s", albums)
    tags = kwargs.pop("tags", None)
    log.debug("tags: %s", tags)

    file = Files(user=user, **kwargs)
    # Reuse the on-disk source directly when we own it: a LocalFile from
    # server-side code, or the temp file Django already spooled the upload to.
    # This skips a full extra disk copy, which matters for multi-GB files.
    if isinstance(f, LocalFile):
        local_path = f.path
    elif isinstance(f, TemporaryUploadedFile):
        local_path = f.temporary_file_path()
    else:
        local_path = None
    detected_extension = None
    with contextlib.ExitStack() as stack:
        if local_path:
            path = local_path
        else:
            # Stream in chunks rather than f.read() — reading a large file (e.g. a
            # multi-GB stream recording) into memory in one shot can exceed the
            # worker's memory limit and get it OOM-killed.
            tmp = stack.enter_context(tempfile.NamedTemporaryFile(suffix=os.path.basename(name)))
            shutil.copyfileobj(f, tmp, length=1024 * 1024)
            tmp.flush()
            path = tmp.name
        log.debug("path: %s", path)
        file_mime = magic.from_file(path, mime=True)
        # libmagic uses content analysis, which misidentifies text files —
        # e.g. a .md file containing Python code blocks becomes
        # text/x-script.python. For any text/* result, prefer the
        # extension-based guess when it provides a more specific type.
        if file_mime and (file_mime.startswith("text/") or file_mime == OCTET_STREAM):
            guess, _ = mimetypes.guess_type(name, strict=False)
            if guess and guess != OCTET_STREAM:
                file_mime = guess
        file_mime = file_mime or OCTET_STREAM
        log.debug("file_mime: %s", file_mime)
        if file_mime in IMAGE_THUMB_MIMES:
            # when handling images, if we detect an extension we need to
            # tell PIL to use that extension now and in thumbnail processor
            detected_extension = file_mime.split("/")[1]
            processor = ImageProcessor(path, user.remove_exif, user.remove_exif_geo, ctx, detected_extension)
            processor.process_file()
            file.meta = processor.meta
            file.exif = processor.exif
        elif file_mime.startswith("video/"):
            strip_gps = ctx.get("strip_gps", user.remove_exif_geo)
            v_exif, v_meta = video_metadata_processor(path, strip_gps=strip_gps)
            file.exif = v_exif
            file.meta = v_meta
        # open a fresh handle after the processors — they may have rewritten
        # the file at `path` (EXIF stripping truncates and rewrites in place)
        fp = stack.enter_context(open(path, "rb"))
        file.file = File(fp, name=name)
        file.mime = file_mime
        log.debug("file.mime: %s", file.mime)
        file.size = file.file.size
        log.debug("file.size: %s", file.size)
        if (meta_preview := kwargs.get("meta_preview")) is not None:
            file.meta_preview = anytobool(meta_preview)
        else:
            file.meta_preview = user.show_exif_preview
        if (private := kwargs.get("private")) is not None:
            file.private = anytobool(private)
        else:
            file.private = user.default_file_private
        file.save()
        log.debug("file.file.name: %s", file.file.name)
        file.name = file.file.name
        file.save()
        if detected_extension:
            # generate the thumbnail from the local copy while we still have
            # it on disk instead of re-downloading the file from storage
            thumbnail_processor(file, path, detected_extension)
    sync_file_tags(file)
    if tags:
        # before the webhook dispatch below so tag include-filters can match
        attach_file_tags(file, tags)

    if albums:
        if albums.isnumeric():
            kwargs = {"id": int(albums)}
        else:
            kwargs = {"name": albums}
        album = Albums.objects.filter(**kwargs)
        log.debug("album: %s", album)
        if album:
            # file[0].albums.add(Albums.objects.filter(id=album)[0])
            file.albums.add(album[0])
            file.save()

    if file_mime.startswith("video/"):
        # on_commit ensures the row is visible to the Celery worker before the
        # task is dispatched, preventing a DoesNotExist race on fast workers.
        strip_gps = ctx.get("strip_gps", user.remove_exif_geo)
        pk = file.pk
        transaction.on_commit(lambda: generate_video_thumb.apply_async(args=[pk], kwargs={"strip_gps": strip_gps}))
    increment_storage_usage(file)
    new_file_websocket.apply_async(args=[file.pk], priority=0)
    dispatch_webhook_event.delay(EVENT_FILE_UPLOAD, file.user_id, build_file_payload(file))
    return file


def get_formatted_name(name: str, _format: str = "") -> str:
    log.debug("name: %s", name)
    ext = os.path.splitext(name)[1]
    log.debug("ext: %s", ext)
    log.debug("_format: %s", _format)
    if _format:
        match _format.lower():
            case "rand":
                return rand_string() + ext
            case "uuid":
                return uuid.uuid4().hex + ext
            case "date":
                # TODO: Look into removing the : from filenames
                return datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S") + ext
    # check file name is not too long, if so fix it, leave room for rand
    name = truncate_long_names(name)
    return name


def truncate_long_names(name: str) -> str:
    if (trunc := (240 - len(name))) < 0:
        log.debug("Truncating filename since filename is too long.")
        exts = ".".join(pathlib.Path(name).suffixes)
        log.debug(f"extensions {exts}")
        name = name[: trunc + len(exts)] + (("." + exts) if len(exts) > 0 else "")
        log.debug(f"New name {name}")
    return name
