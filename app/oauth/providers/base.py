from typing import Optional

from settings.models import SiteSettings


class BaseOauth(object):
    site_settings = SiteSettings.objects.settings()
    redirect_url = site_settings.get_oauth_redirect_url()

    __slots__ = [
        'code',
        'id',
        'username',
        'first_name',
        'data',
        'profile',
    ]

    def __init__(self, code: str) -> None:
        self.code = code
        self.id: Optional[int] = None
        self.username: Optional[str] = None
        self.first_name: Optional[str] = None
        self.data: Optional[dict] = None
        self.profile: Optional[dict] = None
