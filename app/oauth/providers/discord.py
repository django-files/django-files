import httpx
import logging
import urllib.parse
from datetime import datetime, timedelta
from decouple import config
from django.http import HttpRequest
from django.shortcuts import HttpResponseRedirect
from oauth.providers.helpers import get_next_url

log = logging.getLogger('app')


class DiscordOauth(object):
    api_url = 'https://discord.com/api/v8/'

    __slots__ = [
        'token_resp',
        'user_resp',
        'profile',
    ]

    @classmethod
    def process_code(cls, code: str):
        cls.token_resp = cls.get_token(code)
        cls.user_resp = cls.get_profile(cls.token_resp)
        cls.profile = {
            'oauth_id': cls.user_resp['id'],
            'username': cls.user_resp['username'],
            'discord_avatar': cls.user_resp['avatar'],
            'access_token': cls.token_resp['access_token'],
            'refresh_token': cls.token_resp['refresh_token'],
            'expires_in': datetime.now() + timedelta(0, cls.token_resp['expires_in']),
        }

    @classmethod
    def redirect_login(cls, request: HttpRequest) -> HttpResponseRedirect:
        request.session['oauth_provider'] = 'discord'
        request.session['login_redirect_url'] = get_next_url(request)
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
        return HttpResponseRedirect(f'{cls.api_url}/oauth2/authorize?{url_params}')

    @classmethod
    def redirect_webhook(cls, request: HttpRequest) -> HttpResponseRedirect:
        request.session['oauth_provider'] = 'discord'
        request.session['login_redirect_url'] = get_next_url(request)
        log.debug('oauth_webhook: login_redirect_url: %s', request.session.get('login_redirect_url'))
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
        log.debug('get_discord_access_token')
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
            log.info('status_code: %s', r.status_code)
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
            log.info('status_code: %s', r.status_code)
            log.error('content: %s', r.content)
            r.raise_for_status()
        log.debug('r.json(): %s', r.json())
        return r.json()
