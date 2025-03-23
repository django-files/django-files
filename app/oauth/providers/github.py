import logging
import urllib.parse
from typing import Optional

import httpx
from decouple import config
from django.shortcuts import HttpResponseRedirect
from oauth.models import Github
from oauth.providers.base import BaseOauth
from oauth.providers.helpers import is_super_id


provider = "github"
log = logging.getLogger(f"app.{provider}")


class GithubOauth(BaseOauth):

    def process_login(self, site_settings) -> None:
        self.data = self.get_token(site_settings, self.code)
        self.profile = self.get_profile(self.data)
        self.id: Optional[int] = self.profile["id"]
        self.username: Optional[str] = self.profile["login"]
        self.first_name: Optional[str] = self.profile["name"]

    def update_profile(self, user) -> None:
        if not getattr(user, provider, None):
            Github.objects.create(
                user=user,
                id=self.profile["id"],
            )
        log.debug("user.github: %s", user.github)
        user.github.profile = self.profile
        user.github.avatar = self.profile["avatar_url"]
        user.github.access_token = self.data["access_token"]
        user.github.save()
        if is_super_id(self.id):
            user.is_staff = True
            user.is_superuser = True
            user.save()

    @classmethod
    def get_login_url(cls, site_settings) -> str:
        params = {
            "redirect_uri": site_settings.get_oauth_redirect_url(provider="github"),
            "client_id": site_settings.github_client_id,
            "response_type": config("OAUTH_RESPONSE_TYPE", "code"),
            "scope": config("OAUTH_SCOPE", ""),
            "prompt": config("OAUTH_PROMPT", "none"),
        }
        return f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"

    @classmethod
    def redirect_login(cls, request, site_settings) -> HttpResponseRedirect:
        request.session["oauth_provider"] = provider
        if request.user.is_authenticated:
            request.session["oauth_claim_username"] = request.user.username
        return HttpResponseRedirect(cls.get_login_url(site_settings))

    @classmethod
    def get_token(cls, site_settings, code: str) -> dict:
        log.debug("get_token")
        data = {
            "redirect_uri": site_settings.get_oauth_redirect_url(provider="github"),
            "client_id": site_settings.github_client_id,
            "client_secret": site_settings.github_client_secret,
            "grant_type": config("OAUTH_GRANT_TYPE", "authorization_code"),
            "code": code,
        }
        headers = {"Accept": "application/vnd.github+json"}
        url = "https://github.com/login/oauth/access_token"
        r = httpx.post(url, data=data, headers=headers, timeout=10)
        if not r.is_success:
            log.debug("status_code: %s", r.status_code)
            log.error("content: %s", r.content)
            r.raise_for_status()
        return r.json()

    @classmethod
    def get_profile(cls, data: dict) -> dict:
        log.debug("get_discord_profile")
        url = "https://api.github.com/user"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {data['access_token']}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        r = httpx.get(url, headers=headers, timeout=10)
        if not r.is_success:
            log.debug("status_code: %s", r.status_code)
            log.error("content: %s", r.content)
            r.raise_for_status()
        log.debug("r.json(): %s", r.json())
        return r.json()
