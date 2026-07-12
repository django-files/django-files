import hashlib
import hmac
import json
import logging
from datetime import datetime

import httpx
from django.shortcuts import reverse
from django.utils import timezone
from home.util.misc import bytes_to_human_read

log = logging.getLogger("app")

WEBHOOK_TYPE_CUSTOM = "custom"
WEBHOOK_TYPE_DISCORD = "discord"

WEBHOOK_SCOPE_USER = "user"
WEBHOOK_SCOPE_SITE = "site"

EVENT_FILE_UPLOAD = "file.upload"
EVENT_FILE_DELETED = "file.deleted"
EVENT_ALBUM_CREATED = "album.created"
EVENT_ALBUM_UPDATED = "album.updated"
EVENT_ALBUM_DELETED = "album.deleted"
EVENT_SHORT_CREATED = "short.created"
EVENT_SHORT_DELETED = "short.deleted"
EVENT_STREAM_LIVE = "stream.live"
EVENT_STREAM_OFFLINE = "stream.offline"
EVENT_USER_CREATED = "user.created"
EVENT_USER_DELETED = "user.deleted"
EVENT_USER_LOGIN = "user.login"
EVENT_TEST = "webhook.test"

# event key -> human-readable label, rendered as checkboxes in the settings UI
WEBHOOK_EVENTS = {
    EVENT_FILE_UPLOAD: "File Uploaded",
    EVENT_FILE_DELETED: "File Deleted",
    EVENT_ALBUM_CREATED: "Album Created",
    EVENT_ALBUM_UPDATED: "Album Updated",
    EVENT_ALBUM_DELETED: "Album Deleted",
    EVENT_SHORT_CREATED: "Short URL Created",
    EVENT_SHORT_DELETED: "Short URL Deleted",
    EVENT_STREAM_LIVE: "Stream Live",
    EVENT_STREAM_OFFLINE: "Stream Ended",
    EVENT_USER_CREATED: "User Created",
    EVENT_USER_DELETED: "User Deleted",
    EVENT_USER_LOGIN: "User Login",
}

# events that only site-scoped webhooks may subscribe to (owner_pk is None at dispatch)
SITE_ONLY_EVENTS = {EVENT_USER_CREATED, EVENT_USER_DELETED}

# events whose payloads carry file tags and honor the webhook tag filter
FILE_EVENTS = {EVENT_FILE_UPLOAD, EVENT_FILE_DELETED}

DISCORD_TITLES = {
    EVENT_FILE_UPLOAD: "New File Upload",
    EVENT_FILE_DELETED: "File Deleted",
    EVENT_ALBUM_CREATED: "Album Created",
    EVENT_ALBUM_UPDATED: "Album Updated",
    EVENT_ALBUM_DELETED: "Album Deleted",
    EVENT_SHORT_CREATED: "Short URL Created",
    EVENT_SHORT_DELETED: "Short URL Deleted",
    EVENT_STREAM_LIVE: "Stream Live",
    EVENT_STREAM_OFFLINE: "Stream Ended",
    EVENT_USER_CREATED: "User Created",
    EVENT_USER_DELETED: "User Deleted",
    EVENT_USER_LOGIN: "User Login",
    EVENT_TEST: "Webhook Test",
}


def _site_url() -> str:
    from settings.models import SiteSettings

    return SiteSettings.objects.settings().site_url


def _exif_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y:%m:%d %H:%M:%S").strftime("%m/%d/%Y %H:%M:%S")
    except ValueError:
        return ""


def build_file_payload(file) -> dict:
    site_url = _site_url()
    exif = file.exif or {}
    meta = file.meta or {}
    make, model = exif.get("Make", ""), exif.get("Model", "")
    camera = model if not make or make in model else f"{make} {model}"
    return {
        "id": file.id,
        "name": file.name,
        "description": file.info,
        "url": site_url + file.preview_uri(),
        "raw_url": site_url + file.raw_path,
        "size": file.size,
        "mime": file.mime,
        "user": file.user.username,
        "captured_at": _exif_date(exif.get("DateTimeOriginal", "")),
        "location": meta.get("GPSArea", ""),
        "camera": camera,
        "tags": [tag.tag for tag in file.tags.all()],
    }


def build_album_payload(album) -> dict:
    return {
        "id": album.id,
        "name": album.name,
        "url": f"{_site_url()}{reverse('home:files')}?album={album.id}",
        "file_count": album.files_set.count(),
        "user": album.user.username,
    }


def build_short_payload(short) -> dict:
    return {
        "id": short.id,
        "short": short.short,
        "short_url": _site_url() + reverse("home:short", kwargs={"short": short.short}),
        "url": short.url,
        "views": short.views,
        "max": short.max,
        "user": short.user.username,
    }


def build_stream_payload(stream) -> dict:
    duration = None
    if stream.ended_at and stream.started_at:
        started, ended = stream.started_at, stream.ended_at
        # the stream views assign naive datetime.now() while DB values are
        # aware; normalize or the subtraction raises and kills the dispatch
        if timezone.is_naive(started) != timezone.is_naive(ended):
            started = started if timezone.is_aware(started) else timezone.make_aware(started)
            ended = ended if timezone.is_aware(ended) else timezone.make_aware(ended)
        duration = int((ended - started).total_seconds())
    return {
        "name": stream.name,
        "title": stream.title,
        "description": stream.description,
        "url": _site_url() + reverse("home:live", kwargs={"key": stream.name}),
        "user": stream.user.username,
        "duration": duration,
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


def event_matches_filters(event_key: str, filters: dict, payload_data: dict) -> bool:
    """Check an event payload against a webhook's filters.

    Only "tags" is supported so far, and only file events honor it: entries are
    matched case-insensitively against the payload tags, a "!" prefix excludes,
    and exclusions win over matches. No positive entries means any file passes
    the exclusion check. Unknown filter keys are ignored so old workers stay
    compatible with filter types added later.
    """
    if event_key not in FILE_EVENTS or not isinstance(filters, dict):
        return True
    tag_filter = filters.get("tags")
    if not tag_filter:
        return True
    file_tags = {tag.lower() for tag in payload_data.get("tags", [])}
    excluded = {tag[1:].lower() for tag in tag_filter if tag.startswith("!")}
    included = {tag.lower() for tag in tag_filter if not tag.startswith("!")}
    if excluded & file_tags:
        return False
    return not included or bool(included & file_tags)


MAX_TAG_LINE = 256


def _file_description(data: dict) -> str:
    text = f"**{data['name']}**\n`{data['mime']}` - {bytes_to_human_read(data['size'])}"
    if data.get("description"):
        text = f"{data['description']}\n{text}"
    if data.get("captured_at"):
        text += f"\n**Captured On:** {data['captured_at']}"
    if data.get("location"):
        text += f"\n**Location:** {data['location']}"
    if data.get("camera"):
        text += f"\n**Camera:** {data['camera']}"
    if tags := data.get("tags"):
        tag_line = ", ".join(tags)
        if len(tag_line) > MAX_TAG_LINE:
            tag_line = tag_line[: MAX_TAG_LINE - 1] + "…"
        text += f"\n**Tags:** {tag_line}"
    return text


def _human_duration(seconds: int) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _discord_title(event_key: str, data: dict) -> str:
    if event_key == EVENT_STREAM_LIVE:
        return f"{data.get('user', '')} went live"
    if event_key == EVENT_STREAM_OFFLINE:
        return f"{data.get('user', '')} stream ended"
    return DISCORD_TITLES.get(event_key, event_key)


def _discord_description(event_key: str, data: dict) -> str:
    if event_key in (EVENT_FILE_UPLOAD, EVENT_FILE_DELETED):
        return _file_description(data)
    if event_key in (EVENT_ALBUM_CREATED, EVENT_ALBUM_UPDATED, EVENT_ALBUM_DELETED):
        return f"**{data['name']}** - {data['file_count']} files"
    if event_key in (EVENT_SHORT_CREATED, EVENT_SHORT_DELETED):
        return f"**{data['short_url']}**\n{data['url']}"
    if event_key in (EVENT_STREAM_LIVE, EVENT_STREAM_OFFLINE):
        text = f"**{data.get('title') or data['name']}**"
        if data.get("description"):
            text += f"\n{data['description']}"
        if event_key == EVENT_STREAM_OFFLINE and data.get("duration") is not None:
            text += f"\n**Duration:** {_human_duration(data['duration'])}"
        return text
    if event_key == EVENT_TEST:
        return "Webhook added successfully. New results will show up here..."
    return f"**{data.get('username', data.get('user', ''))}**"


def build_discord_embed(event_key: str, payload_data: dict, site_url: str) -> dict:
    from settings.models import SiteSettings

    site_title = SiteSettings.objects.settings().site_title
    embed = {
        "title": _discord_title(event_key, payload_data),
        "description": _discord_description(event_key, payload_data),
        "url": payload_data.get("url", site_url),
        "timestamp": timezone.now().isoformat(),
        "footer": {"text": f"django-files • {site_title}"},
    }
    body = {
        # username overrides the webhook's own name (the Discord application
        # name for OAuth-created hooks) on every delivered message
        "username": site_title,
        "embeds": [embed],
    }
    if event_key == EVENT_FILE_UPLOAD and (raw_url := payload_data.get("raw_url")):
        mime = payload_data.get("mime", "")
        if mime.startswith("image/"):
            embed["image"] = {"url": raw_url}
        elif mime.startswith("video/"):
            # webhook embeds cannot carry a playable video; a bare link in
            # content lets Discord unfurl its own player for formats it
            # supports (mp4/webm — not mov). The generated video thumbnail
            # gives every format at least a preview image.
            body["content"] = raw_url
            separator = "&" if "?" in raw_url else "?"
            embed["image"] = {"url": f"{raw_url}{separator}thumb=true"}
    return body


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
