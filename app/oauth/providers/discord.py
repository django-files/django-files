import logging
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import httpx
from decouple import config
from django.shortcuts import HttpResponseRedirect
from oauth.models import Discord, DiscordWebhooks
from oauth.providers.base import BaseOauth
from oauth.providers.helpers import is_super_id


provider = "discord"
log = logging.getLogger(f"app.{provider}")


class DiscordOauth(BaseOauth):
    api_url = "https://discord.com/api/v8/"

    def process_login(self, site_settings) -> None:
        self.data = self.get_token(site_settings, self.code)
        self.profile = self.get_profile(self.data)
        self.id: Optional[int] = self.profile["id"]
        self.username: Optional[str] = self.profile["username"]
        self.first_name: Optional[str] = self.profile["global_name"]

    def update_profile(self, user) -> None:
        if not getattr(user, provider, None):
            Discord.objects.create(
                user=user,
                id=self.profile["id"],
            )
        log.debug("user.discord: %s", user.discord)
        user.discord.profile = self.profile
        user.discord.avatar = self.profile["avatar"]
        user.discord.access_token = self.data["access_token"]
        user.discord.refresh_token = self.data["refresh_token"]
        user.discord.expires_in = datetime.now() + timedelta(0, self.data["expires_in"])
        user.discord.save()
        if is_super_id(self.id):
            user.is_staff = True
            user.is_superuser = True
            user.save()

    def add_webhook(self, request) -> DiscordWebhooks:
        return DiscordWebhooks.objects.create(
            hook_id=self.data["webhook"]["id"],
            guild_id=self.data["webhook"]["guild_id"],
            channel_id=self.data["webhook"]["channel_id"],
            url=self.data["webhook"]["url"],
            owner=request.user,
        )

    @classmethod
    def get_login_url(cls, site_settings) -> str:
        log.info("get_login_url: %s", site_settings.get_oauth_redirect_url(provider="discord"))
        params = {
            "redirect_uri": site_settings.get_oauth_redirect_url(provider="discord"),
            "client_id": site_settings.discord_client_id,
            "response_type": config("OAUTH_RESPONSE_TYPE", "code"),
            "scope": config("OAUTH_SCOPE", "identify"),
            "prompt": config("OAUTH_PROMPT", "none"),
        }
        return f"https://discord.com/oauth2/authorize?{urllib.parse.urlencode(params)}"

    @classmethod
    def redirect_login(cls, request, site_settings) -> HttpResponseRedirect:
        request.session["oauth_provider"] = provider
        if request.user.is_authenticated:
            request.session["oauth_claim_username"] = request.user.username
        return HttpResponseRedirect(cls.get_login_url(site_settings))

    @classmethod
    def redirect_webhook(cls, request, site_settings) -> HttpResponseRedirect:
        request.session["oauth_provider"] = provider
        request.session["webhook"] = "discord"
        params = {
            "redirect_uri": site_settings.get_oauth_redirect_url(provider="discord"),
            "client_id": site_settings.discord_client_id,
            "response_type": config("OAUTH_RESPONSE_TYPE", "code"),
            "scope": config("OAUTH_SCOPE", "identify") + " webhook.incoming",
        }
        url_params = urllib.parse.urlencode(params)
        url = f"{cls.api_url}/oauth2/authorize?{url_params}"
        return HttpResponseRedirect(url)

    @classmethod
    def get_token(cls, site_settings, code: str) -> dict:
        log.debug("get_token")
        data = {
            "redirect_uri": site_settings.get_oauth_redirect_url(provider="discord"),
            "client_id": site_settings.discord_client_id,
            "client_secret": site_settings.discord_client_secret,
            "grant_type": config("OAUTH_GRANT_TYPE", "authorization_code"),
            "code": code,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        url = f"{cls.api_url}/oauth2/token"
        r = httpx.post(url, data=data, headers=headers, timeout=10)
        if not r.is_success:
            log.debug("status_code: %s", r.status_code)
            log.error("content: %s", r.content)
            r.raise_for_status()
        return r.json()

    @classmethod
    def get_profile(cls, data: dict) -> dict:
        log.debug("get_discord_profile")
        url = f"{cls.api_url}/users/@me"
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        r = httpx.get(url, headers=headers, timeout=10)
        if not r.is_success:
            log.debug("status_code: %s", r.status_code)
            log.error("content: %s", r.content)
            r.raise_for_status()
        log.debug("r.json(): %s", r.json())
        return r.json()
