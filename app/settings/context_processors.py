import zoneinfo

from django.conf import settings
from django.core.cache import cache
from django.forms.models import model_to_dict
from django.utils import timezone
from settings.models import SiteSettings


def site_settings_processor(request):
    site_settings = cache.get("site_settings")
    if not site_settings:
        site_settings = model_to_dict(SiteSettings.objects.settings())
        cache.set("site_settings", site_settings)
    if request is not None and hasattr(request, "user") and request.user.is_authenticated and request.user.timezone:
        timezone.activate(zoneinfo.ZoneInfo(request.user.timezone))
    else:
        timezone.activate(zoneinfo.ZoneInfo(site_settings["timezone"]))
    # Default so templates extending main.html (login, error pages, etc.) can use
    # {% if native_app_arg %} without raising VariableDoesNotExist. Views that build
    # a real deep-link override this in their own context.
    return {
        "site_settings": site_settings,
        "native_app_arg": None,
        "upload_max_size": settings.UPLOAD_MAX_SIZE,
        "tus_enabled": settings.TUS_ENABLED,
    }
