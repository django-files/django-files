from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.forms.models import model_to_dict
from home.tasks import flush_template_cache
from settings.models import SiteSettings


@receiver(post_save, sender=SiteSettings)
@receiver(post_delete, sender=SiteSettings)
def clear_settings_cache_signal(sender, instance, **kwargs):
    cache.set("site_settings", model_to_dict(instance))
    flush_template_cache.delay()
