import hashlib
import hmac
import json
import logging

import httpx
from django.shortcuts import reverse
from django.utils import timezone

log = logging.getLogger("app")

WEBHOOK_TYPE_CUSTOM = "custom"
WEBHOOK_TYPE_DISCORD = "discord"

WEBHOOK_SCOPE_USER = "user"
WEBHOOK_SCOPE_SITE = "site"

EVENT_FILE_UPLOAD = "file.upload"
EVENT_ALBUM_CREATED = "album.created"
EVENT_ALBUM_UPDATED = "album.updated"
EVENT_STREAM_LIVE = "stream.live"
EVENT_STREAM_OFFLINE = "stream.offline"
EVENT_USER_CREATED = "user.created"
EVENT_USER_DELETED = "user.deleted"
EVENT_USER_LOGIN = "user.login"
EVENT_TEST = "webhook.test"

# event key -> human-readable label, rendered as checkboxes in the settings UI
WEBHOOK_EVENTS = {
    EVENT_FILE_UPLOAD: "File Uploaded",
    EVENT_ALBUM_CREATED: "Album Created",
    EVENT_ALBUM_UPDATED: "Album Updated",
    EVENT_STREAM_LIVE: "Stream Live",
    EVENT_STREAM_OFFLINE: "Stream Offline",
    EVENT_USER_CREATED: "User Created",
    EVENT_USER_DELETED: "User Deleted",
    EVENT_USER_LOGIN: "User Login",
}

# events that only site-scoped webhooks may subscribe to (owner_pk is None at dispatch)
SITE_ONLY_EVENTS = {EVENT_USER_CREATED, EVENT_USER_DELETED}

DISCORD_TITLES = {
    EVENT_FILE_UPLOAD: "New File Upload",
    EVENT_ALBUM_CREATED: "Album Created",
    EVENT_ALBUM_UPDATED: "Album Updated",
    EVENT_STREAM_LIVE: "Stream Live",
    EVENT_STREAM_OFFLINE: "Stream Offline",
    EVENT_USER_CREATED: "User Created",
    EVENT_USER_DELETED: "User Deleted",
    EVENT_USER_LOGIN: "User Login",
    EVENT_TEST: "Webhook Test",
}


def _site_url() -> str:
    from settings.models import SiteSettings

    return SiteSettings.objects.settings().site_url


def build_file_payload(file) -> dict:
    site_url = _site_url()
    return {
        "id": file.id,
        "name": file.name,
        "url": site_url + file.preview_uri(),
        "raw_url": site_url + file.raw_path,
        "size": file.size,
        "mime": file.mime,
        "user": file.user.username,
    }


def build_album_payload(album) -> dict:
    return {
        "id": album.id,
        "name": album.name,
        "url": f"{_site_url()}{reverse('home:files')}?album={album.id}",
        "file_count": album.files_set.count(),
        "user": album.user.username,
    }


def build_stream_payload(stream) -> dict:
    return {
        "name": stream.name,
        "url": _site_url() + reverse("home:live", kwargs={"key": stream.name}),
        "user": stream.user.username,
    }


def build_user_payload(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "date_joined": user.date_joined.isoformat(),
    }


def build_test_payload(webhook) -> dict:
    return {
        "id": webhook.id,
        "name": webhook.name,
        "user": webhook.owner.username,
    }


def _discord_description(event_key: str, data: dict) -> str:
    if event_key == EVENT_FILE_UPLOAD:
        return f"**{data['name']}**\n`{data['mime']}` - {data['size']} bytes"
    if event_key in (EVENT_ALBUM_CREATED, EVENT_ALBUM_UPDATED):
        return f"**{data['name']}** - {data['file_count']} files"
    if event_key in (EVENT_STREAM_LIVE, EVENT_STREAM_OFFLINE):
        verb = "went live" if event_key == EVENT_STREAM_LIVE else "ended"
        return f"**{data['name']}** {verb}"
    if event_key == EVENT_TEST:
        return "Webhook added successfully. New results will show up here..."
    return f"**{data.get('username', data.get('user', ''))}**"


def build_discord_embed(event_key: str, payload_data: dict, site_url: str) -> dict:
    return {
        "embeds": [
            {
                "title": DISCORD_TITLES.get(event_key, event_key),
                "description": _discord_description(event_key, payload_data),
                "url": payload_data.get("url", site_url),
                "timestamp": timezone.now().isoformat(),
                "footer": {"text": "django-files"},
            }
        ]
    }


def send_webhook(webhook, event_key: str, payload_data: dict) -> httpx.Response:
    """POST an event to a webhook endpoint. Shared by the Celery task and the test-fire views."""
    site_url = _site_url()
    if webhook.webhook_type == WEBHOOK_TYPE_DISCORD:
        body = build_discord_embed(event_key, payload_data, site_url)
        return httpx.post(webhook.url, json=body, timeout=30)
    payload = {
        "event": event_key,
        "timestamp": timezone.now().isoformat(),
        "site_url": site_url,
        "data": payload_data,
    }
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "X-Webhook-Event": event_key}
    if webhook.secret:
        signature = hmac.new(webhook.secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={signature}"
    return httpx.post(webhook.url, content=body, headers=headers, timeout=30)
