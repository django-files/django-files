import logging
from celery.signals import worker_ready
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.forms.models import model_to_dict
from botocore.exceptions import ClientError

from home.tasks import clear_files_cache, clear_stats_cache, clear_shorts_cache, clear_albums_cache, app_startup, \
    delete_file_websocket, send_success_message, delete_album_websocket, update_file_websocket
from home.models import Files, FileStats, ShortURLs, Albums
from oauth.models import DiscordWebhooks
from home.util.quota import decrement_storage_usage

log = logging.getLogger('app')


@worker_ready.connect
def run_startup_task(sender, **kwargs):
    app_startup.delay()


@receiver(pre_delete, sender=Files)
def files_delete_signal(sender, instance, **kwargs):
    data = model_to_dict(instance, exclude=['file', 'info', 'exif', 'date', 'edit', 'meta', 'thumb', 'albums'])
    try:
        decrement_storage_usage(instance.file.size, instance.user.pk)
    except (ClientError, FileNotFoundError):
        # catch a case where file was removed from s3 but not our database
        # we should probably trigger a storage recalculation in this instance
        log.error(f"Failed decrementing storage usage on delete of {instance.file.name}.")
    instance.thumb.delete(True)
    instance.file.delete(True)
    delete_file_websocket.apply_async(args=[data, instance.user.id], priority=0)


@receiver(post_save, sender=Files)
def files_post_save_signal(sender, instance, **kwargs):
    try:
        log.info('files_post_save_signal, %s, %s, %s', sender, instance, kwargs)
        # clear_files_cache.delay()
        data = model_to_dict(instance, exclude=['file', 'info', 'exif', 'date', 'edit', 'meta', 'thumb', 'albums'])
        update_fields = list(kwargs['update_fields'])
        log.debug('update_fields: %s', update_fields)
        update_file_websocket.apply_async(args=[data, instance.user.id, update_fields], priority=0)
    except Exception as error:
        log.warning('ERROR: %s', error)


@receiver(post_save, sender=Files)
@receiver(post_delete, sender=Files)
def clear_files_cache_signal(sender, instance, **kwargs):
    log.debug('clear_files_cache_signal')
    clear_files_cache.delay()


@receiver(post_save, sender=Albums)
@receiver(post_delete, sender=Albums)
def clear_albums_cache_signal(sender, instance, **kwargs):
    clear_albums_cache.delay()


@receiver(pre_delete, sender=Albums)
def albums_delete_signal(sender, instance, **kwargs):
    data = model_to_dict(instance)
    delete_album_websocket.apply_async(args=[data, instance.user.id], priority=0)


@receiver(post_save, sender=ShortURLs)
@receiver(post_delete, sender=ShortURLs)
def clear_shorts_cache_signal(sender, instance, **kwargs):
    clear_shorts_cache.delay()


@receiver(post_save, sender=FileStats)
@receiver(post_delete, sender=FileStats)
def clear_stats_cache_signal(sender, instance, **kwargs):
    clear_stats_cache.delay()


@receiver(post_save, sender=DiscordWebhooks)
def send_success_message_signal(sender, instance, **kwargs):
    if kwargs.get('created'):
        send_success_message.delay(instance.id)
