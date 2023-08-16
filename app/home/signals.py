from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver

from home.tasks import clear_files_cache, clear_stats_cache, clear_shorts_cache, clear_settings_cache
from home.tasks import send_success_message
from home.models import Files, FileStats, SiteSettings, ShortURLs, Webhooks


@receiver(pre_delete, sender=Files)
def files_delete_signal(sender, instance, **kwargs):
    instance.file.delete(True)


@receiver(post_save, sender=Files)
@receiver(post_delete, sender=Files)
def clear_files_cache_signal(sender, instance, **kwargs):
    clear_files_cache.delay()


@receiver(post_save, sender=ShortURLs)
@receiver(post_delete, sender=ShortURLs)
def clear_shorts_cache_signal(sender, instance, **kwargs):
    clear_shorts_cache.delay()


@receiver(post_save, sender=FileStats)
def clear_stats_cache_signal(sender, instance, **kwargs):
    clear_stats_cache.delay()


@receiver(post_save, sender=Webhooks)
@receiver(post_delete, sender=Webhooks)
@receiver(post_save, sender=SiteSettings)
@receiver(post_delete, sender=SiteSettings)
def clear_settings_cache_signal(sender, instance, **kwargs):
    clear_settings_cache.delay()


@receiver(post_save, sender=Webhooks)
def send_success_message_signal(sender, instance, **kwargs):
    if kwargs.get('created'):
        send_success_message.delay(instance.id)
