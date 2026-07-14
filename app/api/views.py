import io
import ipaddress
import json
import logging
import operator
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import reduce, wraps
from typing import Any, BinaryIO, Callable, List, Optional, Union
from urllib.parse import parse_qs, urlparse

import httpx
import validators
from api.utils import (
    apply_ordering,
    extract_albums,
    extract_files,
    extract_streams,
    serialize_user,
    serialize_users,
)
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.core.paginator import Paginator
from django.core.signing import TimestampSigner
from django.db.models import Count, Max, Q, QuerySet, Sum
from django.db.models.fields.json import KeyTextTransform
from django.forms.models import model_to_dict
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.utils.crypto import constant_time_compare
from django.utils.timezone import localtime, now
from django.views.decorators.cache import cache_control, cache_page, never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie, vary_on_headers
from django_redis import get_redis_connection
from home.models import (
    Albums,
    Files,
    FileStats,
    ShortURLs,
    Stream,
    StreamHistory,
    Webhook,
)
from home.tasks import (
    clear_files_cache,
    clear_shorts_cache,
    dispatch_webhook_event,
    import_stream_recording,
    send_push_live,
    stream_status_websocket,
)
from home.util.auth import create_api_token, hash_token
from home.util.file import process_file
from home.util.misc import anytobool, human_read_to_byte, redact_log
from home.util.nginx import sign_hls_cookie, verify_hls_cookie
from home.util.quota import process_storage_quotas
from home.util.rand import rand_string
from home.util.storage import file_rename
from home.util.stream_record import delete_recording_file
from home.util.tags import clean_tag_names
from home.util.webhooks import (
    EVENT_STREAM_LIVE,
    EVENT_STREAM_OFFLINE,
    EVENT_TEST,
    SITE_ONLY_EVENTS,
    WEBHOOK_EVENTS,
    build_stream_payload,
    build_test_payload,
    send_webhook,
)
from oauth.models import ApiToken, CustomUser, UserInvites
from oauth.providers.discord import DiscordOauth
from oauth.providers.github import GithubOauth
from oauth.providers.google import GoogleOauth
from oauth.views import post_login, pre_login
from packaging import version
from packaging.version import InvalidVersion
from pytimeparse2 import parse
from settings.context_processors import site_settings_processor
from settings.models import SiteSettings
from webpush.models import PushInformation

signer = TimestampSigner()

ERROR_NOT_FOUND = "Not Found"

_ARCHIVE_MIMES = [
    "application/zip",
    "application/x-tar",
    "application/gzip",
    "application/x-gzip",
    "application/x-bzip2",
    "application/x-7z-compressed",
    "application/x-rar-compressed",
    "application/vnd.rar",
    "application/x-xz",
    "application/x-lzma",
    "application/x-compress",
    "application/x-iso9660-image",
    "application/x-apple-diskimage",
]
_DOCUMENT_MIMES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/rtf",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
]
# Match on substrings rather than enumerating every variant — PE alone has
# application/x-msdownload, application/x-dosexec, application/vnd.microsoft.portable-executable, etc.
_EXECUTABLE_Q = (
    Q(mime__icontains="executable")  # x-executable, portable-executable, x-ms-dos-executable
    | Q(mime__icontains="msdownload")  # x-msdownload
    | Q(mime__icontains="mach-binary")  # x-mach-binary (macOS)
    | Q(mime__icontains="dosexec")  # x-dosexec
    | Q(
        mime__in=[
            "application/vnd.android.package-archive",  # .apk
            "application/x-deb",
            "application/x-debian-package",
            "application/x-rpm",
        ]
    )
)
_TYPE_Q = {
    "image": Q(mime__startswith="image/"),
    "video": Q(mime__startswith="video/"),
    "audio": Q(mime__startswith="audio/"),
    "text": Q(mime__startswith="text/"),
    "document": Q(mime__in=_DOCUMENT_MIMES),
    "archive": Q(mime__in=_ARCHIVE_MIMES),
    "executable": _EXECUTABLE_Q,
}


log = logging.getLogger("app")
cache_seconds = 60 * 60 * 4

json_error_message = "Error Parsing JSON Body"
STREAM_NOT_FOUND_ERROR = "Stream not found."
FORBIDDEN_ERROR = "Forbidden."


def paginate_no_count(queryset, page, count):
    """Paginate without a COUNT(*) query. Returns (items, next_page_or_none)."""
    page = max(1, int(page) if page is not None else 1)
    offset = (page - 1) * count
    rows = list(queryset[offset : offset + count + 1])
    has_next = len(rows) > count
    return rows[:count], (page + 1 if has_next else None)


_token_last_used_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="token-last-used")


def _record_token_last_used(pk: str) -> None:
    try:
        get_redis_connection("default").hset("token_last_used", pk, time.time())
    except Exception:
        log.debug("Failed to record token last_used_at for %s", pk, exc_info=True)


def _extract_token(request):
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    # Backward compat: older iOS clients send the raw token as the
    # Authorization value without the Bearer scheme prefix.
    return auth_header or request.headers.get("Token", "")


def _authenticate_bearer(request):
    token = _extract_token(request)
    if not token:
        return None
    api_token_obj = ApiToken.objects.select_related("user").filter(token_hash=hash_token(token)).first()
    if api_token_obj and api_token_obj.is_valid():
        _token_last_used_pool.submit(_record_token_last_used, str(api_token_obj.pk))
        return api_token_obj.user
    return None


def auth_from_token(view=None, no_fail=False):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if getattr(request, "user", None) and request.user.is_authenticated:
            return view(request, *args, **kwargs)
        user = _authenticate_bearer(request)
        if user is not None:
            request.user = user
            return view(request, *args, **kwargs)
        if not no_fail:
            return JsonResponse({"error": "Invalid Authorization"}, status=401)
        return view(request, *args, **kwargs)

    if view:
        return wrapper
    else:
        return lambda func: auth_from_token(func, no_fail)


def _parse_trusted_proxies():
    networks = []
    for cidr in getattr(settings, "TRUSTED_PROXIES", []):
        try:
            networks.append(ipaddress.ip_network(cidr.strip(), strict=False))
        except ValueError:
            log.warning("TRUSTED_PROXIES: invalid entry ignored: %r", cidr)
    return networks


_TRUSTED_PROXY_NETWORKS = _parse_trusted_proxies()


def _client_ip(request):
    remote = request.META.get("REMOTE_ADDR", "unknown")
    if not _TRUSTED_PROXY_NETWORKS:
        return remote
    try:
        remote_addr = ipaddress.ip_address(remote)
    except ValueError:
        return remote
    if not any(remote_addr in net for net in _TRUSTED_PROXY_NETWORKS):
        return remote
    # Walk XFF right-to-left, skip trusted hops, return first untrusted IP.
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidates = [h.strip() for h in xff.split(",") if h.strip()]
    for candidate in reversed(candidates):
        try:
            addr = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if not any(addr in net for net in _TRUSTED_PROXY_NETWORKS):
            return candidate
    return remote


def ip_rate_limit(rate="10/m"):
    limit, period_char = rate.split("/")
    limit = int(limit)
    period = {"s": 1, "m": 60, "h": 3600, "d": 86400}[period_char]

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            ip = _client_ip(request)
            key = f"ratelimit:{view.__name__}:{ip}"
            try:
                count = cache.incr(key)
            except ValueError:
                cache.set(key, 1, period)
                count = 1
            if count > limit:
                return HttpResponse(status=429)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


@csrf_exempt
@login_required
def api_view(request):
    """
    View  /api/
    """
    log.debug("%s - api_view: is_secure: %s", request.method, request.is_secure())
    return render(request, "api.html")


@csrf_exempt
@require_http_methods(["GET", "HEAD", "POST"])
def version_view(request):
    """
    View  /api/version
    """
    log.debug("%s - version_view: APP_VERSION: %s", request.method, settings.APP_VERSION)
    data = {"version": settings.APP_VERSION}
    if request.method != "POST":
        return JsonResponse(data)
    else:
        data["valid"] = False
        if settings.APP_VERSION.startswith("DEV:"):
            log.debug("SUCCESS: DEV VERSION")
            data["valid"] = True
            return JsonResponse(data)
        try:
            current_version = version.parse(settings.APP_VERSION)
            log.debug("current_version: %s", current_version)

            body = get_json_body(request)
            log.debug("body: %s", body)
            log.debug("version: %s", body["version"])

            required_version = version.parse(body["version"])
            log.debug("required_version: %s", required_version)

            if required_version.is_prerelease:
                log.debug("SUCCESS: DEV CLIENT")
                data["valid"] = True
                return JsonResponse(data)

            if required_version >= current_version:
                log.debug("SUCCESS: required version >= current version")
                data["valid"] = True
                return JsonResponse(data)

            log.debug("FAILED: required version < current version")
            return JsonResponse(data)
        except InvalidVersion as error:
            log.warning("InvalidVersion: %s", error)
            return JsonResponse({"error": str(error)}, status=400)
        except Exception as error:
            log.warning("Exception: %s", error)
            return JsonResponse({"error": str(error)}, status=500)


@csrf_exempt
@require_http_methods(["OPTIONS", "POST"])
@auth_from_token(no_fail=True)
def upload_view(request):
    """
    View  /upload/ and /api/upload
    """
    log.debug("upload_view")
    # log.debug(request.headers)
    post = request.POST.dict().copy()
    log.debug(redact_log(post))
    log.debug(request.FILES)
    site_settings = SiteSettings.objects.settings()
    if not site_settings.pub_load and not request.user.is_authenticated:
        return JsonResponse({"error": "Public uploads are disabled."}, status=403)
    elif request.user.is_anonymous:
        request.user = CustomUser.objects.get(username="anonymous")
    try:
        f = request.FILES.get("file")
        # log.debug("f.size: %s", f.size)
        if any(pq := process_storage_quotas(request.user, f.size)):
            if pq[1]:
                message = "Upload Failed: Global storage quota exceeded."
            elif pq[0]:
                message = "Upload Failed: User storage quota exceeded."
            else:
                message = "Unknown error checking quotas."
            log.error(message)
            return JsonResponse({"error": True, "message": message}, status=400)
        if not f and post.get("text"):
            f = io.BytesIO(bytes(post.pop("text"), "utf-8"))
            f.name = post.pop("name", "paste.txt") or "paste.txt"
            f.name = f.name if "." in f.name else f.name + ".txt"
        if not f:
            return JsonResponse({"error": "No file or text keys found."}, status=400)
        # TODO: Determine how to better handle expire and why info is still being used differently from other methods
        expire = parse_expire(request)
        log.debug("expire: %s", expire)
        extra_args = parse_headers(request.headers, expr=expire, **post)
        log.debug("f.name: %s", f.name)
        log.debug("extra_args: %s", extra_args)
        log.debug("request.user: %s", request.user)
        return process_file_upload(request, f, request.user.id, **extra_args)
    except Exception as error:
        log.exception(error)
        return JsonResponse({"error": True, "message": str(error)}, status=500)


@csrf_exempt
@require_http_methods(["OPTIONS", "POST"])
@auth_from_token
def shorten_view(request):
    """
    View  /shorten/ and /api/shorten
    """
    try:
        log.debug("request.headers: %s", request.headers)
        data = get_json_body(request)
        log.debug("data: %s", data)
        url = data_or_header(request, data, "url")
        vanity = data_or_header(request, data, "vanity")
        max_views = data_or_header(request, data, "max-views")
        if not url:
            return JsonResponse({"error": "Missing Required Value: url"}, status=400)
        log.debug("url: %s", url)
        if not validators.url(url, simple_host=True):
            return JsonResponse({"error": "Unable to Validate URL"}, status=400)
        if max_views and not str(max_views).isdigit():
            return JsonResponse({"error": "max-views Must be an Integer"}, status=400)
        if vanity and not validators.slug(vanity):
            return JsonResponse({"error": "vanity Must be a Slug"}, status=400)

        name = gen_short(vanity)
        log.debug("name: %s", name)
        short = ShortURLs.objects.create(
            url=url,
            short=name,
            max=max_views or 0,
            user=request.user,
        )
        log.debug("short: %s", short)
        site_settings = SiteSettings.objects.settings()
        full_url = site_settings.site_url + reverse("home:short", kwargs={"short": short.short})
        return JsonResponse({"url": full_url}, safe=False)

    except Exception as error:
        log.exception(error)
        return JsonResponse({"error": str(error)}, status=500)


def _handle_create_album(request):
    data = get_json_body(request)
    log.debug("data: %s", data)
    # Honor the per-user "Default Private" / "Auto Password" toggles when the
    # caller didn't pass an explicit value. data_or_header treats missing keys
    # as the supplied default, so check the raw sources first to detect omission.
    has_private = "private" in data or "private" in request.headers
    has_password = "password" in data or "password" in request.headers
    private = (
        data_or_header(request, data, "private", False, cast=bool)
        if has_private
        else request.user.default_file_private
    )
    password = data_or_header(request, data, "password") if has_password else ""
    if not has_password and request.user.default_file_password:
        password = rand_string()
    album = Albums(
        user=request.user,
        name=data_or_header(request, data, "name"),
        maxv=data_or_header(request, data, "max-views", 0, cast=int),
        info=data_or_header(request, data, "description"),
        password=password,
        private=private,
        expr=data_or_header(request, data, "expire"),
    )
    # staged for albums_post_save_signal so tags exist before the
    # album.created websocket/webhook payloads are built
    album._pending_tags = data_or_header(request, data, "tags", [], cast=clean_tag_names)
    album.save()
    site_settings = SiteSettings.objects.settings()
    full_url = site_settings.site_url + reverse("home:files") + f"?album={album.id}"
    return JsonResponse({"url": full_url}, safe=False)


def _handle_delete_album(request, album_id):
    album = get_object_or_404(Albums, id=album_id)
    if album.user != request.user and not request.user.is_superuser:
        return HttpResponse(status=403)
    album.delete()
    return HttpResponse(status=204)


def _handle_update_album(request, album_id):
    album = get_object_or_404(Albums, id=album_id)
    if album.user != request.user and not request.user.is_superuser:
        return HttpResponse(status=403)
    data = get_json_body(request)
    if "private" in data:
        album.private = data_or_header(request, data, "private", False, cast=bool)
    if "name" in data:
        album.name = data_or_header(request, data, "name")
    if "password" in data:
        album.password = data_or_header(request, data, "password")
    if "description" in data:
        album.info = data_or_header(request, data, "description")
    if "max-views" in data:
        album.maxv = data_or_header(request, data, "max-views", 0, cast=int)
    if "expire" in data:
        album.expr = data_or_header(request, data, "expire")
    album.save()
    return JsonResponse(extract_albums([album])[0])


def _handle_get_album(request, album_id):
    album = get_object_or_404(Albums, id=album_id if album_id else request.GET.get("id"))
    return JsonResponse(extract_albums([album])[0])


@csrf_exempt
@require_http_methods(["OPTIONS", "POST", "GET", "DELETE", "PATCH"])
@auth_from_token
def album_view(request, album_id: int = None):
    """
    View  /api/album/
    """
    try:
        if request.method == "POST":
            return _handle_create_album(request)
        elif request.method == "DELETE":
            return _handle_delete_album(request, album_id)
        elif request.method == "PATCH":
            return _handle_update_album(request, album_id)
        else:
            return _handle_get_album(request, album_id)
    except Exception as error:
        log.exception(error)
        return JsonResponse({"error": f"{error}"}, status=400)


@csrf_exempt
@require_http_methods(["GET"])
@auth_from_token(no_fail=True)
def random_album(request, user_album: str, idname: str = ""):
    """
    View /api/random/albums/...
    /album_id/
    /user_id_username/album_id_name
    """
    if not idname:
        if not user_album.isnumeric():
            error = "Must provide Album ID, or user/album"
            return JsonResponse({"error": error}, status=400)
        kwargs = {"id": int(user_album)}
    else:
        if not user_album.isnumeric():
            user_album = get_object_or_404(CustomUser, username=user_album)
        kwargs = {"user": user_album}
        kwargs.update(id_or_name(idname))
    log.debug("kwargs: %s", kwargs)

    try:
        album = get_object_or_404(Albums, **kwargs)
        log.debug("random_album: %s: %s: %s", request.method, album.name, album.private)
        if not request.user.is_authenticated and album.private:
            return HttpResponse(status=404)
        files = Files.objects.filter(albums__id=album.id)
        file = random.choice(files)
        url = reverse("home:url-raw-redirect", kwargs={"filename": file.name})
        log.debug("url: %s", url)
        return redirect(url)
    except Exception as error:
        log.debug(error)
        return JsonResponse({"error": f"{error}"}, status=400)


@csrf_exempt
@require_http_methods(["OPTIONS", "GET", "POST"])
@auth_from_token
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix="invites")
@vary_on_headers("Authorization")
@vary_on_cookie
def invites_view(request):
    """
    View  /api/invites/
    """
    log.debug("%s - invites_view: is_secure: %s", request.method, request.is_secure())
    if request.method == "POST":
        log.debug("request.headers: %s", request.headers)
        data = get_json_body(request)
        log.debug("data: %s", data)
        # if not data:
        #     return JsonResponse({'error': 'Error Parsing JSON Body'}, status=400)
        invite = UserInvites.objects.create(
            owner=request.user,
            expire=data_or_header(request, data, "expire", 0, int),
            max_uses=data_or_header(request, data, "max_uses", 1, int),
            super_user=data_or_header(request, data, "super_user", False, anytobool),
            storage_quota=data_or_header(request, data, "storage_quota", 0, human_read_to_byte),
        )
        log.debug("invite: %s", invite)
        log.debug(model_to_dict(invite))
        return JsonResponse(model_to_dict(invite))

    return JsonResponse({"error": "Not Implemented"}, status=501)


@login_required()
@require_http_methods(["DELETE"])
def invite_detail_view(request, invite_id):
    """
    View  /api/invites/<invite_id>/
    """
    if not request.user.is_superuser:
        return HttpResponse(status=403)
    try:
        invite = UserInvites.objects.get(pk=invite_id)
    except UserInvites.DoesNotExist:
        return JsonResponse({"error": ERROR_NOT_FOUND}, status=404)
    invite.delete()
    return HttpResponse(status=204)


def _webhook_response(webhook: Webhook) -> dict:
    return {
        "id": webhook.id,
        "name": webhook.name,
        "webhook_type": webhook.webhook_type,
        "scope": webhook.scope,
        "url": webhook.url,
        "secret": webhook.secret,
        "active": webhook.active,
        "events": webhook.events,
        "filters": webhook.filters,
        "created_at": webhook.created_at,
        "updated_at": webhook.updated_at,
    }


def _clean_webhook_name(value) -> tuple:
    name = str(value).strip()
    if not name or len(name) > 128:
        return None, "Invalid name"
    return name, None


def _clean_webhook_url(value) -> tuple:
    if not validators.url(str(value)):
        return None, "Invalid url"
    return value, None


def _clean_webhook_type(value) -> tuple:
    if value not in (Webhook.WEBHOOK_TYPE_CUSTOM, Webhook.WEBHOOK_TYPE_DISCORD):
        return None, "Invalid webhook_type"
    return value, None


def _clean_webhook_scope(value) -> tuple:
    if value not in (Webhook.SCOPE_USER, Webhook.SCOPE_SITE):
        return None, "Invalid scope"
    return value, None


def _clean_webhook_events(value) -> tuple:
    valid = isinstance(value, list) and all(isinstance(event, str) and event in WEBHOOK_EVENTS for event in value)
    if not valid:
        return None, f"Invalid events. Valid events: {', '.join(WEBHOOK_EVENTS)}"
    return value, None


_WEBHOOK_FILTER_KEYS = ("tags",)
_WEBHOOK_MAX_FILTER_TAGS = 50


def _clean_webhook_filters(value) -> tuple:
    if not isinstance(value, dict):
        return None, "Invalid filters"
    if unknown := [key for key in value if key not in _WEBHOOK_FILTER_KEYS]:
        return None, f"Unknown filter keys: {', '.join(unknown)}. Valid keys: {', '.join(_WEBHOOK_FILTER_KEYS)}"
    tags = value.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        return None, "Invalid filters: tags must be a list of strings"
    tags = [tag.strip() for tag in tags]
    if any(not tag.lstrip("!") or len(tag) > 255 for tag in tags):
        return None, "Invalid filters: each tag must be 1-255 characters"
    if len(tags) > _WEBHOOK_MAX_FILTER_TAGS:
        return None, f"Invalid filters: maximum {_WEBHOOK_MAX_FILTER_TAGS} tags"
    return {"tags": tags} if tags else {}, None


def _clean_webhook_secret(value) -> tuple:
    secret = str(value)
    if len(secret) > 128:
        return None, "Invalid secret"
    return secret, None


def _clean_webhook_active(value) -> tuple:
    return anytobool(value), None


_WEBHOOK_REQUIRED_FIELDS = ("name", "url")

_WEBHOOK_FIELD_CLEANERS = {
    "name": _clean_webhook_name,
    "url": _clean_webhook_url,
    "webhook_type": _clean_webhook_type,
    "scope": _clean_webhook_scope,
    "events": _clean_webhook_events,
    "filters": _clean_webhook_filters,
    "secret": _clean_webhook_secret,
    "active": _clean_webhook_active,
}


def _validate_webhook_data(data: dict, partial: bool = False) -> tuple[dict, Optional[str]]:
    """Validate webhook create/update payloads. Returns (fields, error)."""
    if not partial:
        for key in _WEBHOOK_REQUIRED_FIELDS:
            if key not in data:
                return {}, f"Missing required field: {key}"
    fields = {}
    for key, cleaner in _WEBHOOK_FIELD_CLEANERS.items():
        if key not in data:
            continue
        value, error = cleaner(data[key])
        if error:
            return {}, error
        fields[key] = value
    return fields, None


def _webhook_scope_error(request, fields: dict, current: Optional[Webhook] = None) -> Optional[str]:
    """Cross-field rules for the final webhook state (submitted fields over current values)."""
    scope = fields.get("scope", current.scope if current else Webhook.SCOPE_USER)
    events = fields.get("events", current.events if current else [])
    if scope == Webhook.SCOPE_SITE and not request.user.is_superuser:
        return "Site-scoped webhooks require superuser"
    if scope == Webhook.SCOPE_USER and (site_only := [event for event in events if event in SITE_ONLY_EVENTS]):
        return f"Events require site scope: {', '.join(site_only)}"
    return None


def _get_webhook_or_error(request, webhook_id: int):
    webhook = Webhook.objects.filter(pk=webhook_id).first()
    if not webhook or (webhook.owner_id != request.user.id and not request.user.is_superuser):
        return None
    return webhook


@csrf_exempt
@require_http_methods(["OPTIONS", "GET", "POST"])
@auth_from_token
def webhooks_view(request):
    """
    View  /api/webhooks/
    """
    log.debug("%s - webhooks_view", request.method)
    if request.method == "POST":
        data = get_json_body(request)
        fields, error = _validate_webhook_data(data)
        if not error:
            error = _webhook_scope_error(request, fields)
        if error:
            return JsonResponse({"error": error}, status=400)
        webhook = Webhook.objects.create(owner=request.user, **fields)
        return JsonResponse(_webhook_response(webhook), status=201)
    webhooks = Webhook.objects.filter(owner=request.user)
    return JsonResponse({"webhooks": [_webhook_response(hook) for hook in webhooks]})


@csrf_exempt
@require_http_methods(["OPTIONS", "GET", "PATCH", "DELETE"])
@auth_from_token
def webhook_detail_view(request, webhook_id: int):
    """
    View  /api/webhooks/<webhook_id>/
    """
    log.debug("%s - webhook_detail_view: %s", request.method, webhook_id)
    webhook = _get_webhook_or_error(request, webhook_id)
    if not webhook:
        return JsonResponse({"error": ERROR_NOT_FOUND}, status=404)
    if request.method == "DELETE":
        webhook.delete()
        return HttpResponse(status=204)
    if request.method == "PATCH":
        data = get_json_body(request)
        fields, error = _validate_webhook_data(data, partial=True)
        if not error:
            error = _webhook_scope_error(request, fields, current=webhook)
        if error:
            return JsonResponse({"error": error}, status=400)
        for key, value in fields.items():
            setattr(webhook, key, value)
        webhook.save()
    return JsonResponse(_webhook_response(webhook))


@csrf_exempt
@require_http_methods(["POST"])
@auth_from_token
def webhook_test_view(request, webhook_id: int):
    """
    View  /api/webhooks/<webhook_id>/test/
    """
    log.debug("webhook_test_view: %s", webhook_id)
    webhook = _get_webhook_or_error(request, webhook_id)
    if not webhook:
        return JsonResponse({"error": ERROR_NOT_FOUND}, status=404)
    try:
        r = send_webhook(webhook, EVENT_TEST, build_test_payload(webhook))
    except httpx.HTTPError as error:
        log.warning("webhook_test_view: %s - %s", webhook_id, error)
        return JsonResponse({"success": False, "error": str(error)})
    return JsonResponse({"success": r.is_success, "status_code": r.status_code})


def _quota_bg(pct):
    if pct > 95:
        return "danger"
    if pct > 85:
        return "warning"
    return "secondary"


@csrf_exempt
@require_http_methods(["OPTIONS", "GET"])
@auth_from_token
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix="stats.me")
@vary_on_headers("Authorization")
@vary_on_cookie
def stats_me_view(request):
    """
    View  /api/stats/me/  — dashboard stat cards + chart history for the current user.
    """
    stats = list(FileStats.objects.filter(user=request.user).order_by("-created_at")[:90])

    days, chart_files, chart_size, chart_shorts = [], [], [], []
    for stat in reversed(stats):
        days.append(f"{stat.created_at.month}/{stat.created_at.day}")
        chart_files.append(stat.stats["count"])
        chart_size.append(stat.stats["size"])
        chart_shorts.append(stat.stats["shorts"])

    updated_at = None
    stat_cards = []
    types = []
    if stats:
        s = stats[0]
        updated_at = localtime(s.updated_at).strftime("%-m/%-d %-I:%M %p")
        album_count = Albums.objects.filter(user=request.user).count()
        stat_cards = [
            {
                "icon": "fa-regular fa-folder-open",
                "bg": "primary",
                "value": s.stats["count"],
                "label": "Files",
                "modal": "mime",
            },
            {
                "icon": "fa-solid fa-database",
                "bg": "info",
                "value": s.stats["human_size"],
                "label": "Storage Used",
                "modal": "mime",
            },
            {"icon": "fa-solid fa-link", "bg": "success", "value": s.stats["shorts"], "label": "Short URLs"},
            {"icon": "fa-regular fa-images", "bg": "warning", "value": album_count, "label": "Albums"},
        ]
        if request.user.storage_quota:
            pct = request.user.get_storage_usage_pct()
            stat_cards.append(
                {
                    "icon": "fa-solid fa-hard-drive",
                    "bg": _quota_bg(pct),
                    "value": f"{pct}%",
                    "label": "My Quota",
                    "sublabel": f"{request.user.get_storage_used_human_read()} / {request.user.get_storage_quota_human_read()}",
                }
            )
        raw_types = s.stats.get("types", {})
        types = sorted(
            [
                {
                    "mime": mime or "unknown",
                    "count": d["count"],
                    "size": d["size"],
                    "human_size": Files.get_size_of(d["size"]),
                }
                for mime, d in raw_types.items()
            ],
            key=lambda x: x["count"],
            reverse=True,
        )

    return JsonResponse(
        {
            "has_stats": bool(stats),
            "updated_at": updated_at,
            "stat_cards": stat_cards,
            "types": types,
            "chart": (
                {"days": days, "files": chart_files, "size": chart_size, "shorts": chart_shorts} if days else None
            ),
        }
    )


_SERVER_STATS_CACHE_KEY = "stats.server.data"
_SERVER_STATS_CACHE_TTL = 60 * 5  # 5 minutes


@csrf_exempt
@require_http_methods(["OPTIONS", "GET"])
@auth_from_token
def stats_server_view(request):
    """
    View  /api/stats/server/  — superuser-only server-wide stat cards + chart.
    Chart reads the server-wide _totals FileStats snapshots (user=None).
    """
    if not request.user.is_superuser:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    cached = cache.get(_SERVER_STATS_CACHE_KEY)
    if cached:
        return JsonResponse(cached)

    # Stat cards: live counts
    total_files = Files.objects.count()
    total_size = Files.objects.aggregate(t=Sum("size"))["t"] or 0
    total_shorts = ShortURLs.objects.count()
    total_albums = Albums.objects.count()
    stat_cards = [
        {
            "icon": "fa-regular fa-folder-open",
            "bg": "primary",
            "value": total_files,
            "label": "Server Files",
            "modal": "mime",
        },
        {
            "icon": "fa-solid fa-database",
            "bg": "info",
            "value": Files.get_size_of(total_size),
            "label": "Server Storage",
            "modal": "mime",
        },
        {"icon": "fa-solid fa-link", "bg": "success", "value": total_shorts, "label": "Server Shorts"},
        {"icon": "fa-regular fa-images", "bg": "warning", "value": total_albums, "label": "Server Albums"},
    ]
    site_settings = SiteSettings.objects.settings()
    if site_settings.global_storage_quota:
        pct = site_settings.get_global_storage_quota_usage_pct()
        stat_cards.append(
            {
                "icon": "fa-solid fa-server",
                "bg": _quota_bg(pct),
                "value": f"{pct}%",
                "label": "System Quota",
                "sublabel": f"{site_settings.get_global_storage_usage_human_read()} / {site_settings.get_global_storage_quota_human_read()}",
            }
        )

    # Chart: read server-wide _totals snapshots (user=None), one per UTC day.
    # Use the latest record per day (by max pk) to handle any historical duplicates.
    cutoff_date = (now() - timedelta(days=90)).date()
    latest_pks = (
        FileStats.objects.filter(user__isnull=True, created_at__date__gte=cutoff_date)
        .values("created_at__date")
        .annotate(latest_pk=Max("id"))
        .values_list("latest_pk", flat=True)
    )
    server_snapshots = list(FileStats.objects.filter(pk__in=latest_pks).order_by("created_at"))

    chart_days = [f"{s.created_at.month}/{s.created_at.day}" for s in server_snapshots]
    chart_files = [s.stats["count"] for s in server_snapshots]
    chart_size = [s.stats["size"] for s in server_snapshots]
    chart_shorts = [s.stats["shorts"] for s in server_snapshots]

    # Mime type breakdown: live query
    server_types = list(Files.objects.values("mime").annotate(count=Count("pk"), size=Sum("size")).order_by("-count"))
    types = [
        {
            "mime": t["mime"] or "unknown",
            "count": t["count"],
            "size": t["size"] or 0,
            "human_size": Files.get_size_of(t["size"] or 0),
        }
        for t in server_types
    ]

    data = {
        "stat_cards": stat_cards,
        "types": types,
        "chart": (
            {"days": chart_days, "files": chart_files, "size": chart_size, "shorts": chart_shorts}
            if chart_days
            else None
        ),
    }
    cache.set(_SERVER_STATS_CACHE_KEY, data, _SERVER_STATS_CACHE_TTL)
    return JsonResponse(data)


@csrf_exempt
@require_http_methods(["OPTIONS", "GET"])
@auth_from_token
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix="files")
@vary_on_headers("Authorization")
@vary_on_cookie
def recent_view(request):
    """
    View  /api/recent/
    """
    log.debug("request.user: %s", request.user)
    log.debug("%s - recent_view: is_secure: %s", request.method, request.is_secure())
    try:
        # query = Files.objects.filtered_request(request).select_related("user")
        query = Files.objects.filter(user=request.user).select_related("user").prefetch_related("albums", "tags__tag")
        if album := request.GET.get("album"):
            query = query.filter(albums__id=album)

        after = int(request.GET.get("after", 0))
        log.debug("after: %s", after)
        if after:
            files = query.filter(id__gt=after)
            return JsonResponse(extract_files(files), safe=False)

        amount = int(request.GET.get("amount", 20))
        log.debug("amount: %s", amount)

        before = int(request.GET.get("before", 0))
        log.debug("before: %s", before)
        if before:
            files = query.filter(id__lt=before)[:amount]
            return JsonResponse(extract_files(files), safe=False)

        start = int(request.GET.get("start", 0))
        log.debug("start: %s", start)
        files = query[start : start + amount]
        return JsonResponse(extract_files(files), safe=False)
    except ValueError as error:
        log.debug(error)
        return JsonResponse({"error": f"{error}"}, status=400)


def _files_base_queryset(request, user, album):
    qs = Files.objects.filtered_request
    prefetch = ("albums", "tags__tag")
    if album:
        return qs(request, albums__id=album).select_related("user").prefetch_related(*prefetch)
    if user == "0":
        # grabs files for ALL users; user parameter only accepted for superusers
        return qs(request).select_related("user").prefetch_related(*prefetch)
    if user:
        return qs(request, user_id=int(user)).select_related("user").prefetch_related(*prefetch)
    return None


def _apply_search_filter(q, request):
    search = request.GET.get("search")
    if not search:
        return q
    if request.GET.get("name_only"):
        return q.filter(name__icontains=search)
    return q.filter(Q(name__icontains=search) | Q(tags__tag__name__icontains=search)).distinct()


@csrf_exempt
@require_http_methods(["OPTIONS", "GET"])
@auth_from_token(no_fail=True)
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix="files")
@vary_on_headers("Authorization")
@vary_on_cookie
def files_view(request, page, count=25):
    """
    View  /api/files/{page}/{count}/
    """
    log.debug("%s - files_page_view: %s", request.method, page)
    user = None
    if request.user.is_superuser:
        user = request.GET.get("user") or request.user.id
    elif request.user.is_authenticated:
        user = request.user.id
    log.debug("user: %s", user)
    q = _files_base_queryset(request, user, request.GET.get("album"))
    if q is None:
        return JsonResponse({"error": "Not Authenticated"}, status=401)
    q = _apply_search_filter(q, request)
    if privacy := request.GET.get("privacy"):
        q = q.filter(private=(privacy == "private"))
    if mime := request.GET.get("mime"):
        q = q.filter(mime__startswith=mime)
    if type_param := request.GET.get("type"):
        type_qs = [_TYPE_Q[ts] for t in type_param.split(",") if (ts := t.strip()) in _TYPE_Q]
        if type_qs:
            q = q.filter(reduce(operator.or_, type_qs))
    if request.GET.get("has_gps"):
        q = q.filter(exif__GPSInfo__isnull=False)
    ordering_param = (request.GET.get("ordering") or "").lstrip("-")
    if ordering_param == "exif_date":
        q = q.annotate(_exif_date=KeyTextTransform("DateTimeOriginal", "exif"))
    q = apply_ordering(
        q,
        request,
        allowed={"created": "date", "size": "size", "name": "name", "exif_date": "_exif_date"},
        default="-created",
    )
    page_items, _next = paginate_no_count(q, page, count)
    files = extract_files(page_items)
    # log.debug("files: %s", files)
    response = {
        "files": files,
        "next": _next,
        "count": count,
    }
    return JsonResponse(response, safe=False, status=200)


@csrf_exempt
@require_http_methods(["DELETE", "POST"])
@auth_from_token
def files_edit_view(request):
    """
    View  /api/files/edit|delete/
    TODO: DO not accept DELETE and force POST to /api/files/delete/
    """
    log.debug("files_edit_view: %s" + request.method)
    try:
        data = get_json_body(request)
        # prevent renaming the visible name on file models, no renaming in bulk for now
        data.pop("name", None)
        log.debug("data: %s", data)
        count = 0
        ids = data.get("ids", [])
        log.debug("ids: %s", ids)
        if not ids:
            return JsonResponse({"error": "No IDs to Process"}, status=400)
        del data["ids"]
        # count = Files.objects.filter(id__in=ids, user=request.user).update(**data)
        queryset = Files.objects.filter(id__in=ids)
        if not queryset:
            # TODO: Determine if this should return 404 or 200 with a 0 response
            log.warning("No queryset for provided file IDs.")
            return HttpResponse(0)
        if not request.user.is_superuser:
            queryset = queryset.filter(user=request.user)
        if request.method == "DELETE" or request.path_info.endswith("/delete/"):
            count, _ = queryset.delete()
        else:
            if "albums" in data:
                # queryset = queryset.prefetch_related('albums')
                # albums = Albums.objects.filter(id__in=data["albums"])
                count = max(count, set_albums(queryset, data["albums"]))
                del data["albums"]
            if data:
                log.debug("data: %s", data)
                count = max(count, queryset.update(**data))
        log.debug("count: %s", count)
        if count:
            log.debug("Flushing Files Cache")
            clear_files_cache.delay()
        return HttpResponse(count)
    except Exception as error:
        log.exception(error)
        return JsonResponse({"error": f"{error}"}, status=400)


def set_albums(queryset: QuerySet, album_ids: List[int]) -> int:
    log.debug("edit_albums: %s: %s", album_ids, queryset)
    albums = Albums.objects.filter(id__in=album_ids)
    log.debug("albums: %s", albums)
    count = 0
    if albums:
        for obj in queryset:
            obj.albums.set(albums)
            count += 1
    log.debug("count: %s", count)
    return count


@csrf_exempt
@require_http_methods(["DELETE", "GET", "OPTIONS", "POST"])
@auth_from_token(no_fail=True)
def file_view(request, idname):
    """
    View  /api/file/{id or name}
    """
    kwargs = id_or_name(idname)
    log.debug("kwargs: %s", kwargs)
    if not request.user.is_superuser and request.user.is_authenticated:
        kwargs["user"] = request.user
    file = get_object_or_404(Files, **kwargs)
    # for unautheticated requests we need to make sure the file is public or has the password
    if not request.user.is_authenticated and (file.private or request.GET.get("password", "") != file.password):
        return JsonResponse({"error": "File not found."}, status=404)
    log.debug("file_view: %s: %s", request.method, file.name)
    try:
        if request.method == "DELETE" and (request.user == file.user or request.user.is_superuser):
            file.delete()
            return HttpResponse(status=204)
        elif request.method == "POST" and (request.user == file.user or request.user.is_superuser):
            log.debug(redact_log(request.POST))
            data = get_json_body(request)
            log.debug("data: %s", data)
            if not data:
                return JsonResponse({"error": json_error_message}, status=400)
            if "expr" in data and not parse(data["expr"]):
                data["expr"] = ""
            # TODO: We should probably not use .update here and convert to a function, see below TODO
            queryset = Files.objects.filter(id=file.id)
            if "albums" in data:
                set_albums(queryset, data["albums"])
                del data["albums"]
            new_name = data.pop("name", None)
            queryset.update(**data)
            if new_name and new_name != file.name:
                if Files.objects.filter(name=new_name).exists():
                    return JsonResponse({"error": "File name already in use."}, status=400)
                file = file_rename(file, new_name)
            else:
                file = Files.objects.get(id=file.id)
            response = extract_files([file])[0]
            # TODO: Determine why we have to manually flush file cache here
            #       The Website seems to flush, but not the api/recent/ endpoint
            #       ANSWER: This is not called on .update(), you must call .save()
            # clear_files_cache.delay()
            # TODO: Calling .save after .update is redundant but fires a .save() method!
            file.save(update_fields=list(data.keys()))
            log.debug("response: %s" % response)
            return JsonResponse(response, status=200)
        elif request.method == "GET":
            response = extract_files([file])[0]
            log.debug("response: %s" % response)
            return JsonResponse(response, status=200)
    except Exception as error:
        log.debug(error)
        return JsonResponse({"error": f"{error}"}, status=400)


@csrf_exempt
@require_http_methods(["OPTIONS", "GET"])
@auth_from_token
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix="albums")
@vary_on_headers("Authorization")
@vary_on_cookie
def albums_view(request, page=None, count=100):
    """
    View  /api/albums/{page}/{count}/
    """
    log.info("%s - albums_page_view: %s - %s", request.method, page, count)
    if request.user.is_superuser:
        user = request.GET.get("user") or request.user.id
    else:
        user = request.user.id
    if user == "0":
        q = Albums.objects.filtered_request(request).select_related("user").prefetch_related("tags__tag")
    else:
        q = (
            Albums.objects.filtered_request(request, user_id=int(user))
            .select_related("user")
            .prefetch_related("tags__tag")
        )
    if search := request.GET.get("search"):
        q = q.filter(Q(name__icontains=search) | Q(tags__tag__name__icontains=search)).distinct()
    if privacy := request.GET.get("privacy"):
        q = q.filter(private=(privacy == "private"))
    q = q.annotate(file_count=Count("files"))
    q = apply_ordering(
        q,
        request,
        allowed={"created": "date", "name": "name", "files": "file_count"},
        default="-created",
    )
    page_items, _next = paginate_no_count(q, page, count)
    albums = extract_albums(page_items, user_id=request.user.id)
    log.debug("albums: %s", albums)
    response = {
        "albums": albums,
        "next": _next,
        "count": count,
    }
    return JsonResponse(response, safe=False, status=200)


@csrf_exempt
@require_http_methods(["OPTIONS", "POST"])
@auth_from_token
def remote_view(request):
    """
    View  /api/remote/
    """
    site_settings = site_settings_processor(None)["site_settings"]
    log.debug("%s - remote_view: is_secure: %s", request.method, request.is_secure())
    log.debug("request.POST: %s", redact_log(request.POST))
    data = get_json_body(request)
    log.debug("data: %s", data)
    if not data:
        return JsonResponse({"error": json_error_message}, status=400)

    url = data.get("url")
    log.debug("url: %s", url)
    if not validators.url(url):
        return JsonResponse({"error": "Missing/Invalid URL"}, status=400)

    parsed_url = urlparse(url)
    log.debug("parsed_url: %s", parsed_url)
    name = os.path.basename(parsed_url.path)
    log.debug("name: %s", name)

    r = httpx.get(url, follow_redirects=True)
    if not r.is_success:
        return JsonResponse({"error": f"{r.status_code} Fetching {url}"}, status=400)

    extra_args = parse_headers(request.headers, expr=parse_expire(request), **request.POST.dict())
    log.debug("extra_args: %s", extra_args)
    file = process_file(name, io.BytesIO(r.content), request.user.id, **extra_args)
    response = {"url": f"{site_settings['site_url'] + file.preview_uri()}"}
    log.debug("response: %s", response)
    return JsonResponse(response)


@login_required
def token_view(request):
    """
    GET  /api/token/ — list this user's API tokens (paginated)
    POST /api/token/ — create a new named token; returns plaintext once
    """
    if request.method == "GET":
        page = int(request.GET.get("page", 1))
        per_page = 20
        qs = request.user.api_tokens.order_by("-created_at")
        paginator = Paginator(qs, per_page)
        pg = paginator.get_page(page)
        tokens = [
            {
                "id": str(t.id),
                "name": t.name,
                "created_at": t.created_at.isoformat(),
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
                "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                "created_ip": t.created_ip,
                "user_agent": t.user_agent,
                "is_active": t.is_active,
            }
            for t in pg
        ]
        return JsonResponse(
            {
                "tokens": tokens,
                "page": pg.number,
                "num_pages": paginator.num_pages,
                "count": paginator.count,
            }
        )
    if request.method == "POST":
        data = get_json_body(request)
        name = data.get("name", "")
        expires_at = None
        if data.get("expires_at"):
            from django.utils.dateparse import parse_datetime

            expires_at = parse_datetime(data["expires_at"])
        plaintext = create_api_token(request.user, request, name=name, expires_at=expires_at)
        return JsonResponse({"token": plaintext})
    return HttpResponseNotAllowed(["GET", "POST"])


@login_required
def token_detail_view(request, pk):
    """
    PATCH  /api/token/<uuid>/ — toggle is_active for a token owned by this user
    DELETE /api/token/<uuid>/ — hard-delete a token owned by this user
    """
    if request.method == "PATCH":
        token = get_object_or_404(ApiToken, pk=pk, user=request.user)
        token.is_active = not token.is_active
        token.save(update_fields=["is_active"])
        return JsonResponse({"status": "active" if token.is_active else "disabled", "is_active": token.is_active})
    if request.method == "DELETE":
        token = get_object_or_404(ApiToken, pk=pk, user=request.user)
        token.delete()
        return JsonResponse({"status": "deleted"})
    return HttpResponseNotAllowed(["PATCH", "DELETE"])


@require_http_methods(["GET"])
def auth_methods(request):
    """
    View     /api/auth/methods/
    returns dictionary of configured auth methods, and branding for native client login pages
    """
    site_settings = SiteSettings.objects.settings()
    state_string = "&state=iOSApp"
    methods = []
    site_url = site_settings.site_url if site_settings.site_url else f"{request.scheme}://{request.get_host()}"
    if site_settings.local_auth:
        methods.append({"name": "local", "url": site_url + reverse("oauth:login")})
    # Passkey login runs entirely in the login page's WebAuthn flow; native
    # clients open the page in a web auth session and ?state=iOSApp tells the
    # backend to hand off via djangofiles:// after auth_complete. Gate on the
    # same precondition the ceremony itself enforces (passkey_auth + site_url).
    if site_settings.passkey_auth and site_settings.site_url:
        # autopasskey=1 tells the login page's JS to fire the ceremony on load
        # so the user doesn't have to tap a second button inside the webview.
        methods.append(
            {
                "name": "passkey",
                "url": site_url + reverse("oauth:login") + "?state=iOSApp&autopasskey=1",
            }
        )
    if site_settings.discord_client_id:
        methods.append({"name": "discord", "url": DiscordOauth.get_login_url(site_settings) + state_string})
    if site_settings.github_client_id:
        methods.append({"name": "github", "url": GithubOauth.get_login_url(site_settings) + state_string})
    if site_settings.google_client_id:
        methods.append({"name": "google", "url": GoogleOauth.get_login_url(site_settings) + state_string})
    return JsonResponse({"authMethods": methods, "siteName": site_settings.site_title})


@ip_rate_limit("10/m")
@csrf_exempt
@require_http_methods(["POST"])
def local_auth_for_native_client(request):
    """
    View     /api/auth/token/
    returns raw token for local auth for native client
    """
    log.debug("request.cookies: %s", request.COOKIES)
    log.debug("request.META: %s", request.META)
    log.debug("request.user: %s", request.user)
    if request.user.is_authenticated:
        # Session still valid — return token from session if still active in DB.
        token = request.session.get("api_token")
        if token and not ApiToken.objects.filter(token_hash=hash_token(token), is_active=True).exists():
            token = None
        if not token:
            token = create_api_token(request.user, request)
        return JsonResponse({"token": token})

    data = get_json_body(request)
    if not data:
        return JsonResponse({"error": json_error_message}, status=400)

    site_settings = SiteSettings.objects.settings()
    if site_settings.get_local_auth():
        user = authenticate(request, username=data.get("username"), password=data.get("password"))
        if user:
            login(request, user)
            token = create_api_token(user, request)
            return JsonResponse({"token": token})

    return HttpResponse(status=401)


def verify_signature(signature, max_age=600):
    original = signer.unsign(signature, max_age=max_age)
    log.debug("original: %s", original)
    data = json.loads(original)
    log.debug("data: %s", data)
    return data


@never_cache
@ip_rate_limit("10/m")
@csrf_exempt
@auth_from_token
@require_http_methods(["POST"])
def auth_session(request):
    """
    View /api/auth/session/
    Exchanges a valid Bearer token for a Django session cookie so native clients
    can refresh expired WebView sessions without re-entering credentials.
    """
    site_settings = SiteSettings.objects.settings()
    if response := pre_login(request, request.user, site_settings):
        return response
    login(request, request.user, backend="django.contrib.auth.backends.ModelBackend")
    post_login(request)
    return HttpResponse(status=204)


@csrf_exempt
@require_http_methods(["POST"])
def auth_application(request):
    """
    View /auth/application/
    """
    try:
        signature = request.POST.get("signature")
        log.debug("signature 1: %s", signature)
        if not signature:
            body = get_json_body(request)
            log.debug("body: %s", body)
            signature = body.get("signature")
            log.debug("signature 2: %s", signature)
        if not signature:
            raise ValueError("No signature provided.")
        log.debug("signature 3: %s", signature)
        data = verify_signature(signature)
        log.debug("user_id: %s", data["user_id"])
        user = CustomUser.objects.get(id=data["user_id"])
        log.debug("username: %s", user.username)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        post_login(request)
        token = create_api_token(user, request)
        return JsonResponse({"token": token})
    except Exception as error:
        log.debug("error: %s", error)
        return JsonResponse({"error": str(error)}, status=400)


@csrf_exempt
@require_http_methods(["DELETE"])
@user_passes_test(lambda user: user.is_superuser)
def session_view(request, sessionid):
    """
    View /session/:id/
    """
    try:
        log.debug("request.user: %s", request.user)
        log.debug("sessionid: %s", sessionid)
        if sessionid == "all":
            keys = cache.keys("django.contrib.sessions.cache*")
            log.debug("keys: %s", keys)
            for key in keys:
                if request.session.session_key not in key:
                    log.debug("cache.delete: %s", key)
                    cache.delete(key)
            return HttpResponse(status=201)

        keys = cache.keys(f"*{sessionid}")
        log.debug("keys: %s", keys)
        if keys:
            log.debug("keys[0]: %s", keys[0])
            cache.delete(keys[0])
            return HttpResponse(status=201)
        else:
            return HttpResponse(status=404)
    except Exception as error:
        log.debug("error: %s", error)
        return HttpResponse(str(error), status=500)


def _resolve_stream_user(name, data):
    """
    Resolve the authenticated user from RTMP tcurl query params via stream_token.
    Returns (user, stream_or_None).
    """
    stream_token = data.get("stream_token", [None])[0]
    if stream_token:
        stream = Stream.objects.filter(stream_token=stream_token, name=name).first()
        if stream:
            return stream.user, stream
        log.debug("_resolve_stream_user: invalid stream_token for name=%s", name)
    return None, None


def _parse_stream_kwargs(data):
    kwargs = {}
    if public := data.get("public"):
        kwargs["public"] = anytobool(public[0])
    if viewer_limit := data.get("viewer_limit"):
        try:
            kwargs["viewer_limit"] = int(viewer_limit[0])
        except ValueError:
            log.error("Invalid viewer_limit: %s", viewer_limit)
    if description := data.get("description"):
        kwargs["description"] = description[0]
    if title := data.get("title"):
        kwargs["title"] = title[0]
    if record := data.get("record"):
        kwargs["record"] = anytobool(record[0])
    return kwargs


@csrf_exempt
def stream_auth_view(request):
    """
    View /stream/auth/
    """
    try:
        log.debug("stream_auth_view: %s - %s", request.method, request.META["PATH_INFO"])
        log.debug("stream_auth_view: %s", redact_log(request.GET))
        name = request.GET.get("name")
        log.debug("name: %s", name)
        if not name:
            log.debug("No Stream Name Provided: %s", name)
            return HttpResponse(status=401)

        url = urlparse(request.GET.get("tcurl", ""))
        data = parse_qs(url.query)
        log.debug("data: %s", redact_log(data))
        user, _ = _resolve_stream_user(name, data)
        log.debug("user: %s", user)
        if not user:
            log.debug("User Authorization Failed: %s", name)
            return HttpResponse(status=401)

        stream_kwargs = _parse_stream_kwargs(data)
        stream, created = Stream.objects.get_or_create(
            name=name, defaults={"user": user, "is_live": True, "started_at": datetime.now(), **stream_kwargs}
        )
        if not created and stream.user != user and not user.is_superuser:
            log.debug("stream_auth_view: name %s owned by %s, rejecting %s", name, stream.user, user)
            return HttpResponse(status=403)
        if not created:
            stream.is_live = True
            stream.started_at = datetime.now()
            for k, v in stream_kwargs.items():
                setattr(stream, k, v)
            stream.save()
        log.debug("stream: %s", stream.__dict__)
        # if the stream ended, we want to set started_at to now, and clear ended_at
        if stream.ended_at:
            log.debug("stream ended, resetting started_at and ended_at")
            stream.started_at = datetime.now()
            stream.ended_at = None
            stream.save()
        StreamHistory.objects.create(stream=stream, title=stream.title, description=stream.description)
        _reset_viewer_stats(stream.name)
        send_push_live.apply_async(args=[stream.name], countdown=10)
        stream_status_websocket.delay(stream.name, True, started_at=stream.started_at.isoformat())
        dispatch_webhook_event.delay(EVENT_STREAM_LIVE, stream.user_id, build_stream_payload(stream))

        return HttpResponse()
    except Exception as error:
        log.debug("error: %s", error)
        return HttpResponse(status=401)


@csrf_exempt
def stream_done_view(request):
    """
    View /stream/done/
    Called by the RTMP server when a stream ends.
    """
    try:
        log.debug("stream_done_view: %s - %s", request.method, request.META["PATH_INFO"])
        log.debug("stream_done_view: %s", redact_log(request.GET))
        name = request.GET.get("name")
        log.debug("name: %s", name)
        if not name:
            return HttpResponse(status=400)

        url = urlparse(request.GET.get("tcurl", ""))
        data = parse_qs(url.query)
        user, _ = _resolve_stream_user(name, data)
        if not user:
            log.debug("stream_done_view: invalid or missing credentials")
            return HttpResponse(status=401)

        stream = Stream.objects.get(name=name)
        log.debug("stream: %s", stream)
        if stream.user != user and not user.is_superuser:
            log.debug("stream_done_view: token belongs to %s, not stream owner %s", user, stream.user)
            return HttpResponse(status=403)

        stream.ended_at = datetime.now()
        stream.is_live = False
        stream.save()

        history = StreamHistory.objects.filter(stream=stream, ended_at__isnull=True).order_by("-started_at").first()
        if history:
            peak, avg = _pop_viewer_stats(stream.name)
            history.ended_at = stream.ended_at
            history.peak_viewers = peak
            history.avg_viewers = avg
            history.save()

        stream_status_websocket.delay(stream.name, False, stream.ended_at.isoformat())
        dispatch_webhook_event.delay(EVENT_STREAM_OFFLINE, stream.user_id, build_stream_payload(stream))

    except Exception as error:
        log.debug("error: %s", error)

    return HttpResponse()


@csrf_exempt
def stream_record_done_view(request):
    """
    View /stream/record/
    Called by nginx-rtmp's on_record_done when a recording file is finalized.
    nginx records every live session unconditionally (record all;); this
    endpoint decides whether to keep it based on Stream.record.
    """
    log.debug("stream_record_done_view: %s", redact_log(request.GET))
    name = request.GET.get("name")
    path = request.GET.get("path")
    if not name or not path:
        log.warning("stream_record_done_view: missing name or path: %s", request.GET)
        return HttpResponse(status=400)

    try:
        stream = Stream.objects.get(name=name)
    except Stream.DoesNotExist:
        # %r (not %s) so a crafted name can't inject fake log lines (CRLF etc.)
        log.warning("stream_record_done_view: unknown stream %r, discarding %r", name, path)
        delete_recording_file(path)
        return HttpResponse()

    history = StreamHistory.objects.filter(stream=stream, recording__isnull=True).order_by("-started_at").first()
    if not stream.record or not history:
        delete_recording_file(path)
        return HttpResponse()

    import_stream_recording.delay(history.pk, path)
    return HttpResponse()


@require_http_methods(["POST"])
@login_required
def stream_create_view(request):
    """
    View /api/stream/create/
    Pre-creates a stream for the authenticated user and returns its stream_token.
    Idempotent: re-fetches and returns an existing stream owned by the user.
    """
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "Stream name is required."}, status=400)
    if not re.match(r"^[A-Za-z0-9_-]{1,64}$", name):
        return JsonResponse(
            {"error": "Stream name must be 1–64 chars of letters, numbers, hyphen, or underscore."},
            status=400,
        )
    title = request.POST.get("title", "").strip() or name
    description = request.POST.get("description", "").strip()
    # Honor the per-user "Default Private" / "Auto Password" toggles on first
    # create only. Stream.public is the inverse of private, so flip the bit.
    defaults = {"user": request.user, "title": title, "description": description}
    if request.user.default_file_private:
        defaults["public"] = False
    if request.user.default_file_password:
        defaults["password"] = rand_string()

    stream, created = Stream.objects.get_or_create(name=name, defaults=defaults)
    if not created and stream.user != request.user:
        return JsonResponse({"error": "Stream name already taken."}, status=409)
    return JsonResponse({"name": stream.name, "stream_token": stream.stream_token})


@require_http_methods(["POST"])
@login_required
def stream_rotate_token_view(request, name):
    """
    View /api/stream/<name>/rotate-token/
    Generates a new stream_token for the given stream (owner only).
    """
    stream = Stream.objects.filter(name=name).first()
    if not stream:
        return JsonResponse({"error": STREAM_NOT_FOUND_ERROR}, status=404)
    if stream.user != request.user and not request.user.is_superuser:
        return JsonResponse({"error": FORBIDDEN_ERROR}, status=403)
    stream.stream_token = rand_string()
    stream.save(update_fields=["stream_token"])
    return JsonResponse({"name": stream.name, "stream_token": stream.stream_token})


def _vlc_url_for(request, stream):
    site_url = site_settings_processor(request)["site_settings"].get("site_url")
    base = site_url.rstrip("/") if site_url else request.build_absolute_uri("/").rstrip("/")
    return f"{base}/hls/{stream.name}.m3u8?token={stream.playback_token}"


@require_http_methods(["POST"])
@login_required
def stream_enable_playback_token_view(request, name):
    """
    View /api/stream/<name>/enable-playback-token/
    Generates (or regenerates) the per-stream playback_token used by native
    players via /hls/?token=. Owner only. Calling on an already-enabled stream
    rotates the token and invalidates every previously-issued raw link.
    """
    stream = Stream.objects.filter(name=name).first()
    if not stream:
        return JsonResponse({"error": STREAM_NOT_FOUND_ERROR}, status=404)
    if stream.user_id != request.user.id and not request.user.is_superuser:
        return JsonResponse({"error": FORBIDDEN_ERROR}, status=403)
    stream.playback_token = rand_string()
    stream.save(update_fields=["playback_token"])
    return JsonResponse(
        {
            "name": stream.name,
            "playback_token": stream.playback_token,
            "enabled": True,
            "url": _vlc_url_for(request, stream),
        }
    )


@require_http_methods(["POST"])
@login_required
def stream_disable_playback_token_view(request, name):
    """
    View /api/stream/<name>/disable-playback-token/
    Clears the playback_token, disabling raw-link playback for this stream.
    Owner only. Existing raw links immediately stop working (after nginx auth
    cache TTL expires for already-validated tokens).
    """
    stream = Stream.objects.filter(name=name).first()
    if not stream:
        return JsonResponse({"error": STREAM_NOT_FOUND_ERROR}, status=404)
    if stream.user_id != request.user.id and not request.user.is_superuser:
        return JsonResponse({"error": FORBIDDEN_ERROR}, status=403)
    # Empty string is the documented "disabled" sentinel for playback_token, not
    # a hardcoded credential — bandit's B105 fires on any "" assigned to a name
    # containing "token", so suppress on both the assignment and the echo back.
    stream.playback_token = ""  # nosec B105
    stream.save(update_fields=["playback_token"])
    return JsonResponse({"name": stream.name, "playback_token": "", "enabled": False})  # nosec B105


@require_http_methods(["GET"])
@login_required
def stream_vlc_url_view(request, name):
    """
    View /api/stream/<name>/vlc-url/

    Owner-only. Returns an absolute /hls/<name>.m3u8?token=<playback_token>
    "raw link" for HLS players (VLC, ffmpeg, hls.js standalone, etc.) that can't
    carry browser cookies. The link is valid until the owner rotates or disables
    the token. Returns 409 if raw-link playback has not been enabled on this
    stream.

    playback_token is independent of stream_token (RTMP ingest), so leaking a
    raw link never grants the ability to publish to the stream.
    """
    stream = Stream.objects.filter(name=name).only("name", "user_id", "playback_token").first()
    # Return 404 for both missing and non-owner so this endpoint can't be used
    # to enumerate which private stream names exist.
    if not stream or (stream.user_id != request.user.id and not request.user.is_superuser):
        return JsonResponse({"error": STREAM_NOT_FOUND_ERROR}, status=404)
    if not stream.playback_token:
        return JsonResponse({"error": "Raw-link playback is disabled.", "enabled": False}, status=409)
    return JsonResponse({"name": stream.name, "url": _vlc_url_for(request, stream), "enabled": True})


@require_http_methods(["GET", "HEAD"])
def stream_hls_auth_view(request):
    """
    View /api/stream/hls-auth/?name=<name>&token=<token>&sig=<sig>&exp=<exp>

    Internal endpoint hit by nginx's auth_request for every /hls/ request.
    Returns 204 if any of the following holds, else 403:

      1. The hls_sig/hls_exp cookie pair (forwarded as ?sig/?exp) is a valid
         signature for the stream. Cookies are issued by live_view only after
         the viewer passes the auth + password gate, so a valid cookie proves
         the bearer already cleared those checks.
      2. ?token matches the stream's non-empty playback_token (owner-issued
         raw link for native players like VLC / ffmpeg).
      3. The stream is public AND not password-protected — public streams
         keep working without any auth, matching the pre-signing behavior.

    Meant to be reached only via nginx's internal subrequest (loopback);
    nginx returns 404 for direct external hits on /api/stream/hls-auth/.
    Nginx caches the response keyed by (name, token, sig, exp) so Django is
    hit at most once per cache window per distinct auth bundle — public-stream
    viewers all share a single cache entry.
    """
    name = request.GET.get("name") or ""
    if not name:
        return HttpResponse(status=403)
    stream = Stream.objects.filter(name=name).only("public", "password", "playback_token").first()
    if not stream:
        return HttpResponse(status=403)
    sig = request.GET.get("sig") or ""
    exp = request.GET.get("exp") or ""
    if verify_hls_cookie(name, sig, exp):
        return HttpResponse(status=204)
    token = request.GET.get("token") or ""
    if token and stream.playback_token and constant_time_compare(token, stream.playback_token):
        return HttpResponse(status=204)
    if stream.public and not stream.password:
        return HttpResponse(status=204)
    return HttpResponse(status=403)


@csrf_exempt
@require_http_methods(["GET"])
@auth_from_token
def stream_ingest_view(request):
    """
    View /stream/ingest/
    Returns the RTMP ingest host for this server, derived the same way
    the web UI does (RTMP_HOST env var → site_url hostname → request host).
    The port comes from the RTMP_PORT env var (default 1935); clients may
    override it locally.
    """
    from home.views import get_rtmp_host

    site_settings = SiteSettings.objects.settings()
    rtmp_host, _ = get_rtmp_host(request, site_settings)
    return JsonResponse({"rtmp_host": rtmp_host, "rtmp_port": settings.RTMP_PORT})


def stream_ping_view(request, name):
    """
    View /stream/ping/:name/
    """
    log.debug("stream_ping_view: name: %s", name)
    session_key = request.session.session_key
    if not session_key:
        log.debug("no session_key: request.session.save()")
        request.session.save()
        session_key = request.session.session_key
    log.debug("stream_ping_view: session_key: %s", session_key)

    key = f"stream:{name}:viewers"
    redis = get_redis_connection("default")
    redis.zadd(key, {session_key: int(now().timestamp())})
    redis.expire(key, 60)
    return HttpResponse()


@require_http_methods(["GET"])
@auth_from_token(no_fail=True)
def stream_hls_token_view(request, name):
    """
    View /stream/hls-token/:name/

    Re-issues the hls_sig/hls_exp cookies so any viewer — anonymous on a public
    stream, session-authenticated user, or native client with a user API token —
    can keep fetching segments past the original signing TTL.

    Gates:
      - private stream: requires authenticated user (session or bearer token).
      - password-protected stream: requires either ?password=... matching, OR a
        still-valid hls_sig/hls_exp cookie pair (rolling refresh — the existing
        cookie is itself proof that the original password check passed).
    """
    stream = Stream.objects.filter(name=name).only("name", "public", "password", "user_id").first()
    if not stream:
        return JsonResponse({"detail": "not found"}, status=404)
    is_owner = request.user.is_authenticated and (request.user.id == stream.user_id or request.user.is_superuser)
    if not is_owner:
        if not stream.public and not request.user.is_authenticated:
            return JsonResponse({"detail": "forbidden"}, status=403)
        if stream.password:
            supplied = request.GET.get("password")
            existing_ok = verify_hls_cookie(
                stream.name, request.COOKIES.get("hls_sig"), request.COOKIES.get("hls_exp")
            )
            if supplied != stream.password and not existing_ok:
                return JsonResponse({"detail": "password required"}, status=403)
    sig, exp = sign_hls_cookie(stream.name)
    ttl = settings.HLS_SIGNED_URL_TTL_SECONDS
    response = JsonResponse({"exp": exp})
    response.set_cookie("hls_sig", sig, max_age=ttl, path="/hls", httponly=True, samesite="Lax")
    response.set_cookie("hls_exp", str(exp), max_age=ttl, path="/hls", httponly=True, samesite="Lax")
    return response


def stream_viewers_view(request, name):
    """
    View /stream/viewers/:name/
    """
    log.debug("stream_viewers_view - name: %s", name)
    log.debug("stream_viewers_view - request.GET: %s", request.GET)
    count = get_viewer_count(name)
    log.debug("stream_viewers_view - count: %s", count)
    if request.headers.get("accept") == "application/json":
        return JsonResponse({"count": count})
    context = {
        "viewers": count,
        "prefix": request.GET.get("prefix") or "",
        "suffix": request.GET.get("suffix") or "",
    }
    log.debug("stream_viewers_view - context: %s", context)
    return render(request, "stream/overlay/viewers.html", context)


@require_http_methods(["GET"])
def stream_subscribers_view(request, name):
    """
    View /stream/subscribers/:name/
    """
    log.debug("stream_subscribers_view - name: %s", name)
    count = PushInformation.objects.filter(group__name=name).count()
    return JsonResponse({"count": count})


@csrf_exempt
@require_http_methods(["GET"])
@auth_from_token(no_fail=True)
def stream_commands_view(request, name):
    """
    View /api/stream/commands/<name>/

    Returns slash commands available to the requesting user for the given stream,
    plus chat context (live_chat, anonymous_chat) so the client knows whether to
    show the input bar.  Auth is optional.
    """
    log.debug("stream_commands_view: name=%s user=%s", name, request.user)
    stream = Stream.objects.filter(name=name).first()
    if not stream:
        return JsonResponse({"error": STREAM_NOT_FOUND_ERROR}, status=404)

    user = request.user
    is_authenticated = bool(getattr(user, "is_authenticated", False) and user.pk)
    is_owner = is_authenticated and (user == stream.user or getattr(user, "is_superuser", False))

    commands = []

    if stream.live_chat:
        commands += [
            {"command": "/join", "args": "", "description": "Join the stream chat", "category": "chat"},
            {"command": "/leave", "args": "", "description": "Leave the stream chat", "category": "chat"},
        ]
        if is_authenticated or stream.anonymous_chat:
            commands.append(
                {
                    "command": "/set-name",
                    "args": "<name>",
                    "description": "Set your chat display name",
                    "category": "chat",
                }
            )
        if is_owner:
            commands += [
                {"command": "/title", "args": "<title>", "description": "Set the stream title", "category": "stream"},
                {
                    "command": "/description",
                    "args": "<description>",
                    "description": "Set the stream description",
                    "category": "stream",
                },
                {
                    "command": "/ban",
                    "args": "<display_name>",
                    "description": "Ban a user from chat",
                    "category": "moderation",
                },
                {
                    "command": "/ban-message-cleanup",
                    "args": "<display_name>",
                    "description": "Remove all messages from a banned user",
                    "category": "moderation",
                },
            ]

    return JsonResponse(
        {
            "stream": name,
            "title": stream.title or "",
            "description": stream.description or "",
            "is_live": stream.is_live,
            "is_public": stream.public,  # model field is `public`
            "live_chat": stream.live_chat,
            "anonymous_chat": stream.anonymous_chat,
            "commands": commands,
        }
    )


def _parse_optional_int(value) -> Optional[int]:
    return int(value) if value not in (None, "") else None


def _apply_stream_patch(stream: Stream, data: dict, request) -> None:
    if "public" in data:
        stream.public = data_or_header(request, data, "public", True, cast=bool)
    if "title" in data:
        stream.title = data_or_header(request, data, "title")
    if "description" in data:
        stream.description = data_or_header(request, data, "description")
    if "password" in data:
        stream.password = data_or_header(request, data, "password")
    if "viewer_limit" in data:
        stream.viewer_limit = data_or_header(request, data, "viewer_limit", 0, cast=int)
    if "record" in data:
        stream.record = data_or_header(request, data, "record", False, cast=bool)
    if "recording_retention_days" in data:
        stream.recording_retention_days = _parse_optional_int(data["recording_retention_days"])
    if "recording_retention_count" in data:
        stream.recording_retention_count = _parse_optional_int(data["recording_retention_count"])


@csrf_exempt
@require_http_methods(["OPTIONS", "PATCH"])
@auth_from_token
def stream_detail_view(request, name: str = None):
    """
    View  /api/stream/<name>/
    """
    try:
        if request.method == "PATCH":
            stream = get_object_or_404(Stream, name=name)
            if stream.user != request.user and not request.user.is_superuser:
                return HttpResponse(status=403)
            data = get_json_body(request)
            _apply_stream_patch(stream, data, request)
            stream.save()
            return JsonResponse(extract_streams([stream], request.user.id)[0])
    except Exception as error:
        log.exception(error)
        return JsonResponse({"error": f"{error}"}, status=400)


@require_http_methods(["GET"])
@auth_from_token
def stream_history_view(request, name: str, page=None, count=25):
    """
    View /api/stream/<name>/history/{page}/{count}/
    Past sessions (StreamHistory) for a stream, most recent first, with a link
    to the recording's normal file preview when one exists.
    """
    stream = get_object_or_404(Stream, name=name)
    if stream.user != request.user and not request.user.is_superuser:
        return HttpResponse(status=403)
    q = StreamHistory.objects.filter(stream=stream).select_related("recording")
    page_items, _next = paginate_no_count(q, page, count)
    site_url = SiteSettings.objects.settings().site_url
    history = [
        {
            "id": h.id,
            "started_at": h.started_at,
            "ended_at": h.ended_at,
            "peak_viewers": h.peak_viewers,
            "avg_viewers": h.avg_viewers,
            "title": h.title,
            "description": h.description,
            "recording_url": site_url + h.recording.preview_uri() if h.recording else None,
            "recording_name": h.recording.name if h.recording else None,
        }
        for h in page_items
    ]
    return JsonResponse({"history": history, "next": _next, "count": count}, status=200)


def get_viewer_count(name):
    log.debug("stream_viewers_view - name: %s", name)
    key = f"stream:{name}:viewers"
    redis = get_redis_connection("default")
    cutoff = int(now().timestamp()) - 60
    count = redis.zcount(key, min=cutoff, max="+inf")
    log.debug("stream_viewers_view - count: %s", count)
    _record_viewer_sample(name, count)
    return count


def _record_viewer_sample(name, count):
    """Accumulate a viewer-count sample, piggybacking on stream_viewers_view polling,
    so peak/avg can be computed for the StreamHistory row when the stream ends."""
    redis = get_redis_connection("default")
    peak_key = f"stream:{name}:peak_viewers"
    current_peak = redis.get(peak_key)
    if current_peak is None or count > int(current_peak):
        redis.set(peak_key, count, ex=3600)
    redis.incrby(f"stream:{name}:viewer_sum", count)
    redis.expire(f"stream:{name}:viewer_sum", 3600)
    redis.incr(f"stream:{name}:viewer_samples")
    redis.expire(f"stream:{name}:viewer_samples", 3600)


def _pop_viewer_stats(name):
    """Read and clear the accumulated peak/avg viewer stats for a finished stream session."""
    redis = get_redis_connection("default")
    peak_key = f"stream:{name}:peak_viewers"
    sum_key = f"stream:{name}:viewer_sum"
    samples_key = f"stream:{name}:viewer_samples"
    peak = int(redis.get(peak_key) or 0)
    total = int(redis.get(sum_key) or 0)
    samples = int(redis.get(samples_key) or 0)
    redis.delete(peak_key, sum_key, samples_key)
    return peak, (total // samples if samples else 0)


def _reset_viewer_stats(name):
    redis = get_redis_connection("default")
    redis.delete(f"stream:{name}:peak_viewers", f"stream:{name}:viewer_sum", f"stream:{name}:viewer_samples")


def get_json_body(request):
    try:
        return json.loads(request.body.decode())
    except Exception as error:
        log.debug(error)
        return {}


def parse_headers(headers: dict, **kwargs) -> dict:
    # TODO: Review This Function
    allowed = [
        "format",
        "embed",
        "password",
        "private",
        "strip-gps",
        "strip-exif",
        "auto-password",
        "expr",
        "avatar",
        "albums",
        "tags",
        "info",
    ]
    data = {}
    # TODO: IMPORTANT: Determine why these values are not 1:1 - meta_preview:embed
    difference_mapping = {"embed": "meta_preview"}
    for key in allowed:
        if key in headers:
            value = headers[key]
            if key in difference_mapping:
                key = difference_mapping[key]
            data[key.replace("-", "_")] = value
    for key, value in kwargs.items():
        key = key.lower()
        if key in allowed:
            key = difference_mapping.get(key, key)
            data[key.replace("-", "_")] = value
    return data


def process_file_upload(request, f: BinaryIO, user_id: int, **kwargs):
    log.debug("user_id: %s", user_id)
    log.debug("kwargs: %s", kwargs)
    site_settings = site_settings_processor(None)["site_settings"]
    name = kwargs.pop("name", f.name)
    file = process_file(name, f, user_id, **kwargs)

    if request.user.username == "anonymous":
        if site_settings["pub_album"]:
            album = Albums.objects.filter(id=site_settings["pub_album"])
            log.debug("album: %s", album)
            if album:
                file.albums.add(album[0])
                file.save()

    data = {
        "files": [site_settings["site_url"] + file.preview_uri()],
        "url": site_settings["site_url"] + file.preview_uri(),
        "raw": site_settings["site_url"] + file.raw_path,
        "r": file.get_url(),
        "name": file.name,
        "size": file.size,
    }
    return JsonResponse(data)


def gen_short(vanity: Optional[str] = None, length: int = 4) -> str:
    if vanity:
        if not ShortURLs.objects.filter(short=vanity):
            return vanity
        else:
            raise ValueError(f"Vanity Taken: {vanity}")
    rand = rand_string(length=length)
    while ShortURLs.objects.filter(short=rand):
        rand = rand_string(length=length)
    return rand


def parse_expire(request) -> str:
    # Get Expiration from POST or Default
    expr = ""
    if request.POST.get("Expires-At") is not None:
        expr = request.POST["Expires-At"].strip()
    elif request.POST.get("ExpiresAt") is not None:
        expr = request.POST["ExpiresAt"].strip()
    elif request.headers.get("Expires-At") is not None:
        expr = request.headers["Expires-At"].strip()
    elif request.headers.get("ExpiresAt") is not None:
        expr = request.headers["ExpiresAt"].strip()
    if expr.lower() in ["0", "never", "none", "null"]:
        return ""
    if parse(expr) is not None:
        return expr
    if request.user.is_authenticated:
        return request.user.default_expire or ""
    return ""


def data_or_header(request, data: dict, value: str, default: Any = "", cast: Callable = str):
    if data and value in data:
        raw = data[value]
    else:
        raw = request.headers.get(value, default)
    if raw == "" and cast is not str:
        return default
    return cast(raw)


def id_or_name(id_name: Union[str, int], name="name") -> dict:
    if id_name.isnumeric():
        return {"id": int(id_name)}
    else:
        return {name: id_name}


def _build_shorts_data(shorts, site_url):
    result = []
    for short in shorts:
        short_dict = model_to_dict(short)
        short_dict["full_url"] = site_url + reverse("home:short", kwargs={"short": short.short})
        result.append(short_dict)
    return result


@csrf_exempt
@require_http_methods(["OPTIONS", "GET"])
@auth_from_token
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix="shorts")
@vary_on_headers("Authorization")
@vary_on_cookie
def shorts_view(request):
    """
    View  /api/shorts/
    """
    log.debug("request.user: %s", request.user)
    log.debug("%s - shorts_view: is_secure: %s", request.method, request.is_secure())
    try:
        query = ShortURLs.objects.filter(user=request.user)

        before = int(request.GET.get("before", 0))
        log.debug("before: %s", before)
        if before:
            shorts = query.filter(id__lt=before)
            return JsonResponse([model_to_dict(short) for short in shorts], safe=False)

        amount = int(request.GET.get("amount", 10))
        log.debug("amount: %s", amount)

        after = int(request.GET.get("after", 0))
        log.debug("after: %s", after)
        if after:
            shorts = query.filter(id__gt=after)[:amount]
            return JsonResponse([model_to_dict(short) for short in shorts], safe=False)

        start = int(request.GET.get("start", 0))
        log.debug("start: %s", start)
        shorts = query[start : start + amount]

        # TODO: Determine why this data only gets modified at this stage
        site_settings = site_settings_processor(None)["site_settings"]
        return JsonResponse(_build_shorts_data(shorts, site_settings["site_url"]), safe=False)

    except ValueError as error:
        log.debug(error)
        return JsonResponse({"error": f"{error}"}, status=400)


@auth_from_token
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix="shorts")
@vary_on_headers("Authorization")
@vary_on_cookie
def shorts_paginated_view(request, page=1, count=100):
    """
    View  /api/shorts/<page>/<count>/
    """
    log.debug("shorts_paginated_view: page=%s count=%s", page, count)
    try:
        if request.user.is_superuser:
            user = request.GET.get("user")
            if user == "0":
                query = ShortURLs.objects.all()
            elif user:
                query = ShortURLs.objects.filter(user_id=int(user))
            else:
                query = ShortURLs.objects.get_request(request)
        else:
            query = ShortURLs.objects.get_request(request)
        query = apply_ordering(
            query,
            request,
            allowed={"created": "created_at", "name": "short", "views": "views"},
            default="-created",
        )
        page_items, _next = paginate_no_count(query, page, count)
        site_settings = site_settings_processor(None)["site_settings"]
        shorts_data = _build_shorts_data(page_items, site_settings["site_url"])
        return JsonResponse({"shorts": shorts_data, "next": _next, "count": count}, status=200)
    except ValueError as error:
        log.debug(error)
        return JsonResponse({"error": f"{error}"}, status=400)


@csrf_exempt
@require_http_methods(["OPTIONS", "DELETE"])
@auth_from_token
def shorts_delete_view(request):
    """
    View  /api/shorts/delete/
    """
    try:
        data = get_json_body(request)
        ids = data.get("ids", [])
        if not ids:
            return JsonResponse({"error": "No IDs provided"}, status=400)
        queryset = ShortURLs.objects.filter(id__in=ids)
        if not request.user.is_superuser:
            queryset = queryset.filter(user=request.user)
        count, _ = queryset.delete()
        if count:
            clear_shorts_cache.delay()
        return HttpResponse(count)
    except Exception as error:
        log.debug(error)
        return JsonResponse({"error": f"{error}"}, status=500)


@csrf_exempt
@require_http_methods(["OPTIONS", "GET"])
@auth_from_token
def users_view(request):
    """
    View  /api/users/
    """
    log.debug("request.user: %s", request.user)
    log.debug("%s - users_view: is_secure: %s", request.method, request.is_secure())

    if not request.user.is_superuser:
        return JsonResponse({"error": "Superuser required"}, status=403)
    try:
        query = CustomUser.objects.all()
        after = int(request.GET.get("after", 0))
        log.debug("after: %s", after)
        if after:
            users = query.filter(id__gt=after)
            return JsonResponse(serialize_users(users), safe=False)

        amount = int(request.GET.get("amount", 20))
        log.debug("amount: %s", amount)

        before = int(request.GET.get("before", 0))
        log.debug("before: %s", before)
        if before:
            users = query.filter(id__lt=before)[:amount]
            return JsonResponse(serialize_users(users), safe=False)

        start = int(request.GET.get("start", 0))
        log.debug("start: %s", start)
        users = query[start : start + amount]
        return JsonResponse(serialize_users(users), safe=False)
    except ValueError as error:
        log.debug(error)
        return JsonResponse({"error": f"{error}"}, status=400)


@csrf_exempt
@require_http_methods(["OPTIONS", "GET"])
@auth_from_token
def users_paginated_view(request, page=1, count=50):
    """
    View  /api/users/<page>/<count>/
    """
    log.debug("users_paginated_view: page=%s count=%s", page, count)
    if not request.user.is_superuser:
        return JsonResponse({"error": "Superuser required"}, status=403)
    try:
        query = CustomUser.objects.select_related("discord", "github", "google").order_by("id")
        page_items, _next = paginate_no_count(query, page, count)
        users_data = serialize_users(page_items)
        for user_dict in users_data:
            user_dict["name"] = user_dict.get("first_name") or user_dict.get("username", "")
        return JsonResponse({"users": users_data, "next": _next, "count": count}, status=200)
    except ValueError as error:
        log.debug(error)
        return JsonResponse({"error": f"{error}"}, status=400)


@csrf_exempt
@require_http_methods(["OPTIONS", "GET", "PATCH"])
@auth_from_token
@cache_control(no_cache=True)
def user_view(request, user_id=None):
    """
    View  /api/user/ | /api/user/{user_id}/
    """
    log.debug("request.user: %s", request.user)
    log.debug("%s - user_view: user_id: %s", request.method, user_id)

    try:
        # Determine target user
        if user_id is None:
            target_user = request.user
        else:
            # Check if requesting own user info or if superuser
            if int(user_id) != request.user.id and not request.user.is_superuser:
                return JsonResponse({"error": "Access Denied"}, status=403)
            target_user = get_object_or_404(CustomUser, id=user_id)

        if request.method == "PATCH":
            data = get_json_body(request)
            log.debug("update data: %s", data)
            if not data:
                return JsonResponse({"error": json_error_message}, status=400)

            if "password" in data:
                target_user.set_password(data.pop("password"))

            if not request.user.is_superuser:
                sensitive_fields = ["authorization", "is_superuser", "is_staff", "password"]
                for field in sensitive_fields:
                    data.pop(field, None)

            if "storage_quota" in data:
                quota_bytes = human_read_to_byte(str(data["storage_quota"]))
                if not isinstance(quota_bytes, int):
                    return JsonResponse({"error": "Invalid storage quota value."}, status=400)
                data["storage_quota"] = quota_bytes

            for key, value in data.items():
                if hasattr(target_user, key):
                    setattr(target_user, key, value)
                else:
                    log.warning("Attempted to update non-existent field: %s", key)

            target_user.save()
            log.debug("User updated successfully")

        return JsonResponse(serialize_user(target_user), safe=False)

    except ValueError as error:
        log.debug(error)
        return JsonResponse({"error": "Invalid user ID"}, status=400)
    except Exception as error:
        log.debug(error)
        return JsonResponse({"error": f"{error}"}, status=400)


@vary_on_cookie
@auth_from_token
def streams_view(request, page=None, count=100):
    """
    View  /api/streams/{page}/{count}/
    """
    log.info("%s - streams_page_view: %s - %s", request.method, page, count)
    if request.user.is_superuser:
        user = request.GET.get("user") or request.user.id
    else:
        user = request.user.id
    if user == "0":
        q = Stream.objects.select_related("user").prefetch_related("tags__tag").all()
    else:
        q = Stream.objects.select_related("user").prefetch_related("tags__tag").filter(user_id=int(user))
    if search := request.GET.get("search"):
        q = q.filter(
            Q(name__icontains=search) | Q(title__icontains=search) | Q(tags__tag__name__icontains=search)
        ).distinct()
    if privacy := request.GET.get("privacy"):
        q = q.filter(public=(privacy == "public"))
    q = apply_ordering(
        q,
        request,
        allowed={"created": "started_at", "name": "name", "views": "unique_views"},
        default="-created",
    )
    page_items, _next = paginate_no_count(q, page, count)
    from home.views import get_rtmp_host

    rtmp_host, _ = get_rtmp_host(request)
    stream_list = page_items
    stream_names = [s.name for s in stream_list]
    subscriber_counts = dict(
        PushInformation.objects.filter(group__name__in=stream_names)
        .values("group__name")
        .annotate(cnt=Count("pk"))
        .values_list("group__name", "cnt")
    )
    streams = extract_streams(
        stream_list,
        request.user.id,
        rtmp_host=rtmp_host,
        rtmp_port=settings.RTMP_PORT,
        subscriber_counts=subscriber_counts,
    )
    log.debug("streams: %s", streams)
    response = {
        "streams": streams,
        "next": _next,
        "count": count,
    }
    return JsonResponse(response, safe=False, status=200)
