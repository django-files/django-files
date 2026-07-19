"""
tusd HTTP hook endpoint (tusd v2 hook protocol).

The tusd sidecar owns the upload transport (chunk assembly, offsets, resume
state) and POSTs hook events here directly at app:9000 over the internal
docker network. nginx returns 404 for this path to external callers — same
containment pattern as /api/stream/hls-auth/ — so tusd is the only reachable
caller. Defense in depth on top of that containment: the view 404s unless
TUS_ENABLED is set, and requires the shared hook secret (TUS_HOOK_SECRET env,
else the file nginx generates on the shared media volume) as a ?secret= query
param — tusd has no flag for static hook headers, so the URL is the channel.

pre-create runs before any bytes transfer: authenticate the uploader, check
the declared Upload-Length against the size cap and storage quotas, then
stamp the resolved user id and the parsed upload options into the upload's
metadata via ChangeFileInfo. Client-supplied values for those keys are always
overwritten, so they cannot be spoofed.

post-finish hands the assembled file to Celery for zero-copy import through
process_file. Import is async: clients learn the file URL from the existing
new-file websocket event, the same completion signal the gallery already uses.
"""

import hmac
import json
import logging
import os
from http.cookies import CookieError, SimpleCookie
from importlib import import_module
from types import SimpleNamespace
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import auth
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from home.tasks import import_tus_upload
from home.util.auth import hash_token
from oauth.models import ApiToken
from pytimeparse2 import parse
from settings.models import SiteSettings

log = logging.getLogger("app")


@csrf_exempt
@require_http_methods(["POST"])
def tus_hook_view(request):
    """
    View  /api/tus/hook/  (internal-only, called by the tusd sidecar)
    """
    if not settings.TUS_ENABLED:
        return JsonResponse({"error": "Not Found."}, status=404)
    if not _hook_secret_valid(request):
        return JsonResponse({"error": "Invalid hook secret."}, status=403)
    try:
        data = json.loads(request.body.decode())
    except ValueError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    hook_type = data.get("Type", "")
    event = data.get("Event") or {}
    log.debug("tus_hook_view: %s", hook_type)
    if hook_type == "pre-create":
        return _pre_create(event)
    if hook_type == "post-finish":
        return _post_finish(event)
    return JsonResponse({})


def _pre_create(event: dict) -> JsonResponse:
    from api.views import _upload_size_error, parse_headers

    upload = event.get("Upload") or {}
    metadata = upload.get("MetaData") or {}
    headers = _lower_headers(event)
    user = _resolve_user(headers, metadata)
    if user is None:
        return _reject(401, "Invalid Authorization.")
    if upload.get("SizeIsDeferred"):
        # quota must be checkable before bytes move; require a declared length
        return _reject(400, "Upload-Length is required.")
    size = upload.get("Size") or 0
    if error_response := _upload_size_error(user, size):
        message = json.loads(error_response.content)["message"]
        return _reject(error_response.status_code, message)

    # Same option channels as upload_view: request headers play the role of
    # request.headers, tus metadata plays the role of POST fields — so option
    # behavior is identical across the XHR and tus endpoints.
    expire = _parse_expire(headers, metadata, user)
    kwargs = parse_headers(headers, expr=expire, **{k.lower(): v for k, v in metadata.items()})
    log.debug("_pre_create: user=%s size=%s kwargs=%s", user.id, size, _redact(kwargs))
    # Credentials never persist past this hook: tusd writes the (rewritten)
    # metadata to the on-disk .info sidecar and echoes it on HEAD requests,
    # and the stamped user_id below already carries the auth result.
    new_meta = {k: v for k, v in metadata.items() if k.lower() not in ("authorization", "token")}
    new_meta["user_id"] = str(user.id)
    new_meta["df_kwargs"] = json.dumps(kwargs)
    return JsonResponse({"ChangeFileInfo": {"MetaData": new_meta}})


def _post_finish(event: dict) -> JsonResponse:
    upload = event.get("Upload") or {}
    metadata = upload.get("MetaData") or {}
    path = (upload.get("Storage") or {}).get("Path", "")
    user_id = metadata.get("user_id", "")
    if not path or not user_id.isdigit():
        # pre-create always stamps user_id; missing means a misconfigured tusd
        log.warning("_post_finish: missing path or user_id, ignoring: %s", upload.get("ID"))
        return JsonResponse({})
    try:
        options = json.loads(metadata.get("df_kwargs") or "{}")
    except ValueError:
        options = {}
    name = metadata.get("name") or metadata.get("filename") or os.path.basename(path)
    import_tus_upload.delay(path, name, int(user_id), options)
    return JsonResponse({})


def _hook_secret_valid(request) -> bool:
    secret = settings.TUS_HOOK_SECRET or _read_hook_secret_file()
    if not secret:
        # fail closed: a correctly composed stack always has the file — the
        # nginx entrypoint generates it on the shared volume at startup
        log.error(
            "tus_hook_view: no hook secret configured (set TUS_HOOK_SECRET or provide %s)",
            settings.TUS_HOOK_SECRET_FILE,
        )
        return False
    return hmac.compare_digest(secret, request.GET.get("secret", ""))


def _read_hook_secret_file() -> str:
    try:
        with open(settings.TUS_HOOK_SECRET_FILE) as f:
            return f.read().strip()
    except OSError:
        return ""


def _redact(kwargs: dict) -> dict:
    return {key: "***" if key == "password" and value else value for key, value in kwargs.items()}


def _reject(status: int, message: str) -> JsonResponse:
    # tusd expects HTTP 200 from the hook itself; RejectUpload + HTTPResponse
    # control status and body of the response the uploading client sees.
    return JsonResponse(
        {
            "RejectUpload": True,
            "HTTPResponse": {
                "StatusCode": status,
                "Body": json.dumps({"error": True, "message": message}),
                "Header": {"Content-Type": "application/json"},
            },
        }
    )


def _lower_headers(event: dict) -> dict:
    """Flatten tusd's HTTPRequest.Header (Go http.Header: name -> [values])
    into a lowercase-keyed dict of first values."""
    header = (event.get("HTTPRequest") or {}).get("Header") or {}
    return {key.lower(): value[0] for key, value in header.items() if value}


def _resolve_user(headers: dict, metadata: dict):
    token = _extract_hook_token(headers, metadata)
    if token:
        api_token = ApiToken.objects.select_related("user").filter(token_hash=hash_token(token)).first()
        if api_token and api_token.is_valid():
            return api_token.user
        # an explicit bad token never falls through to cookie auth
        return None
    # Browser path: session cookie. tusd sits outside Django's CSRF
    # protection, so cookie auth additionally requires an Origin/Referer
    # matching the site — otherwise any web page could upload into a
    # logged-in user's account with their ambient cookies.
    if not _origin_allowed(headers):
        return None
    return _session_user(headers)


def _extract_hook_token(headers: dict, metadata: dict) -> str:
    auth_header = headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    # native clients may put the token in tus metadata instead of a header
    # (mirrors the websocket auth pattern in home.consumers)
    return auth_header or headers.get("token", "") or metadata.get("authorization", "") or metadata.get("token", "")


def _session_user(headers: dict):
    cookies = SimpleCookie()
    try:
        cookies.load(headers.get("cookie", ""))
    except CookieError:
        return None
    morsel = cookies.get(settings.SESSION_COOKIE_NAME)
    if not morsel:
        return None
    engine = import_module(settings.SESSION_ENGINE)
    # auth.get_user validates the session auth hash against the user record,
    # it only needs a request-shaped object carrying the session
    user = auth.get_user(SimpleNamespace(session=engine.SessionStore(morsel.value)))
    return user if user.is_authenticated else None


def _origin_allowed(headers: dict) -> bool:
    origin = headers.get("origin") or headers.get("referer")
    if not origin:
        return False
    netloc = urlparse(origin).netloc
    if not netloc:
        return False
    allowed = set()
    if site_url := SiteSettings.objects.settings().site_url:
        allowed.add(urlparse(site_url).netloc)
    for trusted in getattr(settings, "CSRF_TRUSTED_ORIGINS", []):
        allowed.add(urlparse(trusted).netloc)
    return netloc in allowed


def _parse_expire(headers: dict, metadata: dict, user) -> str:
    # mirrors api.views.parse_expire with tus metadata standing in for POST
    expr = ""
    for source in (
        metadata.get("Expires-At"),
        metadata.get("ExpiresAt"),
        headers.get("expires-at"),
        headers.get("expiresat"),
    ):
        if source is not None:
            expr = source.strip()
            break
    if expr.lower() in ["0", "never", "none", "null"]:
        return ""
    if parse(expr) is not None:
        return expr
    return user.default_expire or ""
