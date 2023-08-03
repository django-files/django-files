from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver

from .tasks import clear_files_cache, send_success_message
from .models import Files, Webhooks


@receiver(pre_delete, sender=Files)
def files_delete_signal(sender, instance, **kwargs):
    instance.file.delete(True)


@receiver(post_save, sender=Files)
@receiver(post_delete, sender=Files)
def clear_files_cache_signal(sender, instance, **kwargs):
    clear_files_cache.delay()


# # Not Implemented
# @receiver(post_save, sender=SiteSettings)
# @receiver(post_delete, sender=SiteSettings)
# def clear_settings_cache_signal(sender, instance, **kwargs):
#     clear_settings_cache.delay()


@receiver(post_save, sender=Webhooks)
def send_success_message_signal(sender, instance, **kwargs):
    if 'created' in kwargs and kwargs['created']:
        send_success_message.delay(instance.id)
