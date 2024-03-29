import zoneinfo
from django.utils import timezone
from django.core.cache import cache
from django.forms.models import model_to_dict

from settings.models import SiteSettings


def site_settings_processor(request):
    site_settings = cache.get('site_settings')
    if not site_settings:
        site_settings = model_to_dict(SiteSettings.objects.settings())
    if request.user and request.user.is_authenticated and request.user.timezone:
        timezone.activate(zoneinfo.ZoneInfo(request.user.timezone))
    else:
        timezone.activate(zoneinfo.ZoneInfo(site_settings['timezone']))
    return {'site_settings': site_settings}
