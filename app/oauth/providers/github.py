import httpx
import logging
import urllib.parse
from decouple import config
from django.shortcuts import HttpResponseRedirect
from typing import Optional

from oauth.models import Github
from oauth.providers.helpers import is_super_id

provider = 'github'
log = logging.getLogger(f'app.{provider}')


class GithubOauth(object):
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
        self.username: Optional[str] = self.profile['login']
        self.first_name: Optional[str] = self.profile['name']

    def update_profile(self, user) -> None:
        if not getattr(user, provider, None):
            Github.objects.create(
                user=user,
                id=self.profile['id'],
            )
        log.debug('user.github: %s', user.github)
        user.github.profile = self.profile
        user.github.avatar = self.profile['avatar_url']
        user.github.access_token = self.data['access_token']
        user.github.save()
        if is_super_id(self.id):
            user.is_staff = True
            user.is_superuser = True
            user.save()

    @classmethod
    def redirect_login(cls, request) -> HttpResponseRedirect:
        request.session['oauth_provider'] = provider
        log.debug('request.session.oauth_provider: %s', request.session['oauth_provider'])
        if request.user.is_authenticated:
            request.session['oauth_claim_username'] = request.user.username
        params = {
            'redirect_uri': config('OAUTH_REDIRECT_URL'),
            'client_id': config('GITHUB_CLIENT_ID'),
            'response_type': config('OAUTH_RESPONSE_TYPE', 'code'),
            'scope': config('OAUTH_SCOPE', ''),
            'prompt': config('OAUTH_PROMPT', 'none'),
        }
        url_params = urllib.parse.urlencode(params)
        url = f'https://github.com/login/oauth/authorize?{url_params}'
        return HttpResponseRedirect(url)

    @classmethod
    def get_token(cls, code: str) -> dict:
        log.debug('get_token')
        url = 'https://github.com/login/oauth/access_token'
        data = {
            'redirect_uri': config('OAUTH_REDIRECT_URL'),
            'client_id': config('GITHUB_CLIENT_ID'),
            'client_secret': config('GITHUB_CLIENT_SECRET'),
            'grant_type': config('OAUTH_GRANT_TYPE', 'authorization_code'),
            'code': code,
        }
        headers = {'Accept': 'application/vnd.github+json'}
        r = httpx.post(url, data=data, headers=headers, timeout=10)
        if not r.is_success:
            log.debug('status_code: %s', r.status_code)
            log.error('content: %s', r.content)
            r.raise_for_status()
        return r.json()

    @classmethod
    def get_profile(cls, data: dict) -> dict:
        log.debug('get_discord_profile')
        url = 'https://api.github.com/user'
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {data['access_token']}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        r = httpx.get(url, headers=headers, timeout=10)
        if not r.is_success:
            log.debug('status_code: %s', r.status_code)
            log.error('content: %s', r.content)
            r.raise_for_status()
        log.debug('r.json(): %s', r.json())
        return r.json()
