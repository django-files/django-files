import json
import logging
import os
import tempfile
from datetime import datetime
from datetime import timezone as dt_timezone
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
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django_redis import get_redis_connection
from home.models import Files, FileStats, Stream, StreamHistory, Webhook
from home.util.image import thumbnail_processor
from home.util.quota import regenerate_all_storage_values
from home.util.stream_record import delete_recording_file, validate_recording_path
from home.util.tags import sync_file_tags
from home.util.video import (
    remux_to_mp4,
    video_metadata_processor,
    video_thumbnail_processor,
)
from home.util.webhooks import (
    EVENT_STREAM_RECORDING_READY,
    SITE_ONLY_EVENTS,
    build_stream_recording_payload,
    event_matches_filters,
    send_webhook,
)
from oauth.models import ApiToken, CustomUser
from packaging import version
from PIL import Image, UnidentifiedImageError
from pytimeparse2 import parse
from settings.models import SiteSettings
from webpush import send_group_notification

log = logging.getLogger("app")

VIDEO_MIME_PREFIX = "video/"


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 10, "countdown": 1})
def app_init():
    log.info("app_init")
    # Only seed an admin when USERNAME/PASSWORD are explicitly configured (for
    # headless/automated deploys). With no config, leave the DB admin-less so the
    # first-run setup wizard creates the initial superuser. Never fall back to
    # default credentials -- that shipped a known admin/12345 on every deploy.
    username = config("USERNAME", "")
    password = config("PASSWORD", "")
    if username and password:
        if not CustomUser.objects.filter(username=username).exists():
            CustomUser.objects.create_superuser(username=username, password=password)
            log.info("Initial User Created: %s", username)
        else:
            log.info("User already exists, skipping: %s", username)
    return "app_init - finished"


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def generate_thumbs(user_pk: int = None, only_missing: bool = True):
    log.info("Generating Thumbnails - only_missing: %s - user_pk: %s", only_missing, user_pk)
    user_filter = Q(user_id=user_pk) if user_pk else Q()
    # Formats Pillow cannot reliably thumbnail. DNG is TIFF-based so libmagic
    # may report image/tiff; exclude by extension as well to catch that case.
    thumb_exclude = Q(mime__in=["image/jxl", "image/x-adobe-dng"]) | Q(name__iendswith=".dng")

    files = Files.objects.filter(user_filter, mime__startswith="image/").exclude(thumb_exclude)
    if only_missing:
        files = files.filter(thumb__in=[None, ""])
    processed = 0
    for file in files.iterator(chunk_size=100):
        processed += 1
        log.info("Generating thumbnail for: %s", file.name)
        try:
            thumbnail_processor(file)
        except ValueError, UnidentifiedImageError, FileNotFoundError, Image.DecompressionBombError:
            # if we hit a file that cannot be processed or is missing from storage ignore and continue
            log.error("Unable to process thumbnail for %s", file.name)
    log.info("Processed thumbnails for %d objects", processed)

    # Queue a separate task per video so they run in parallel and each gets
    # its own retry budget; generate_video_thumb checks for an existing thumb
    # before doing any work so re-queuing in-flight files is safe.
    videos = Files.objects.filter(user_filter, mime__startswith=VIDEO_MIME_PREFIX)
    if only_missing:
        videos = videos.filter(thumb__in=[None, ""])
    queued = 0
    for pk in videos.values_list("pk", flat=True).iterator(chunk_size=500):
        generate_video_thumb.delay(pk)
        queued += 1
    log.info("Queued video thumbnails for %d files", queued)


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
        sync_file_tags(file)
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


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def app_startup():
    log.info("app_startup")
    site_settings = SiteSettings.objects.settings()
    version_check.apply_async(countdown=5)
    cache.delete_pattern("*.decorators.cache.*")
    log.info("Flushed Template Cache")
    # site_settings cache is set by the SiteSettings post_save signal when the
    # unconditional save() below runs, so no explicit cache.set is needed here.
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
    except Exception:
        log.exception("Exception checking version")


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
    file_count = 0
    if not acquire_lock(lock_key, 1000):
        log.info("Gallery cache refresh task locked, skipping run.")
        return "Skipped — already running."
    try:
        log.info("----- START gallery cache refresh -----")
        # any file that renders in a gallery: an image, or a file with a generated thumb (video/audio)
        qs = Files.objects.filter(Q(mime__startswith="image/") | ~Q(thumb=""))
        for file in qs.iterator(chunk_size=500):
            file.get_gallery_url()
            file_count += 1
        log.info("----- COMPLETE gallery cache refresh -----")
    except Exception:
        log.exception("Error populating gallery cache")
    finally:
        release_lock(lock_key)
    return f"Refreshed {file_count} gallery urls in cache."


@shared_task()
def delete_expired_files():
    log.info("delete_expired_files")
    now = timezone.now()
    deleted = 0
    for file in Files.objects.exclude(expr="").iterator():
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
    data = {"_totals": {"types": {}, "size": 0, "count": 0, "shorts": 0}}

    # Single GROUP BY query instead of loading every file row into Python
    for row in Files.objects.values("user_id", "mime").annotate(count=Count("id"), total_size=Sum("size")):
        uid = row["user_id"]
        mime = row["mime"]
        count = row["count"]
        size = row["total_size"] or 0

        if uid not in data:
            data[uid] = {"types": {}, "size": 0, "count": 0, "shorts": 0}

        for bucket in (data["_totals"], data[uid]):
            bucket["count"] += count
            bucket["size"] += size
            mime_bucket = bucket["types"].setdefault(mime, {"size": 0, "count": 0})
            mime_bucket["count"] += count
            mime_bucket["size"] += size

    for user in CustomUser.objects.annotate(shorts_count=Count("shorturls")):
        if user.id not in data:
            data[user.id] = {"types": {}, "size": 0, "count": 0, "shorts": user.shorts_count}
        else:
            data[user.id]["shorts"] = user.shorts_count
        data["_totals"]["shorts"] += user.shorts_count

    for user_id, _data in data.items():
        if user_id is None:
            # Orphaned files (no user) — already counted in _totals, skip
            continue
        _data["human_size"] = Files.get_size_of(_data["size"])
        real_user_id = None if user_id == "_totals" else user_id
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
    file = Files.objects.filter(pk=pk).first()
    if not file:
        log.warning("new_file_websocket: pk=%s not found, skipping", pk)
        return
    log.debug("file: %s", file)
    data = extract_files([file])[0]
    log.debug("data: %s", data)
    # TODO: Backwards Compatibility
    data["pk"] = pk
    data["event"] = "file-new"
    # handle datetime obj to str
    data["date"] = str(data["date"])
    _send_websocket_event(data, f"user-{file.user_id}")


@shared_task()
def delete_file_websocket(data: dict, user_id):
    log.debug("delete_file_websocket")
    log.debug("data: %s", data)
    log.debug("delete_file_websocket pk: %s user_id: %s", data["id"], user_id)
    data["event"] = "file-delete"
    data["pk"] = data["id"]
    user = CustomUser.objects.filter(pk=user_id).first()
    data["user_name"] = user.get_name() if user else str(user_id)
    _send_websocket_event(data, f"user-{user_id}")


@shared_task()
def update_file_websocket(data: dict, user_id: int, update_fields: Optional[list] = None):
    log.debug("update_file_websocket user_id: %s data: %s", user_id, data)
    log.debug("update_fields: %s", update_fields)
    data["event"] = "file-update"
    data["update_fields"] = update_fields
    _send_websocket_event(data, f"user-{user_id}")


@shared_task()
def update_album_websocket(data: dict, user_id: int, update_fields: Optional[list] = None):
    log.debug("update_album_websocket user_id: %s data: %s", user_id, data)
    log.debug("update_fields: %s", update_fields)
    data["event"] = "album-update"
    data["update_fields"] = update_fields
    _send_websocket_event(data, f"user-{user_id}", default=str)


@shared_task()
def new_album_websocket(album):
    log.debug("new_album_websocket: %s", album)
    album["event"] = "album-new"
    # handle datetime obj to str
    album["date"] = str(album["date"])
    _send_websocket_event(album, f"user-{album['user']}")


@shared_task()
def delete_album_websocket(data: dict, user_id):
    log.debug("delete_album_websocket")
    log.debug("data: %s", data)
    log.debug("delete_album_websocket pk: %s user_id: %s", data["id"], user_id)
    data["event"] = "album-delete"
    data["pk"] = data["id"]
    user = CustomUser.objects.filter(pk=user_id).first()
    data["user_name"] = user.get_name() if user else str(user_id)
    _send_websocket_event(data, f"user-{user_id}")


def _send_websocket_event(data: dict, group: str, default=None):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        log.error("channel layer not configured, dropping websocket event for group %s", group)
        return
    try:
        event = {"type": "websocket.send", "text": json.dumps(data, default=default)}
        async_to_sync(channel_layer.group_send)(group, event)
    except Exception:
        log.exception("websocket group_send failed for group %s", group)


@shared_task()
def file_album_websocket(data: dict, user_id: int):
    _send_websocket_event(data, f"user-{user_id}")


@shared_task()
def file_tag_websocket(data: dict, user_id: int):
    _send_websocket_event(data, f"user-{user_id}")


@shared_task()
def album_tag_websocket(data: dict, user_id: int):
    _send_websocket_event(data, f"user-{user_id}")


@shared_task()
def stream_tag_websocket(data: dict, user_id: int):
    _send_websocket_event(data, f"user-{user_id}")


@shared_task()
def delete_stream_websocket(name: str, user_id: int):
    log.debug("delete_stream_websocket: name=%s user_id=%s", name, user_id)
    _send_websocket_event({"event": "stream-delete", "name": name}, f"user-{user_id}")


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
    stream = Stream.objects.filter(name=stream_name).first()
    if not stream:
        log.warning("send_push_live: stream %s not found, skipping", stream_name)
        return
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


@shared_task()
def import_stream_recording(history_pk: int, path: str):
    """
    Remux a finished stream recording (FLV, written by nginx-rtmp's `record all;`
    to the shared media_dir volume) into an MP4 and import it as a Files object,
    then link it to the StreamHistory row for that session.

    Deliberately no retries: the finally block always deletes the source
    recording (media_dir is a persistent volume; leftovers would accumulate
    forever), so a retry would find the file already gone.

    process_file is imported locally to avoid a circular import: home.util.file
    imports from home.tasks at module load time.
    """
    from home.util.file import LocalFile, process_file

    log.info("import_stream_recording: history_pk=%s path=%s", history_pk, path)
    try:
        history = StreamHistory.objects.select_related("stream", "stream__user").get(pk=history_pk)
    except StreamHistory.DoesNotExist:
        log.warning("import_stream_recording: history_pk=%s not found, discarding %s", history_pk, path)
        delete_recording_file(path)
        return

    resolved = validate_recording_path(path)
    if not resolved or not os.path.isfile(resolved):
        log.warning("import_stream_recording: invalid or missing recording path: %s", path)
        return

    stream = history.stream
    mp4_path = os.path.splitext(resolved)[0] + ".mp4"
    try:
        remux_to_mp4(resolved, mp4_path)
        name = f"{stream.name}-{history.started_at:%Y%m%d-%H%M%S}.mp4"
        # Age-based expiry rides the existing Files.expr / delete_expired_files
        # mechanism (same as any other upload) instead of a second cleanup path.
        expr = f"{stream.recording_retention_days}d" if stream.recording_retention_days else ""
        # LocalFile lets process_file consume the mp4 in place instead of
        # copying a multi-GB recording to a second temp file first; the
        # finally block below still owns cleanup of mp4_path.
        recording = process_file(name, LocalFile(mp4_path), stream.user_id, expr=expr)
        history.recording = recording
        history.save()
        dispatch_webhook_event.delay(
            EVENT_STREAM_RECORDING_READY, stream.user_id, build_stream_recording_payload(history)
        )
    finally:
        delete_recording_file(resolved)
        if os.path.exists(mp4_path):
            os.remove(mp4_path)


@shared_task()
def enforce_stream_retention(stream_name: str = None):
    """
    Delete recording Files beyond a stream's recording_retention_count, keeping
    only the N most recent. Age-based expiry isn't handled here — it's set as
    Files.expr at import time and enforced by the existing delete_expired_files
    task, the same path every other upload's expiration goes through.
    """
    streams = Stream.objects.filter(name=stream_name) if stream_name else Stream.objects.all()
    for stream in streams.iterator():
        if not stream.recording_retention_count:
            continue
        history_qs = StreamHistory.objects.filter(stream=stream, recording__isnull=False).order_by("-started_at")
        keep_pks = set(history_qs.values_list("pk", flat=True)[: stream.recording_retention_count])
        to_delete = history_qs.exclude(pk__in=keep_pks)
        for history in to_delete.select_related("recording"):
            log.info("enforce_stream_retention: stream=%s deleting recording history_pk=%s", stream.name, history.pk)
            if history.recording:
                history.recording.delete()


@shared_task()
def dispatch_webhook_event(event_key, owner_pk, payload_data):
    """Fan an event out to all subscribed webhooks.

    Site-scoped webhooks (staff-owned) receive events for all users. User-scoped
    webhooks only receive events for their owner's actions, and never the
    SITE_ONLY_EVENTS (owner_pk is None when those are dispatched). Event
    membership is checked in Python because JSONField __contains is not
    supported on SQLite.
    """
    log.info("dispatch_webhook_event: %s owner=%s", event_key, owner_pk)
    query = Q(scope=Webhook.SCOPE_SITE, owner__is_staff=True)
    if event_key not in SITE_ONLY_EVENTS and owner_pk is not None:
        query |= Q(scope=Webhook.SCOPE_USER, owner_id=owner_pk)
    for webhook in Webhook.objects.filter(query, active=True):
        if event_key in webhook.events and event_matches_filters(event_key, webhook.filters, payload_data):
            fire_webhook.delay(webhook.pk, event_key, payload_data)


@shared_task(bind=True, max_retries=6)
def fire_webhook(self, webhook_pk, event_key, payload_data):
    log.info("fire_webhook: pk=%s event=%s", webhook_pk, event_key)
    webhook = Webhook.objects.filter(pk=webhook_pk, active=True).first()
    if not webhook:
        log.warning("fire_webhook: webhook %s not found or inactive", webhook_pk)
        return
    try:
        r = send_webhook(webhook, event_key, payload_data)
    except httpx.HTTPError as error:
        log.warning("fire_webhook: %s - %s", webhook_pk, error)
        raise self.retry(countdown=30) from error
    if r.is_success:
        return r.status_code
    log.warning("fire_webhook: %s returned %s: %s", webhook.url, r.status_code, r.text[:256])
    if webhook.webhook_type == Webhook.WEBHOOK_TYPE_DISCORD and r.status_code in (404, 410):
        log.warning("Hook %s removed by owner %s", webhook_pk, webhook.owner.username)
        webhook.delete()
        return r.status_code
    if self.request.retries >= self.max_retries:
        if webhook.webhook_type == Webhook.WEBHOOK_TYPE_CUSTOM:
            log.warning("fire_webhook: deactivating webhook %s after max retries", webhook_pk)
            webhook.active = False
            webhook.save(update_fields=["active"])
        return r.status_code
    raise self.retry(countdown=30)


def acquire_lock(key, timeout=900):
    # cache.add is atomic: returns False if the key already exists
    log.debug("Acquiring lock for %s", key)
    return cache.add(key, "1", timeout)


def release_lock(key):
    log.debug("Lock cleared on %s", key)
    cache.delete(key)


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    release_lock("gallery_refresh")


@shared_task
def flush_token_last_used():
    """Write buffered last_used_at values from Redis to the ApiToken table."""
    redis = get_redis_connection("default")
    pipe = redis.pipeline()
    pipe.hgetall("token_last_used")
    pipe.delete("token_last_used")
    data, _ = pipe.execute()
    if not data:
        return

    updates = []
    for pk_bytes, ts_bytes in data.items():
        ts = datetime.fromtimestamp(float(ts_bytes), tz=dt_timezone.utc)
        updates.append(ApiToken(pk=pk_bytes.decode(), last_used_at=ts))
    if updates:
        ApiToken.objects.bulk_update(updates, ["last_used_at"])
