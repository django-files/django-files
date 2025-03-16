import logging
import urllib.parse
from typing import Optional

import httpx
from decouple import config
from django.shortcuts import HttpResponseRedirect
from oauth.models import Google
from oauth.providers.base import BaseOauth
from oauth.providers.helpers import is_super_id


provider = "google"
log = logging.getLogger(f"app.{provider}")


class GoogleOauth(BaseOauth):

    def process_login(self, site_settings) -> None:
        self.data = self.get_token(site_settings, self.code)
        self.profile = self.get_profile(self.data)
        self.id: Optional[int] = self.profile["id"]
        self.username: Optional[str] = self.profile["email"]
        self.first_name: Optional[str] = self.profile["given_name"]

    def update_profile(self, user) -> None:
        if not getattr(user, provider, None):
            Google.objects.create(
                user=user,
                id=self.profile["id"],
            )
        log.debug("user.google: %s", user.google)
        user.google.profile = self.profile
        user.google.avatar = self.profile.get("picture")
        user.google.access_token = self.data["access_token"]
        user.google.save()
        if is_super_id(self.id):
            user.is_staff = True
            user.is_superuser = True
            user.save()

    @classmethod
    def get_login_url(cls, settings) -> str:
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.get_oauth_redirect_url(provider="google"),
            "scope": config("OAUTH_SCOPE", "openid email profile"),
            "response_type": config("OAUTH_RESPONSE_TYPE", "code"),
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"

    @classmethod
    def redirect_login(cls, request, settings) -> HttpResponseRedirect:
        request.session["oauth_provider"] = provider
        if request.user.is_authenticated:
            request.session["oauth_claim_username"] = request.user.username
        return HttpResponseRedirect(cls.get_login_url(settings))

    @classmethod
    def get_token(cls, site_settings, code: str) -> dict:
        log.debug("get_token")
        data = {
            "redirect_uri": site_settings.get_oauth_redirect_url(provider="google"),
            "client_id": site_settings.google_client_id,
            "client_secret": site_settings.google_client_secret,
            "grant_type": config("OAUTH_GRANT_TYPE", "authorization_code"),
            "code": code,
        }
        headers = {"Accept": "application/json"}
        url = "https://oauth2.googleapis.com/token"
        r = httpx.post(url, data=data, headers=headers, timeout=10)
        if not r.is_success:
            log.debug("status_code: %s", r.status_code)
            log.error("content: %s", r.content)
            r.raise_for_status()
        return r.json()

    @classmethod
    def get_profile(cls, data: dict) -> dict:
        log.debug("get_google_profile")
        url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {data['access_token']}",
        }
        r = httpx.get(url, headers=headers, timeout=10)
        if not r.is_success:
            log.debug("status_code: %s", r.status_code)
            log.error("content: %s", r.content)
            r.raise_for_status()
        log.debug("r.json(): %s", r.json())
        return r.json()
