import httpx
import logging
import urllib.parse
from datetime import datetime, timedelta
from decouple import config
from django.shortcuts import HttpResponseRedirect
from typing import Optional

from oauth.models import Discord
from oauth.providers.helpers import is_super_id
from settings.models import SiteSettings, Webhooks

provider = 'discord'
log = logging.getLogger(f'app.{provider}')


class DiscordOauth(object):
    api_url = 'https://discord.com/api/v8/'

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
        self.username: Optional[str] = self.profile['username']
        self.first_name: Optional[str] = self.profile['global_name']

    def update_profile(self, user) -> None:
        if not getattr(user, provider, None):
            Discord.objects.create(
                user=user,
                id=self.profile['id'],
            )
        log.debug('user.discord: %s', user.discord)
        user.discord.profile = self.profile
        user.discord.avatar = self.profile['avatar']
        user.discord.access_token = self.data['access_token']
        user.discord.refresh_token = self.data['refresh_token']
        user.discord.expires_in = datetime.now() + timedelta(0, self.data['expires_in'])
        user.discord.save()
        if is_super_id(self.id):
            user.is_staff = True
            user.is_superuser = True
            user.save()

    def add_webhook(self, request) -> Webhooks:
        return Webhooks.objects.create(
            hook_id=self.data['webhook']['id'],
            guild_id=self.data['webhook']['guild_id'],
            channel_id=self.data['webhook']['channel_id'],
            url=self.data['webhook']['url'],
            owner=request.user,
        )

    @classmethod
    def redirect_login(cls, request) -> HttpResponseRedirect:
        request.session['oauth_provider'] = provider
        site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
        if request.user.is_authenticated:
            request.session['oauth_claim_username'] = request.user.username
        params = {
            'redirect_uri': site_settings.oauth_redirect_url or config('OAUTH_REDIRECT_URL'),
            'client_id': site_settings.discord_client_id or config('DISCORD_CLIENT_ID'),
            'response_type': config('OAUTH_RESPONSE_TYPE', 'code'),
            'scope': config('OAUTH_SCOPE', 'identify'),
            'prompt': config('OAUTH_PROMPT', 'none'),
        }
        url_params = urllib.parse.urlencode(params)
        url = f'{cls.api_url}/oauth2/authorize?{url_params}'
        return HttpResponseRedirect(url)

    @classmethod
    def redirect_webhook(cls, request) -> HttpResponseRedirect:
        request.session['oauth_provider'] = provider
        request.session['webhook'] = 'discord'
        site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
        params = {
            'redirect_uri': site_settings.oauth_redirect_url or config('OAUTH_REDIRECT_URL'),
            'client_id': site_settings.discord_client_id or config('DISCORD_CLIENT_ID'),
            'response_type': config('OAUTH_RESPONSE_TYPE', 'code'),
            'scope': config('OAUTH_SCOPE', 'identify') + ' webhook.incoming',
        }
        url_params = urllib.parse.urlencode(params)
        url = f'{cls.api_url}/oauth2/authorize?{url_params}'
        return HttpResponseRedirect(url)

    @classmethod
    def get_token(cls, code: str) -> dict:
        log.debug('get_token')
        site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
        data = {
            'redirect_uri': site_settings.oauth_redirect_url or config('OAUTH_REDIRECT_URL'),
            'client_id': site_settings.discord_client_id or config('DISCORD_CLIENT_ID'),
            'client_secret': site_settings.discord_client_secret or config('DISCORD_CLIENT_SECRET'),
            'grant_type': config('OAUTH_GRANT_TYPE', 'authorization_code'),
            'code': code,
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        url = f'{cls.api_url}/oauth2/token'
        r = httpx.post(url, data=data, headers=headers, timeout=10)
        if not r.is_success:
            log.debug('status_code: %s', r.status_code)
            log.error('content: %s', r.content)
            r.raise_for_status()
        return r.json()

    @classmethod
    def get_profile(cls, data: dict) -> dict:
        log.debug('get_discord_profile')
        url = f'{cls.api_url}/users/@me'
        headers = {'Authorization': f"Bearer {data['access_token']}"}
        r = httpx.get(url, headers=headers, timeout=10)
        if not r.is_success:
            log.debug('status_code: %s', r.status_code)
            log.error('content: %s', r.content)
            r.raise_for_status()
        log.debug('r.json(): %s', r.json())
        return r.json()
