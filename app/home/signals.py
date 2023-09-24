from celery.signals import worker_ready
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.forms.models import model_to_dict

from home.tasks import clear_files_cache, clear_stats_cache, clear_shorts_cache
from home.tasks import app_startup, delete_file_websocket, send_success_message
from home.models import Files, FileStats, ShortURLs
from oauth.models import DiscordWebhooks


@worker_ready.connect
def run_startup_task(sender, **kwargs):
    app_startup.delay()


@receiver(pre_delete, sender=Files)
def files_delete_signal(sender, instance, **kwargs):
    data = model_to_dict(instance, exclude=['file', 'info', 'exif', 'date', 'edit', 'meta'])
    instance.file.delete(True)
    delete_file_websocket.delay(data, instance.user.id)


@receiver(post_save, sender=Files)
@receiver(post_delete, sender=Files)
def clear_files_cache_signal(sender, instance, **kwargs):
    clear_files_cache.delay()


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
