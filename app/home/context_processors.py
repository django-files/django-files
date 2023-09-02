from home.models import SiteSettings
from django.core.cache import cache
from django.forms.models import model_to_dict


def site_settings(request):
    if (site_settings := cache.get('site_settings')) is None:
        site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
        cache.set('site_settings', model_to_dict(site_settings))
    return {'site_settings': site_settings}