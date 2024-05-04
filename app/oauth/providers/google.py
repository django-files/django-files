import httpx
import logging
import urllib.parse
from decouple import config
from django.shortcuts import HttpResponseRedirect
from typing import Optional

from oauth.models import Google
from oauth.providers.helpers import is_super_id
from settings.models import SiteSettings

provider = 'google'
log = logging.getLogger(f'app.{provider}')


class GoogleOauth(object):
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

    def process_login(self) -> None:
        self.data = self.get_token(self.code)
        self.profile = self.get_profile(self.data)
        self.id: Optional[int] = self.profile['id']
        self.username: Optional[str] = self.profile['email']
        self.first_name: Optional[str] = self.profile['given_name']

    def update_profile(self, user) -> None:
        if not getattr(user, provider, None):
            Google.objects.create(
                user=user,
                id=self.profile['id'],
            )
        log.debug('user.google: %s', user.google)
        user.google.profile = self.profile
        user.google.avatar = self.profile.get('picture')
        user.google.access_token = self.data['access_token']
        user.google.save()
        if is_super_id(self.id):
            user.is_staff = True
            user.is_superuser = True
            user.save()

    @classmethod
    def redirect_login(cls, request) -> HttpResponseRedirect:
        request.session['oauth_provider'] = provider
        site_settings = SiteSettings.objects.settings()
        if request.user.is_authenticated:
            request.session['oauth_claim_username'] = request.user.username
        params = {
            'client_id': site_settings.google_client_id or config('GOOGLE_CLIENT_ID'),
            'redirect_uri': site_settings.oauth_redirect_url or config('OAUTH_REDIRECT_URL'),
            'scope': config('OAUTH_SCOPE', 'openid email profile'),
            'response_type': config('OAUTH_RESPONSE_TYPE', 'code'),
        }
        url_params = urllib.parse.urlencode(params)
        url = f'https://accounts.google.com/o/oauth2/v2/auth?{url_params}'
        return HttpResponseRedirect(url)

    @classmethod
    def get_token(cls, code: str) -> dict:
        log.debug('get_token')
        site_settings = SiteSettings.objects.settings()
        data = {
            'redirect_uri': site_settings.oauth_redirect_url or config('OAUTH_REDIRECT_URL'),
            'client_id': site_settings.google_client_id or config('GOOGLE_CLIENT_ID'),
            'client_secret': site_settings.google_client_secret or config('GOOGLE_CLIENT_SECRET'),
            'grant_type': config('OAUTH_GRANT_TYPE', 'authorization_code'),
            'code': code,
        }
        headers = {'Accept': 'application/json'}
        url = 'https://oauth2.googleapis.com/token'
        r = httpx.post(url, data=data, headers=headers, timeout=10)
        if not r.is_success:
            log.debug('status_code: %s', r.status_code)
            log.error('content: %s', r.content)
            r.raise_for_status()
        return r.json()

    @classmethod
    def get_profile(cls, data: dict) -> dict:
        log.debug('get_google_profile')
        url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {data['access_token']}",
        }
        r = httpx.get(url, headers=headers, timeout=10)
        if not r.is_success:
            log.debug('status_code: %s', r.status_code)
            log.error('content: %s', r.content)
            r.raise_for_status()
        log.debug('r.json(): %s', r.json())
        return r.json()
