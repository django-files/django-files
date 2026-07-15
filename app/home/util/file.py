import contextlib
import datetime
import logging
import mimetypes
import os
import pathlib
import shutil
import tempfile
import uuid
from typing import BinaryIO, Optional, Union

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


def _pop_upload_options(user: CustomUser, kwargs: dict) -> dict:
    """
    Pop processor-only options out of kwargs (so they never reach the Files
    constructor), applying user defaults; returns the processor ctx.
    """
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
    return ctx


def _replace_existing_avatar(user: CustomUser, kwargs: dict) -> None:
    if kwargs.get("avatar") != "True":
        return
    log.debug("This is an avatar upload.")
    # avatar should never expire
    kwargs.pop("expr", None)
    try:
        # if user avatar already exists for the user delete it
        Files.objects.get(user=user, avatar=True).delete()
    except ObjectDoesNotExist:
        pass


def _stage_source(f: Union[BinaryIO, LocalFile], name: str, stack: contextlib.ExitStack) -> str:
    """
    Return a local filesystem path for the upload source. Reuses the on-disk
    file directly when we own it: a LocalFile from server-side code, or the
    temp file Django already spooled the upload to. This skips a full extra
    disk copy, which matters for multi-GB files.
    """
    if isinstance(f, LocalFile):
        return f.path
    if isinstance(f, TemporaryUploadedFile):
        return f.temporary_file_path()
    # Stream in chunks rather than f.read() — reading a large file (e.g. a
    # multi-GB stream recording) into memory in one shot can exceed the
    # worker's memory limit and get it OOM-killed.
    tmp = stack.enter_context(tempfile.NamedTemporaryFile(suffix=os.path.basename(name)))
    shutil.copyfileobj(f, tmp, length=1024 * 1024)
    tmp.flush()
    return tmp.name


def _detect_mime(path: str, name: str) -> str:
    file_mime = magic.from_file(path, mime=True)
    # libmagic uses content analysis, which misidentifies text files —
    # e.g. a .md file containing Python code blocks becomes
    # text/x-script.python. For any text/* result, prefer the
    # extension-based guess when it provides a more specific type.
    if file_mime and (file_mime.startswith("text/") or file_mime == OCTET_STREAM):
        guess, _ = mimetypes.guess_type(name, strict=False)
        if guess and guess != OCTET_STREAM:
            file_mime = guess
    return file_mime or OCTET_STREAM


def _process_metadata(file: Files, path: str, file_mime: str, user: CustomUser, ctx: dict) -> Optional[str]:
    """
    Run the image/video metadata processors (these may rewrite the file at
    `path` in place); returns the detected image extension, if any.
    """
    if file_mime in IMAGE_THUMB_MIMES:
        # when handling images, if we detect an extension we need to
        # tell PIL to use that extension now and in thumbnail processor
        detected_extension = file_mime.split("/")[1]
        processor = ImageProcessor(path, user.remove_exif, user.remove_exif_geo, ctx, detected_extension)
        processor.process_file()
        file.meta = processor.meta
        file.exif = processor.exif
        return detected_extension
    if file_mime.startswith("video/"):
        strip_gps = ctx.get("strip_gps", user.remove_exif_geo)
        file.exif, file.meta = video_metadata_processor(path, strip_gps=strip_gps)
    return None


def _attach_album(file: Files, albums: Optional[str]) -> None:
    if not albums:
        return
    lookup = {"id": int(albums)} if albums.isnumeric() else {"name": albums}
    album = Albums.objects.filter(**lookup)
    log.debug("album: %s", album)
    if album:
        file.albums.add(album[0])
        file.save()


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
    _format = kwargs.pop("format", user.default_upload_name_format)
    name = get_formatted_name(name, _format)
    log.debug("get_formatted_name: name: %s", name)
    ctx = _pop_upload_options(user, kwargs)
    _replace_existing_avatar(user, kwargs)
    albums = kwargs.pop("albums", None)
    log.debug("albums: %s", albums)
    tags = kwargs.pop("tags", None)
    log.debug("tags: %s", tags)

    file = Files(user=user, **kwargs)
    with contextlib.ExitStack() as stack:
        path = _stage_source(f, name, stack)
        log.debug("path: %s", path)
        file_mime = _detect_mime(path, name)
        log.debug("file_mime: %s", file_mime)
        detected_extension = _process_metadata(file, path, file_mime, user, ctx)
        # open a fresh handle after the processors — they may have rewritten
        # the file at `path` (EXIF stripping truncates and rewrites in place)
        fp = stack.enter_context(open(path, "rb"))
        file.file = File(fp, name=name)
        file.mime = file_mime
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
    _attach_album(file, albums)

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
