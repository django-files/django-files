import json
import logging
import os
import tempfile
from typing import Optional

import httpx
from api.utils import extract_files
from asgiref.sync import async_to_sync
from celery import shared_task
from celery.signals import worker_shutdown
from channels.layers import get_channel_layer
from decouple import config
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from django.forms.models import model_to_dict
from django.template.loader import render_to_string
from django.utils import timezone
from home.models import Files, FileStats, Stream
from home.util.image import thumbnail_processor
from home.util.quota import regenerate_all_storage_values
from home.util.video import video_metadata_processor, video_thumbnail_processor
from oauth.models import CustomUser, DiscordWebhooks
from packaging import version
from PIL import UnidentifiedImageError
from pytimeparse2 import parse
from settings.models import SiteSettings
from webpush import send_group_notification

log = logging.getLogger("app")

VIDEO_MIME_PREFIX = "video/"


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 10, "countdown": 1})
def app_init():
    log.info("app_init")
    username = config("USERNAME", "admin")
    password = config("PASSWORD", "12345")
    oauth = bool(config("OAUTH_REDIRECT_URL", None))
    if not oauth or (username and password):
        CustomUser.objects.create_superuser(username=username, password=password)
        log.info("Initial User Created: %s", username)
    return "app_init - finished"


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60, "default_retry_delay": 180})
def generate_thumbs(user_pk: int = None, only_missing: bool = True):
    log.info("Generating Thumbnails - only_missing: %s - user_pk: %s", only_missing, user_pk)
    users = CustomUser.objects.filter(pk=user_pk) if user_pk else CustomUser.objects.all()
    # Formats Pillow cannot reliably thumbnail. DNG is TIFF-based so libmagic
    # may report image/tiff; exclude by extension as well to catch that case.
    thumb_exclude = Q(mime__in=["image/jxl", "image/x-adobe-dng"]) | Q(name__iendswith=".dng")

    if only_missing:
        files = Files.objects.filter(thumb__in=[None, ""], user__in=users, mime__startswith="image/").exclude(
            thumb_exclude
        )
    else:
        files = Files.objects.filter(user__in=users, mime__startswith="image").exclude(thumb_exclude)
    log.info("Processing thumbnails for %d objects: %s", len(files), files)
    for file in files:
        log.info("Generating thumbnail for: %s", file.name)
        try:
            thumbnail_processor(file)
        except ValueError, UnidentifiedImageError:
            # if we hit a file that cannot be processed ignore and continue
            log.error("Unable to process thumbnail for %s", file.name)
            continue

    # Queue a separate task per video so they run in parallel and each gets
    # its own retry budget. Evaluate the queryset once to avoid a COUNT then
    # SELECT double-query; generate_video_thumb checks for an existing thumb
    # before doing any work so re-queuing in-flight files is safe.
    if only_missing:
        video_files = list(
            Files.objects.filter(thumb__in=[None, ""], user__in=users, mime__startswith=VIDEO_MIME_PREFIX)
        )
    else:
        video_files = list(Files.objects.filter(user__in=users, mime__startswith=VIDEO_MIME_PREFIX))
    log.info("Queueing video thumbnails for %d files", len(video_files))
    for vfile in video_files:
        generate_video_thumb.delay(vfile.pk)


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def generate_video_thumb(pk: int, strip_gps: bool = None):
    """
    Generate a thumbnail for a single video file identified by primary key.

    Skips files whose recorded size exceeds settings.VIDEO_THUMB_MAX_BYTES
    to avoid filling /tmp with very large video downloads.
    """
    log.info("generate_video_thumb: pk=%s", pk)
    max_bytes = settings.VIDEO_THUMB_MAX_BYTES
    try:
        file = Files.objects.get(pk=pk)
    except Files.DoesNotExist:
        log.warning("generate_video_thumb: pk=%s not found, skipping", pk)
        return

    if strip_gps is None:
        strip_gps = bool(getattr(file.user, "remove_exif_geo", False))

    if file.thumb and file.exif and file.meta:
        log.info("generate_video_thumb: pk=%s already has thumbnail and metadata, skipping", pk)
        return
    if file.size and file.size > max_bytes:
        log.warning(
            "generate_video_thumb: pk=%s size %d bytes exceeds limit of %d bytes, skipping",
            pk,
            file.size,
            max_bytes,
        )
        return

    if not file.thumb:
        if not video_thumbnail_processor(file, max_bytes=max_bytes):
            log.warning("generate_video_thumb: failed to generate thumbnail for pk=%s", pk)
            return

    if not file.exif or not file.meta:
        _extract_video_metadata(file, strip_gps)


def _extract_video_metadata(file: Files, strip_gps: bool) -> bool:
    """Download the video and extract metadata into the Files record."""
    suffix = os.path.splitext(os.path.basename(file.name.replace("\\", "/")))[1] or ".mp4"
    tmp_video = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as vf:
            written = 0
            with file.file.open("rb") as source:
                for chunk in source.chunks():
                    written += len(chunk)
                    if written > settings.VIDEO_THUMB_MAX_BYTES:
                        raise ValueError(
                            f"Video exceeds {settings.VIDEO_THUMB_MAX_BYTES // (1024 * 1024)} MB size limit during download"
                        )
                    vf.write(chunk)
            tmp_video = vf.name

        exif, meta = video_metadata_processor(tmp_video, strip_gps=strip_gps)
        file.exif = exif
        file.meta = meta
        file.save(update_fields=["exif", "meta"])
        log.info("_extract_video_metadata: saved metadata for %s", file.name)
        return True
    except Exception:
        log.exception("_extract_video_metadata: failed for %s", file.name)
        return False
    finally:
        if tmp_video:
            try:
                os.remove(tmp_video)
            except OSError:
                pass


def _backfill_single_video(file, max_bytes: int) -> bool:
    """Download one video, extract GPS metadata, and persist it. Returns True if GPS was saved."""
    suffix = os.path.splitext(os.path.basename(file.name.replace("\\", "/")))[1] or ".mp4"
    tmp_video = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as vf:
            written = 0
            with file.file.open("rb") as source:
                for chunk in source.chunks():
                    written += len(chunk)
                    if written > max_bytes:
                        raise ValueError(f"Video exceeds {max_bytes // (1024 * 1024)} MB size limit during download")
                    vf.write(chunk)
            tmp_video = vf.name

        v_exif, v_meta = video_metadata_processor(tmp_video)
        if not v_exif.get("GPSInfo"):
            log.info("backfill_video_gps: pk=%s no GPS found", file.pk)
            return False

        file.exif = {**file.exif, **v_exif}
        file.meta = {**file.meta, **v_meta}
        file.save(update_fields=["exif", "meta"])
        log.info("backfill_video_gps: pk=%s GPS saved", file.pk)
        return True

    except Exception:
        log.exception("backfill_video_gps: failed for pk=%s, continuing", file.pk)
        return False
    finally:
        if tmp_video:
            try:
                os.remove(tmp_video)
            except OSError:
                pass


@shared_task()
def backfill_video_gps():
    """
    One-time backfill task: scan every eligible video file that has no stored
    GPS data, download it to a local temp file (compatible with both S3 and
    local filesystem storage), and attempt to extract GPS metadata.

    Trigger from the Django shell or Flower:
        from home.tasks import backfill_video_gps
        backfill_video_gps.delay()

    TODO: Remove this task in a future release.
    """
    max_bytes = settings.VIDEO_THUMB_MAX_BYTES
    files = (
        Files.objects.filter(mime__startswith=VIDEO_MIME_PREFIX, user__remove_exif_geo=False)
        .exclude(exif__has_key="GPSInfo")
        .exclude(size__gt=max_bytes)
        .select_related("user")
    )
    total = len(files)
    log.info("backfill_video_gps: processing %d video file(s) without GPS", total)
    updated = sum(_backfill_single_video(file, max_bytes) for file in files)
    result = f"backfill_video_gps: done — {updated}/{total} video(s) updated with GPS"
    log.info(result)
    return result


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def app_startup():
    log.info("app_startup")
    site_settings = SiteSettings.objects.settings()
    version_check.apply_async(countdown=5)
    cache.delete_pattern("*.decorators.cache.*")
    log.info("Flushed Template Cache")
    cache.set("site_settings", model_to_dict(site_settings))
    log.info("Created Cache: site_settings")
    if oauth_redirect_url := config("OAUTH_REDIRECT_URL", ""):
        site_settings.oauth_redirect_url = oauth_redirect_url
    if discord_client_id := config("DISCORD_CLIENT_ID", ""):
        site_settings.discord_client_id = discord_client_id
        site_settings.discord_client_secret = config("DISCORD_CLIENT_SECRET", "")
    if github_client_id := config("GITHUB_CLIENT_ID", ""):
        site_settings.github_client_id = github_client_id
        site_settings.github_client_secret = config("GITHUB_CLIENT_SECRET", "")
    if google_client_id := config("GOOGLE_CLIENT_ID", ""):
        site_settings.google_client_id = google_client_id
        site_settings.google_client_secret = config("GOOGLE_CLIENT_SECRET", "")
    if local_auth := config("LOCAL_AUTH", ""):
        site_settings.local_auth = bool(local_auth)
    site_settings.save()
    username = config("USERNAME", "")
    password = config("PASSWORD", "")
    if site_settings.get_local_auth() and username and password:
        user = CustomUser.objects.filter(username=username).first()
        if user:
            if not user.check_password(password):
                user.set_password(password)
                user.save()
                log.info("Password Ensured for user: %s", user.username)
        else:
            user = CustomUser.objects.create_superuser(username=username, password=password)
            log.info("Custom User Created: %s", user.username)
    CustomUser.objects.get_or_create(username="anonymous", first_name="Anonymous")
    os.makedirs(f"{settings.MEDIA_ROOT}/qr", exist_ok=True)
    regenerate_all_storage_values()
    refresh_gallery_static_urls_cache.delay()
    generate_thumbs.delay(only_missing=True)
    return "app_startup - finished"


@shared_task()
def version_check():
    log.info("version_check")
    try:
        app_version = config("APP_VERSION", "")
        if not app_version or app_version.lower() in ["dev", "latest"]:
            return "Skipping Version Check due to APP_VERSION not set or invalid."
        app_version = version.parse(app_version)
        log.info("app_version: %s", app_version)
        r = httpx.head(settings.VERSION_CHECK_URL, timeout=10)
        if r.status_code != 302:
            return "Error: Version Check URL Response did not return a 302."
        log.info("location: %s", r.headers["location"])
        latest_version = version.parse(os.path.basename(r.headers["location"]))
        log.info("latest_version: %s", latest_version)
        site_settings = SiteSettings.objects.settings()
        log.info("site_settings.latest_version: %s", site_settings.latest_version)
        if latest_version > app_version:
            if str(latest_version) != site_settings.latest_version:
                site_settings.latest_version = str(latest_version)
                site_settings.save()
                return f"New Update Found. Setting version to: {latest_version}"
            return f"New Update already set. latest_version: {latest_version}"
        else:
            if site_settings.latest_version:
                site_settings.latest_version = ""
                site_settings.save()
                return f"App Updated. Clearing latest_version: {latest_version}"
            return f"No Update Available. Current Version: {app_version}"
    except Exception as error:
        log.warning("Exception checking version: %s", error)


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 300})
def app_cleanup():
    log.info("app_cleanup")
    with open(settings.NGINX_ACCESS_LOGS, "a") as f:
        f.truncate(0)


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 10})
def flush_template_cache():
    log.info("flush_template_cache")
    return cache.delete_pattern("*.decorators.cache.*")


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 10})
def clear_files_cache():
    log.info("clear_files_cache")
    return cache.delete_pattern("*.files.*")


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 10})
def clear_albums_cache():
    log.info("clear_albums_cache")
    return cache.delete_pattern("*.albums.*")


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 10})
def clear_shorts_cache():
    log.info("clear_shorts_cache")
    return cache.delete_pattern("*.shorts.*")


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 10})
def clear_stats_cache():
    log.info("clear_stats_cache")
    return cache.delete_pattern("*.stats.*")


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 10})
def refresh_gallery_static_urls_cache():
    lock_key = "gallery_refresh"
    # Refresh cached gallery files to handle case where url signing expired
    file_count = 0
    if acquire_lock(lock_key, 1000):
        try:
            log.info("----- START gallery cache refresh -----")
            # any file that renders in a gallery: an image, or a file with a generated thumb (video/audio)
            files = Files.objects.filter(Q(mime__startswith="image/") | ~Q(thumb=""))
            for file in files:
                file.get_gallery_url()
                file_count += 1
            log.info("----- COMPLETE gallery cache refresh -----")
        except Exception:
            log.exception("Error populating gallery cache")
        finally:
            release_lock(lock_key)
    else:
        log.info("Gallery cache refresh task locked skipping run.")
    return f"Refreshed {file_count} gallery urls in cache."


@shared_task()
def delete_expired_files():
    log.info("delete_expired_files")
    now = timezone.now()
    files = Files.objects.exclude(expr="")
    deleted = 0
    for file in files:
        duration = parse(file.expr)
        if duration and (now - file.date).total_seconds() > duration:
            log.info("Deleting expired file: %s", file.file.name)
            file.delete()
            deleted += 1
    return f"Deleted: {deleted}"


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 2, "countdown": 30})
def process_stats():
    log.info("----- START process_stats -----")
    now = timezone.now()
    files = Files.objects.all()
    data = {"_totals": {"types": {}, "size": 0, "count": 0, "shorts": 0}}
    for file in files:
        if file.user_id not in data:
            data[file.user_id] = {"types": {}, "size": 0, "count": 0, "shorts": 0}

        for bucket in (data["_totals"], data[file.user_id]):
            bucket["count"] += 1
            bucket["size"] += file.size
            mime_bucket = bucket["types"].setdefault(file.mime, {"size": 0, "count": 0})
            mime_bucket["count"] += 1
            mime_bucket["size"] += file.size

    for user in CustomUser.objects.annotate(shorts_count=Count("shorturls")):
        if user.id not in data:
            data[user.id] = {"types": {}, "size": 0, "count": 0, "shorts": user.shorts_count}
        else:
            data[user.id]["shorts"] = user.shorts_count
        data["_totals"]["shorts"] += user.shorts_count

    for user_id, _data in data.items():
        _data["human_size"] = Files.get_size_of(_data["size"])
        real_user_id = None if str(user_id) == "_totals" else user_id
        log.info("user_id: %s data: %s", real_user_id, _data)
        stats = FileStats.objects.filter(user_id=real_user_id, created_at__date=now).first()
        if stats:
            stats.stats = _data
            stats.save()
        else:
            stats = FileStats.objects.create(user_id=real_user_id, stats=_data)
        log.info("stats.pk: %s", stats.pk)
    log.info("----- END process_stats -----")


@shared_task()
def new_file_websocket(pk):
    log.debug("new_file_websocket: %s", pk)
    file = Files.objects.get(pk=pk)
    log.debug("file: %s", file)
    data = extract_files([file])[0]
    log.debug("data: %s", data)
    # TODO: Backwards Compatibility
    data["pk"] = pk
    data["event"] = "file-new"
    # handle datetime obj to str
    data["date"] = str(data["date"])
    channel_layer = get_channel_layer()
    log.info("data: %s", data)
    event = {
        "type": "websocket.send",
        "text": json.dumps(data),
    }
    log.debug("event: %s", event)
    async_to_sync(channel_layer.group_send)(f"user-{file.user_id}", event)


@shared_task()
def delete_file_websocket(data: dict, user_id):
    log.debug("delete_file_websocket")
    log.debug("data: %s", data)
    log.debug("delete_file_websocket pk: %s user_id: %s", data["id"], user_id)
    data["event"] = "file-delete"
    data["pk"] = data["id"]
    user = CustomUser.objects.filter(pk=user_id).first()
    data["user_name"] = user.get_name() if user else str(user_id)
    channel_layer = get_channel_layer()
    event = {
        "type": "websocket.send",
        "text": json.dumps(data),
    }
    async_to_sync(channel_layer.group_send)(f"user-{user_id}", event)


@shared_task()
def update_file_websocket(data: dict, user_id: int, update_fields: Optional[list] = None):
    try:
        log.debug("update_file_websocket user_id: %s data: %s", user_id, data)
        log.debug("update_fields: %s", update_fields)
        data["event"] = "file-update"
        # if update_fields:
        data["update_fields"] = update_fields
        channel_layer = get_channel_layer()
        event = {
            "type": "websocket.send",
            "text": json.dumps(data),
        }
        async_to_sync(channel_layer.group_send)(f"user-{user_id}", event)

    except Exception as error:
        log.warning("tasks websocket error: %s", error)


@shared_task()
def update_album_websocket(data: dict, user_id: int, update_fields: Optional[list] = None):
    try:
        log.debug("update_album_websocket user_id: %s data: %s", user_id, data)
        log.debug("update_fields: %s", update_fields)
        data["event"] = "album-update"
        data["update_fields"] = update_fields
        channel_layer = get_channel_layer()
        event = {
            "type": "websocket.send",
            "text": json.dumps(data, default=str),
        }
        async_to_sync(channel_layer.group_send)(f"user-{user_id}", event)
    except Exception as error:
        log.warning("tasks websocket error: %s", error)


@shared_task()
def new_album_websocket(album):
    log.debug("new_album_websocket: %s", album)
    log.debug("album: %s", album)
    album["event"] = "album-new"
    # handle datetime obj to str
    album["date"] = str(album["date"])
    channel_layer = get_channel_layer()
    log.info("data: %s", album)
    event = {
        "type": "websocket.send",
        "text": json.dumps(album),
    }
    log.debug("event: %s", event)
    async_to_sync(channel_layer.group_send)(f"user-{album['user']}", event)


@shared_task()
def delete_album_websocket(data: dict, user_id):
    log.debug("delete_album_websocket")
    log.debug("data: %s", data)
    log.debug("delete_album_websocket pk: %s user_id: %s", data["id"], user_id)
    data["event"] = "album-delete"
    data["pk"] = data["id"]
    user = CustomUser.objects.filter(pk=user_id).first()
    data["user_name"] = user.get_name() if user else str(user_id)
    channel_layer = get_channel_layer()
    event = {
        "type": "websocket.send",
        "text": json.dumps(data),
    }
    async_to_sync(channel_layer.group_send)(f"user-{user_id}", event)


def _send_websocket_event(data: dict, group: str):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        log.error("channel layer not configured, dropping websocket event for group %s", group)
        return
    try:
        event = {"type": "websocket.send", "text": json.dumps(data)}
        async_to_sync(channel_layer.group_send)(group, event)
    except Exception:
        log.exception("websocket group_send failed for group %s", group)


@shared_task()
def file_album_websocket(data: dict, user_id: int):
    _send_websocket_event(data, f"user-{user_id}")


@shared_task()
def delete_stream_websocket(name: str, user_id: int):
    log.debug("delete_stream_websocket: name=%s user_id=%s", name, user_id)
    _send_websocket_event({"event": "stream-delete", "name": name}, f"user-{user_id}")


# @shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 1, "countdown": 300})
@shared_task()
def stream_status_websocket(stream_name: str, is_live: bool, ended_at: str = None, started_at: str = None):
    log.debug("stream_status_websocket: stream_name=%s is_live=%s", stream_name, is_live)
    data = {"event": "stream-status", "name": stream_name, "is_live": is_live}
    if ended_at:
        data["ended_at"] = ended_at
    if started_at:
        data["started_at"] = started_at
    _send_websocket_event(data, "home")


@shared_task()
def send_push_live(stream_name: str, ttl: int = 1800):
    stream = Stream.objects.get(name=stream_name)
    log.info("send_push_live: name: %s - user: %s", stream.name, stream.user.username)
    site_settings = SiteSettings.objects.settings()
    payload = {
        "head": f"{stream.user.username} went Live!",
        "body": stream.title,
        "icon": stream.user.get_avatar_url(),
        "url": f"{site_settings.site_url}/live/{stream.name}/",
    }
    log.info("payload: %s", payload)
    send_group_notification(group_name=stream.name, payload=payload, ttl=ttl)


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 6, "countdown": 30})
def send_discord_message(pk):
    log.info("send_discord_message: pk: %s", pk)
    file = Files.objects.filter(pk=pk).first()
    if not file:
        log.warning("send_discord_message: 404 File Not Found - pk: %s", pk)
        return f"404 File Not Found - pk: {pk}"
    webhooks = DiscordWebhooks.objects.filter(owner=file.user)
    context = {"file": file}
    message = render_to_string("message/new-file.html", context)
    log.info(message)
    for hook in webhooks:
        send_discord.delay(hook.id, message)


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 6, "countdown": 30})
def send_success_message(hook_pk):
    site_settings = SiteSettings.objects.settings()
    log.info("send_success_message: %s", hook_pk)
    context = {"site_url": site_settings.site_url}
    message = render_to_string("message/welcome.html", context)
    send_discord.delay(hook_pk, message)


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 5, "countdown": 60}, rate_limit="10/m")
def send_discord(hook_pk, message):
    log.info("send_discord: %s", hook_pk)
    try:
        webhook = DiscordWebhooks.objects.get(pk=hook_pk)
        body = {"content": message}
        log.debug("send_discord body: %s", body)
        r = httpx.post(webhook.url, json=body, timeout=30)
        if r.status_code == 404:
            log.warning("Hook %s removed by owner %s", webhook.hook_id, webhook.owner.username)
            webhook.delete()
            return 404
        if not r.is_success:
            log.warning(r.content.decode(r.encoding))
            r.raise_for_status()
        return r.status_code
    except Exception as error:
        log.exception(error)
        raise


def acquire_lock(key, timeout=900):
    log.debug("Checking lock for %s", key)
    if cache.get(key):
        log.debug("Found Lock")
        return False
    log.debug("Setting lock for %s", key)
    return cache.add(key, "1", timeout)


def release_lock(key):
    log.debug("Lock cleared on %s", key)
    cache.delete(key)


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    release_lock("gallery_refresh")
