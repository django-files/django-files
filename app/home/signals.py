from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver

from .tasks import clear_home_cache, clear_settings_cache, send_success_message
from .models import Files, Webhooks


@receiver(pre_delete, sender=Files)
def files_delete_signal(sender, instance, **kwargs):
    instance.file.delete(True)


@receiver(post_save, sender=Files)
@receiver(post_delete, sender=Files)
def clear_home_cache_signal(sender, instance, **kwargs):
    clear_home_cache.delay()


@receiver(post_save, sender=Webhooks)
@receiver(post_delete, sender=Webhooks)
def clear_settings_cache_signal(sender, instance, **kwargs):
    clear_settings_cache.delay()


@receiver(post_save, sender=Webhooks)
def send_success_message_signal(sender, instance, **kwargs):
    if 'created' in kwargs and kwargs['created']:
        send_success_message.delay(instance.id)
