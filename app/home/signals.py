import logging

from api.utils import extract_albums
from botocore.exceptions import ClientError
from celery.signals import worker_ready
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.forms.models import model_to_dict
from home.models import (
    Albums,
    AlbumTag,
    Files,
    FileStats,
    ShortURLs,
    Stream,
    Tag,
    Webhook,
)
from home.tasks import (
    app_startup,
    clear_albums_cache,
    clear_files_cache,
    clear_shorts_cache,
    clear_stats_cache,
    delete_album_websocket,
    delete_file_websocket,
    delete_stream_websocket,
    dispatch_webhook_event,
    fire_webhook,
    new_album_websocket,
    update_album_websocket,
    update_file_websocket,
)
from home.util.quota import decrement_storage_usage
from home.util.webhooks import (
    EVENT_ALBUM_CREATED,
    EVENT_ALBUM_DELETED,
    EVENT_ALBUM_UPDATED,
    EVENT_FILE_DELETED,
    EVENT_SHORT_CREATED,
    EVENT_SHORT_DELETED,
    EVENT_TEST,
    EVENT_USER_CREATED,
    EVENT_USER_DELETED,
    build_album_payload,
    build_file_payload,
    build_short_payload,
    build_test_payload,
    build_user_payload,
)
from oauth.models import CustomUser

log = logging.getLogger("app")


@worker_ready.connect
def run_startup_task(sender, **kwargs):
    app_startup.delay()


# must be registered (defined) before files_delete_signal: that receiver
# deletes the backing storage objects, which clears fields the payload needs
@receiver(pre_delete, sender=Files)
def files_delete_webhook_signal(sender, instance, **kwargs):
    try:
        dispatch_webhook_event.delay(EVENT_FILE_DELETED, instance.user_id, build_file_payload(instance))
    except Exception:
        log.exception("files_delete_webhook_signal failed")


@receiver(pre_delete, sender=Files)
def files_delete_signal(sender, instance, **kwargs):
    data = model_to_dict(instance, exclude=["file", "info", "exif", "date", "edit", "meta", "thumb", "albums"])
    try:
        decrement_storage_usage(instance.file.size, instance.user.pk)
    except ClientError, FileNotFoundError:
        # catch a case where file was removed from s3 but not our database
        # we should probably trigger a storage recalculation in this instance
        log.exception("Failed decrementing storage usage on delete of %s", instance.file.name)
    instance.thumb.delete(True)
    instance.file.delete(True)
    delete_file_websocket.apply_async(args=[data, instance.user.id], priority=0)


@receiver(post_save, sender=Files)
def files_post_save_signal(sender, instance, **kwargs):
    try:
        log.info("files_post_save_signal, %s, %s, %s", sender, instance, kwargs)
        # clear_files_cache.delay()
        data = model_to_dict(instance, exclude=["file", "info", "exif", "date", "edit", "meta", "thumb", "albums"])
        update_fields = list(kwargs["update_fields"]) if kwargs.get("update_fields") else []
        log.debug("update_fields: %s", update_fields)
        update_file_websocket.apply_async(args=[data, instance.user.id, update_fields], priority=0)
    except Exception:
        log.exception("files_post_save_signal failed")


@receiver(post_save, sender=Files)
@receiver(post_delete, sender=Files)
def clear_files_cache_signal(sender, instance, **kwargs):
    log.debug("clear_files_cache_signal")
    clear_files_cache.delay()


@receiver(post_save, sender=Albums)
def albums_post_save_signal(sender, instance, created, **kwargs):
    try:
        if created:
            # tags staged by the create API; they must be attached before the
            # payloads below are built or album.created would never match an
            # include tag filter
            for name in getattr(instance, "_pending_tags", []):
                AlbumTag.objects.get_or_create(album=instance, tag=Tag.objects.get_or_create_tag(name))
            data = extract_albums([instance])[0]
            new_album_websocket.apply_async(args=[data], priority=0)
        else:
            data = model_to_dict(instance)
            data["date"] = str(instance.date)
            data["user_name"] = instance.user.get_name()
            update_fields = list(kwargs["update_fields"]) if kwargs.get("update_fields") else []
            update_album_websocket.apply_async(args=[data, instance.user.id, update_fields], priority=0)
        event_key = EVENT_ALBUM_CREATED if created else EVENT_ALBUM_UPDATED
        dispatch_webhook_event.delay(event_key, instance.user_id, build_album_payload(instance))
    except Exception:
        log.exception("albums_post_save_signal failed")


@receiver(post_save, sender=Albums)
@receiver(post_delete, sender=Albums)
def clear_albums_cache_signal(sender, instance, **kwargs):
    clear_albums_cache.delay()


@receiver(pre_delete, sender=Albums)
def albums_delete_signal(sender, instance, **kwargs):
    data = model_to_dict(instance)
    delete_album_websocket.apply_async(args=[data, instance.user.id], priority=0)
    try:
        dispatch_webhook_event.delay(EVENT_ALBUM_DELETED, instance.user_id, build_album_payload(instance))
    except Exception:
        log.exception("albums_delete_signal webhook dispatch failed")


@receiver(pre_delete, sender=Stream)
def streams_delete_signal(sender, instance, **kwargs):
    delete_stream_websocket.apply_async(args=[instance.name, instance.user_id], priority=0)


@receiver(post_save, sender=ShortURLs)
@receiver(post_delete, sender=ShortURLs)
def clear_shorts_cache_signal(sender, instance, **kwargs):
    clear_shorts_cache.delay()


@receiver(post_save, sender=ShortURLs)
def shorts_created_signal(sender, instance, created, **kwargs):
    try:
        if created:
            dispatch_webhook_event.delay(EVENT_SHORT_CREATED, instance.user_id, build_short_payload(instance))
    except Exception:
        log.exception("shorts_created_signal failed")


@receiver(post_delete, sender=ShortURLs)
def shorts_deleted_signal(sender, instance, **kwargs):
    try:
        dispatch_webhook_event.delay(EVENT_SHORT_DELETED, instance.user_id, build_short_payload(instance))
    except Exception:
        log.exception("shorts_deleted_signal failed")


@receiver(post_save, sender=FileStats)
@receiver(post_delete, sender=FileStats)
def clear_stats_cache_signal(sender, instance, **kwargs):
    clear_stats_cache.delay()


@receiver(post_save, sender=Webhook)
def webhook_created_signal(sender, instance, created, **kwargs):
    if created and instance.webhook_type == Webhook.WEBHOOK_TYPE_DISCORD:
        fire_webhook.delay(instance.pk, EVENT_TEST, build_test_payload(instance))


@receiver(post_save, sender=CustomUser)
def user_created_signal(sender, instance, created, **kwargs):
    if created:
        dispatch_webhook_event.delay(EVENT_USER_CREATED, None, build_user_payload(instance))


@receiver(pre_delete, sender=CustomUser)
def user_deleted_signal(sender, instance, **kwargs):
    dispatch_webhook_event.delay(EVENT_USER_DELETED, None, build_user_payload(instance))
