from settings.models import SiteSettings
from django.core.cache import cache
from django.forms.models import model_to_dict


def site_settings_processor(request):
    site_settings = cache.get('site_settings')
    if not site_settings:
        site_settings = model_to_dict(SiteSettings.objects.settings())
    return {'site_settings': site_settings, 'latest_version': cache.get('latest_version')}
