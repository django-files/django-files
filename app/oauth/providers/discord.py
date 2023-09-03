import httpx
import logging
import urllib.parse
from datetime import datetime, timedelta
from decouple import config
from django.db import models
from django.http import HttpRequest
from django.shortcuts import HttpResponseRedirect
from oauth.providers.helpers import get_next_url, get_or_create_user, OauthUser
from typing import Optional, Tuple

from oauth.models import CustomUser, Discord

log = logging.getLogger('app')


class DiscordOauth(object):
    api_url = 'https://discord.com/api/v8/'

    # __slots__ = [
    #     'token_resp',
    #     'user_resp',
    #     'profile',
    # ]

    # def __init__(self, code: str):
    #     self.token_resp = self.get_token(code)
    #     self.user_resp = self.get_profile(self.token_resp)
    #     self.profile = {
    #         'oauth_id': self.user_resp['id'],
    #         'username': self.user_resp['username'],
    #         'discord_avatar': self.user_resp['avatar'],
    #         'access_token': self.token_resp['access_token'],
    #         'refresh_token': self.token_resp['refresh_token'],
    #         'expires_in': datetime.now() + timedelta(0, self.token_resp['expires_in']),
    #     }

    @classmethod
    def redirect_login(cls, request: HttpRequest) -> HttpResponseRedirect:
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
    def redirect_webhook(cls, request: HttpRequest) -> HttpResponseRedirect:
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

    # @classmethod
    # def get_user(cls, code: str) -> Optional[OauthUser]:
    #     Discord.objects.create(
    #         user=user,
    #         id=profile['id'],
    #         profile=profile,
    #         avatar=profile['avatar'],
    #         access_token=data['access_token'],
    #         refresh_token=data['refresh_token'],
    #         expires_in=datetime.now() + timedelta(0, data['expires_in']),
    #     )
    #     return user

    @classmethod
    def get_user(cls, code: str) -> Optional[OauthUser]:
        data = cls.get_token(code)
        profile = cls.get_profile(data)
        # user = get_or_create_user(profile['id'], profile['username'])
        if not (user := get_or_create_user(profile['id'], profile['username'])):
            return None
        return OauthUser(
            _id=profile['id'],
            username=profile['username'],
            user=user,
            data=data,
            profile=profile,
        )

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
        # user_resp = r.json()
        # return {
        #     'oauth_id': user_resp['id'],
        #     'username': user_resp['username'],
        #     'discord_avatar': user_resp['avatar'],
        #     'access_token': data['access_token'],
        #     'refresh_token': data['refresh_token'],
        #     'expires_in': datetime.now() + timedelta(0, data['expires_in']),
        # }
