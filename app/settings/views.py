import json
import logging
import zoneinfo
from datetime import datetime, timedelta
from urllib.parse import quote

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.backends.cache import SessionStore
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.signing import TimestampSigner
from django.db import IntegrityError, transaction
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, reverse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from home.util.misc import redact_log
from home.util.webhooks import WEBHOOK_EVENTS
from oauth.models import CustomUser, UserInvites, superuser_exists
from settings.forms import SiteSettingsForm, UserSettingsForm, WelcomeForm
from settings.models import SiteSettings

signer = TimestampSigner()

log = logging.getLogger("app")
_PLACEHOLDER_TOKEN = "<YOUR_API_TOKEN>"  # nosec
cache_seconds = 60 * 60 * 4
SESSION_AUTH_REQUIRED = "Session authentication required."
SETTINGS_SITE_URL = "settings:site"
SETUP_TEMPLATE = "settings/setup.html"
USERNAME_TAKEN = "That username is already taken."


@csrf_exempt
@login_required
def site_view(request):
    """
    View  /settings/site/
    """
    log.debug("site_view: %s", request.method)
    if not request.user.is_superuser:
        return HttpResponse(status=401)

    site_settings = SiteSettings.objects.settings()

    if request.method != "POST":
        invites = UserInvites.objects.select_related("owner").all()
        context = {
            "site_settings": site_settings,
            "invites": invites,
            "sessions": get_sessions(request),
            "timezones": sorted(zoneinfo.available_timezones()),
        }
        return render(request, "settings/site.html", context)

    log.debug(redact_log(request.POST))
    form = SiteSettingsForm(request.POST)
    if not form.is_valid():
        log.debug("form INVALID")
        return JsonResponse(form.errors, status=400)
    data = {"reload": False}
    log.debug(redact_log(form.cleaned_data))

    if not site_settings.site_url:
        data["reload"] = True
    site_settings.site_url = form.cleaned_data["site_url"]
    site_settings.site_title = form.cleaned_data["site_title"]
    site_settings.timezone = form.cleaned_data["timezone"]
    site_settings.site_description = form.cleaned_data["site_description"]
    site_settings.site_color = form.cleaned_data["site_color"]
    site_settings.pub_load = form.cleaned_data["pub_load"]
    site_settings.pub_album = form.cleaned_data["pub_album"]
    site_settings.oauth_reg = form.cleaned_data["oauth_reg"]
    site_settings.local_auth = form.cleaned_data["local_auth"]
    site_settings.duo_auth = form.cleaned_data["duo_auth"]
    site_settings.passkey_auth = form.cleaned_data["passkey_auth"]
    site_settings.site_animations = form.cleaned_data["site_animations"]
    site_settings.tsparticles_enabled = form.cleaned_data["tsparticles_enabled"]
    site_settings.global_storage_quota = form.cleaned_data["global_storage_quota"]
    site_settings.default_user_storage_quota = form.cleaned_data["default_user_storage_quota"]
    site_settings.login_background = form.cleaned_data["login_background"]
    site_settings.background_video = form.cleaned_data["background_video"]
    site_settings.background_picture = form.cleaned_data["background_picture"]
    site_settings.tsparticles_enabled = form.cleaned_data["tsparticles_enabled"]
    site_settings.tsparticles_config = form.cleaned_data["tsparticles_config"]
    site_settings.save()

    if data["reload"]:
        messages.success(request, "Settings Saved Successfully.")
    return JsonResponse(data, status=200)


@csrf_exempt
@login_required
def user_view(request):
    """
    View  /settings/user/
    """
    log.debug("user_view: %s", request.method)
    if request.method != "POST":
        webhooks = request.user.webhooks.all()
        context = {
            "webhooks": webhooks,
            "webhook_events": WEBHOOK_EVENTS,
            "timezones": sorted(zoneinfo.available_timezones()),
            "default_upload_name_formats": CustomUser.UploadNameFormats.choices,
            "user_avatar_choices": CustomUser.UserAvatarChoices.choices,
        }
        return render(request, "settings/user.html", context)

    log.debug(redact_log(request.POST))
    form = UserSettingsForm(request.POST)
    if not form.is_valid():
        log.debug("form INVALID")
        return JsonResponse(form.errors, status=400)
    data = {"reload": False}
    log.debug(redact_log(form.cleaned_data))

    request.user.first_name = form.cleaned_data["first_name"]
    request.user.timezone = form.cleaned_data["timezone"]
    # request.session['timezone'] = form.cleaned_data['timezone']
    request.user.default_expire = form.cleaned_data["default_expire"]

    if request.user.default_color != form.cleaned_data["default_color"]:
        request.user.default_color = form.cleaned_data["default_color"]

    if request.user.nav_color_1 != form.cleaned_data["nav_color_1"]:
        request.user.nav_color_1 = form.cleaned_data["nav_color_1"]
        data["reload"] = True

    if request.user.nav_color_2 != form.cleaned_data["nav_color_2"]:
        request.user.nav_color_2 = form.cleaned_data["nav_color_2"]
        data["reload"] = True

    request.user.remove_exif_geo = form.cleaned_data["remove_exif_geo"]
    request.user.remove_exif = form.cleaned_data["remove_exif"]
    request.user.show_exif_preview = form.cleaned_data["show_exif_preview"]
    request.user.default_upload_name_format = form.cleaned_data["default_upload_name_format"]

    if request.user.user_avatar_choice != form.cleaned_data["user_avatar_choice"]:
        request.user.user_avatar_choice = form.cleaned_data["user_avatar_choice"]
        data["reload"] = True

    request.user.default_file_private = form.cleaned_data["default_file_private"]
    request.user.default_file_password = form.cleaned_data["default_file_password"]
    log.debug("form.cleaned_data.show_exif_preview: %s", form.cleaned_data["show_exif_preview"])
    log.debug("request.user.show_exif_preview: %s", request.user.show_exif_preview)

    request.user.save()
    if data["reload"]:
        messages.success(request, "Settings Saved Successfully.")
    return JsonResponse(data, status=200)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def welcome_view(request):
    """
    View  /settings/welcome/

    First-run setup wizard. While no superuser exists yet, an anonymous visitor
    may create the initial admin account here (bootstrap). Once an admin exists
    the view reverts to its login-required behavior and only personalizes the
    currently authenticated account -- the bootstrap path can never mint a second
    admin.
    """
    site_settings = SiteSettings.objects.settings()

    # First run: no admin exists yet. Show the standalone glass-card setup page
    # so an anonymous visitor can create the initial superuser.
    if not superuser_exists():
        return _first_run_setup(request, site_settings)

    # Security gate: once an admin exists this is an authenticated-only page that
    # merely personalizes the current account -- it can never mint a second admin.
    if not request.user.is_authenticated:
        return redirect("oauth:login")
    if not site_settings.show_setup:
        return redirect(SETTINGS_SITE_URL)

    if request.method == "POST":
        return _welcome_post(request, site_settings)

    context = {"timezones": sorted(zoneinfo.available_timezones())}
    return render(request, "settings/welcome.html", context)


def _welcome_post(request, site_settings):
    """Authenticated first-run personalization (AJAX modal flow)."""
    form = WelcomeForm(request.POST)
    if not form.is_valid():
        log.debug(form.errors)
        return JsonResponse(form.errors, status=400)
    if not request.session.get("oauth_provider") and not form.cleaned_data["password"]:
        return JsonResponse({"password": "This Field is Required."}, status=400)  # nosec B105

    site_settings.show_setup = False
    site_settings.save()
    user = CustomUser.objects.get(pk=request.user.pk)
    user.username = form.cleaned_data["username"]
    log.debug("username: %s", form.cleaned_data["username"])
    user.set_password(form.cleaned_data["password"])
    user.timezone = form.cleaned_data["timezone"]
    user.save()
    if request.user.is_superuser and form.cleaned_data["site_url"]:
        site_settings.site_url = form.cleaned_data["site_url"]
        site_settings.timezone = form.cleaned_data["timezone"]
        site_settings.save()
    login(request, user)
    request.session["login_redirect_url"] = reverse(SETTINGS_SITE_URL)
    messages.info(request, f"Welcome to Django Files {request.user.get_name()}.")
    return HttpResponse(status=200)


def _first_run_setup(request, site_settings):
    """Create the initial superuser on first run via the glass-card setup page."""
    timezones = sorted(zoneinfo.available_timezones())
    if request.method == "GET":
        # Leave site_url/timezone for the client to fill from the browser (real
        # origin incl. port, and the client's IANA timezone); the server may sit
        # behind a proxy that hides the port and cannot know the client's tz.
        context = {
            "timezones": timezones,
            "timezone": site_settings.timezone,
            "site_url": site_settings.site_url or "",
            "username": "",
            "error": None,
        }
        return render(request, SETUP_TEMPLATE, context)

    form = WelcomeForm(request.POST)
    confirm = request.POST.get("confirm_password") or ""
    context = {
        "timezones": timezones,
        "username": request.POST.get("username", ""),
        "site_url": request.POST.get("site_url", ""),
        "timezone": request.POST.get("timezone") or site_settings.timezone,
    }
    if error := _setup_form_error(form, confirm):
        return render(request, SETUP_TEMPLATE, {**context, "error": error}, status=400)

    username = form.cleaned_data["username"]
    try:
        with transaction.atomic():
            # Re-check inside the transaction so two concurrent first-run requests
            # cannot both pass the gate and create separate admin accounts.
            if superuser_exists():
                error = "Setup has already been completed. Please log in."
                return render(request, SETUP_TEMPLATE, {**context, "error": error}, status=409)
            if CustomUser.objects.filter(username=username).exists():
                error = "That username is already taken."
                return render(request, SETUP_TEMPLATE, {**context, "error": error}, status=400)
            user = CustomUser.objects.create_superuser(username=username, password=form.cleaned_data["password"])
            user.timezone = form.cleaned_data["timezone"]
            user.save(update_fields=["timezone"])
            site_settings.show_setup = False
            site_settings.timezone = form.cleaned_data["timezone"]
            if form.cleaned_data["site_url"]:
                site_settings.site_url = form.cleaned_data["site_url"]
            site_settings.save()
    except IntegrityError:
        log.exception("first-run setup: race creating initial superuser")
        return render(request, SETUP_TEMPLATE, {**context, "error": USERNAME_TAKEN}, status=400)

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["login_redirect_url"] = reverse(SETTINGS_SITE_URL)
    messages.info(request, f"Welcome to Django Files {user.get_name()}.")
    log.info("first-run setup: created initial superuser=%s", user.username)
    return redirect(SETTINGS_SITE_URL)


def _setup_form_error(form, confirm):
    """Validate the first-run setup form. Returns an error string or None."""
    if not form.is_valid():
        return next(iter(form.errors.values()))[0]
    password = form.cleaned_data["password"]
    if not password:
        return "Password is required."
    if password != confirm:
        return "Passwords do not match."
    try:
        validate_password(password)
    except ValidationError as error:
        return " ".join(error.messages)
    return None


@login_required
@require_http_methods(["GET"])
def gen_sharex(request):
    """
    View  /settings/sharex/
    """
    log.debug("gen_sharex")
    data = {
        "Version": "15.0.0",
        "Name": f"Django Files - {request.get_host()} - File",
        "DestinationType": "ImageUploader, FileUploader, TextUploader",
        "RequestMethod": "POST",
        "RequestURL": request.build_absolute_uri(reverse("api:upload")),
        "Headers": {
            "Authorization": request.session.get("api_token", _PLACEHOLDER_TOKEN),
            "Expires-At": request.user.default_expire,
        },
        "Body": "MultipartFormData",
        "URL": "{json:url}",
        "FileFormName": "file",
        "ErrorMessage": "{json:error}",
    }
    filename = f"{request.get_host()} - Files.sxcu"
    response = JsonResponse(data, json_dumps_params={"indent": 4})
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_http_methods(["GET"])
def gen_sharex_url(request):
    """
    View  /settings/sharex-url/
    """
    log.debug("gen_sharex_url")
    data = {
        "Version": "15.0.0",
        "Name": f"Django Files - {request.get_host()} - URL",
        "DestinationType": "URLShortener, URLSharingService",
        "RequestMethod": "POST",
        "RequestURL": request.build_absolute_uri(reverse("api:shorten")),
        "Headers": {
            "Authorization": request.session.get("api_token", _PLACEHOLDER_TOKEN),
        },
        "Body": "JSON",
        "URL": "{json:url}",
        "Data": '{"url":"{input}"}',
        "ErrorMessage": "{json:error}",
    }
    filename = f"{request.get_host()} - URL.sxcu"
    response = JsonResponse(data, json_dumps_params={"indent": 4})
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_http_methods(["GET"])
def gen_flameshot(request):
    """
    View  /settings/flameshot/
    """
    context = {
        "site_url": request.build_absolute_uri(reverse("home:upload")),
        "token": request.session.get("api_token", _PLACEHOLDER_TOKEN),
    }
    log.debug("context: %s", context)
    message = render_to_string("scripts/flameshot.sh", context, request)
    response = HttpResponse(message)
    response["Content-Disposition"] = 'attachment; filename="flameshot.sh"'
    return response


@login_required
@require_http_methods(["POST"])
def local_auth_view(request):
    """
    View  /settings/user/local-auth
    Toggle local (username/password) login. Disabling sets an unusable password
    on the user, which makes Django's authenticate() reject password logins.
    Re-enabling requires setting a new password through password_view.
    """
    log.debug("local_auth_view: %s", request.user)
    if not request.session.session_key or not request.session.get("_auth_user_id"):
        return JsonResponse({"error": SESSION_AUTH_REQUIRED}, status=401)

    disable = request.POST.get("disable") == "true"
    if not disable:
        return JsonResponse(
            {"error": "Set a new password to re-enable local login."},
            status=400,
        )
    user = request.user
    has_oauth = hasattr(user, "discord") or hasattr(user, "github") or hasattr(user, "google")
    if not has_oauth:
        return JsonResponse(
            {"error": "Link at least one OAuth provider before disabling local login."},
            status=400,
        )
    user.set_unusable_password()
    user.save()
    update_session_auth_hash(request, user)
    return JsonResponse({"disabled": True}, status=200)


@login_required
@require_http_methods(["POST"])
def password_view(request):
    """
    View  /settings/user/password
    Session-authenticated only — token auth is not applied to this endpoint.
    """
    log.debug("password_view: %s", request.user)
    # Defensive check: only allow real session-authenticated users.
    # auth_from_token is not applied here, but enforce it explicitly so future
    # decorator changes can't silently allow token-based password resets.
    if not request.session.session_key or not request.session.get("_auth_user_id"):
        return JsonResponse({"error": SESSION_AUTH_REQUIRED}, status=401)

    new_password = request.POST.get("new_password", "")
    confirm = request.POST.get("confirm_new_password", "")
    if not new_password:
        return JsonResponse({"new_password": "This field is required."}, status=400)  # nosec B105
    if new_password != confirm:
        return JsonResponse({"confirm_new_password": "Passwords do not match."}, status=400)  # nosec B105
    try:
        validate_password(new_password, user=request.user)
    except ValidationError as error:
        return JsonResponse({"new_password": " ".join(error.messages)}, status=400)

    request.user.set_password(new_password)
    request.user.save()
    update_session_auth_hash(request, request.user)
    return JsonResponse({"success": True}, status=200)


@login_required
@require_http_methods(["POST"])
def delete_account_view(request):
    """
    View  /settings/user/delete
    Permanently deletes the authenticated user's account and all associated data.
    Session-authenticated only — token auth is explicitly rejected.
    CASCADE deletes Albums, Files, ShortURLs, Streams; pre_delete signals remove
    the actual files from storage (local filesystem or S3) and update quotas.
    """
    log.debug("delete_account_view: %s", request.user)
    if not request.session.session_key or not request.session.get("_auth_user_id"):
        return JsonResponse({"error": SESSION_AUTH_REQUIRED}, status=401)

    expected_phrase = f"delete {request.user.username} and all associated data"
    confirm_phrase = request.POST.get("confirm_phrase", "").strip()
    if not confirm_phrase:
        return JsonResponse({"error": "Confirmation phrase is required."}, status=400)
    if confirm_phrase != expected_phrase:
        return JsonResponse({"error": "Confirmation phrase did not match. Please try again."}, status=400)

    site_settings = SiteSettings.objects.settings()
    if site_settings.duo_auth:
        from oauth.views import duo_redirect

        request.session["pending_account_delete"] = True
        try:
            url = duo_redirect(request, request.user.username)
        except ValueError:
            del request.session["pending_account_delete"]
            log.exception("delete_account_view: Duo health check failed")
            return JsonResponse({"error": "Duo is unavailable. Please try again later."}, status=503)
        return JsonResponse({"duo_redirect": url}, status=200)

    user = request.user
    log.warning("delete_account_view: deleting account for user %s (id=%s)", user.username, user.pk)
    logout(request)
    user.delete()
    return JsonResponse({"redirect": reverse("oauth:login")}, status=200)


@login_required
def signature_view(request):
    """
    View  /settings/user/signature
    """
    signature = get_signature(user_id=request.user.id)
    url = get_signed_url(request)
    return JsonResponse({"signature": signature, "url": url})


@login_required
def qr_view(request):
    """
    View  /settings/user/qr.png
    """
    url = get_signed_url(request)
    img = qrcode.make(url)
    # TODO: Add a valid MEDIA_ROOT variable since MEDIA_ROOT=/data/media/assets/files
    path = f"{settings.MEDIA_ROOT}/qr/{request.user.id}.png"
    log.debug("path: %s", path)
    img.save(path)
    return FileResponse(open(path, "rb"), content_type="image/png")


def get_sessions(request, exclude_current=False):
    log.debug("get_sessions: %s", request.session.session_key)
    user_map = {str(user.id): user.get_name() for user in CustomUser.objects.all()}
    prefix = "django.contrib.sessions.cache"
    sessions = []
    for key in cache.keys(f"{prefix}*"):
        session_key = key[len(prefix) :]
        log.debug("session_key: %s", session_key)
        # data = cache.get(key)
        session = SessionStore(session_key=session_key)
        data = session.load()
        now = datetime.now()
        if "_auth_user_id" in data:
            if session_key == request.session.session_key:
                if exclude_current:
                    continue
                data["current"] = True
            data["key"] = session_key
            data["ttl"] = cache.ttl(key)
            data["age"] = session.get_expiry_age()
            data["date"] = now + timedelta(seconds=data["ttl"])
            data["user_id"] = data["_auth_user_id"]
            data["user_name"] = user_map.get(data["user_id"], "Deleted")
            log.debug("data: %s", data)
            sessions.append(data)
    sessions.sort(key=lambda x: x["date"], reverse=True)
    log.debug("sessions: %s", sessions)
    return sessions


def get_signed_url(request):
    site_settings = SiteSettings.objects.settings()
    signature = get_signature(user_id=request.user.id)
    log.debug("signature: %s", signature)
    data = {"url": site_settings.site_url, "signature": signature}
    log.debug("data: %s", data)
    scheme = "djangofiles"
    host = "authorize"
    path = "/"
    query = "&".join(f"{quote(k)}={quote(v)}" for k, v in data.items())
    url = f"{scheme}://{host}{quote(path)}?{query}"
    return url


def get_signature(**kwargs):
    value = json.dumps(kwargs)
    signature = signer.sign(value)
    return signature
