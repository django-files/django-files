import httpx
import logging
import urllib.parse
from datetime import datetime, timedelta
from decouple import config
from django.shortcuts import HttpResponseRedirect
from typing import Optional

from oauth.models import Discord

log = logging.getLogger('app')


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

    def __init__(self, code: str):
        self.code = code
        self.id: Optional[int] = None
        self.username: Optional[str] = None
        self.first_name: Optional[str] = None
        self.data: Optional[dict] = None
        self.profile: Optional[dict] = None

    def process_login(self):
        self.data = self.get_token(self.code)
        self.profile = self.get_profile(self.data)
        self.id: Optional[int] = self.profile['id']
        self.username: Optional[str] = self.profile['username']
        self.first_name: Optional[str] = self.profile['global_name']

    def update_profile(self, user):
        if not getattr(user, 'discord', None):
            Discord.objects.create(
                user=user,
                id=self.profile['id'],
            )
        log.debug('user.discord: %s', user.discord)
        user.discord.profile = self.profile,
        user.discord.avatar = self.profile['avatar'],
        user.discord.access_token = self.data['access_token'],
        user.discord.refresh_token = self.data['refresh_token'],
        user.discord.expires_in = datetime.now() + timedelta(0, self.data['expires_in']),
        user.save()

    @classmethod
    def redirect_login(cls, request) -> HttpResponseRedirect:
        request.session['oauth_provider'] = 'discord'
        if request.user.is_authenticated:
            request.session['oauth_claim_username'] = request.user.username
        params = {
            'redirect_uri': config('OAUTH_REDIRECT_URL'),
            'client_id': config('DISCORD_CLIENT_ID'),
            'response_type': config('OAUTH_RESPONSE_TYPE', 'code'),
            'scope': config('OAUTH_SCOPE', 'identify'),
            'prompt': config('OAUTH_PROMPT', 'none'),
        }
        url_params = urllib.parse.urlencode(params)
        url = f'{cls.api_url}/oauth2/authorize?{url_params}'
        return HttpResponseRedirect(url)

    @classmethod
    def redirect_webhook(cls, request) -> HttpResponseRedirect:
        request.session['oauth_provider'] = 'discord'
        params = {
            'redirect_uri': config('OAUTH_REDIRECT_URL'),
            'client_id': config('DISCORD_CLIENT_ID'),
            'response_type': config('OAUTH_RESPONSE_TYPE', 'code'),
            'scope': config('OAUTH_SCOPE', 'identify') + ' webhook.incoming',
        }
        url_params = urllib.parse.urlencode(params)
        url = f'{cls.api_url}/oauth2/authorize?{url_params}'
        return HttpResponseRedirect(url)

    @classmethod
    def get_token(cls, code: str) -> dict:
        log.debug('get_token')
        url = f'{cls.api_url}/oauth2/token'
        data = {
            'redirect_uri': config('OAUTH_REDIRECT_URL'),
            'client_id': config('DISCORD_CLIENT_ID'),
            'client_secret': config('DISCORD_CLIENT_SECRET'),
            'grant_type': config('OAUTH_GRANT_TYPE', 'authorization_code'),
            'code': code,
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
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
