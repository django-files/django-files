import json
import logging
import zoneinfo
from datetime import datetime, timedelta
from urllib.parse import quote

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.backends.cache import SessionStore
from django.core.cache import cache
from django.core.signing import TimestampSigner
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, reverse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from oauth.models import CustomUser, DiscordWebhooks, UserInvites
from settings.forms import SiteSettingsForm, UserSettingsForm, WelcomeForm
from settings.models import SiteSettings


signer = TimestampSigner()

log = logging.getLogger("app")
cache_seconds = 60 * 60 * 4


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
        invites = UserInvites.objects.all()
        context = {
            "site_settings": site_settings,
            "invites": invites,
            "sessions": get_sessions(request),
            "timezones": sorted(zoneinfo.available_timezones()),
        }
        return render(request, "settings/site.html", context)

    log.debug(request.POST)
    form = SiteSettingsForm(request.POST)
    if not form.is_valid():
        log.debug("form INVALID")
        return JsonResponse(form.errors, status=400)
    data = {"reload": False}
    log.debug(form.cleaned_data)

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
        webhooks = DiscordWebhooks.objects.get_request(request)
        context = {
            "webhooks": webhooks,
            "timezones": sorted(zoneinfo.available_timezones()),
            "default_upload_name_formats": CustomUser.UploadNameFormats.choices,
            "user_avatar_choices": CustomUser.UserAvatarChoices.choices,
        }
        return render(request, "settings/user.html", context)

    log.debug(request.POST)
    form = UserSettingsForm(request.POST)
    if not form.is_valid():
        log.debug("form INVALID")
        return JsonResponse(form.errors, status=400)
    data = {"reload": False}
    log.debug(form.cleaned_data)

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
@login_required
def welcome_view(request):
    """
    View  /settings/welcome/
    """
    site_settings = SiteSettings.objects.settings()

    if not site_settings.show_setup:
        return redirect("settings:site")

    if request.method == "POST":
        form = WelcomeForm(request.POST)
        if not form.is_valid():
            log.debug(form.errors)
            return JsonResponse(form.errors, status=400)

        if not request.session.get("oauth_provider") and not form.cleaned_data["password"]:
            return JsonResponse({"password": "This Field is Required."}, status=400)

        site_settings.show_setup = False
        site_settings.save()
        user = CustomUser.objects.get(pk=request.user.pk)
        user.username = form.cleaned_data["username"]
        log.debug("username: %s", form.cleaned_data["username"])
        user.set_password(form.cleaned_data["password"])
        log.debug("password: %s", form.cleaned_data["password"])
        user.timezone = form.cleaned_data["timezone"]
        user.save()
        if request.user.is_superuser and form.cleaned_data["site_url"]:
            site_settings = SiteSettings.objects.settings()
            site_settings.site_url = form.cleaned_data["site_url"]
            site_settings.timezone = form.cleaned_data["timezone"]
            site_settings.save()
        login(request, user)
        request.session["login_redirect_url"] = reverse("settings:site")
        messages.info(request, f"Welcome to Django Files {request.user.get_name()}.")
        return HttpResponse(status=200)

    context = {"timezones": sorted(zoneinfo.available_timezones())}
    return render(request, "settings/welcome.html", context)


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
            "Authorization": request.user.authorization,
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
            "Authorization": request.user.authorization,
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
    context = {"site_url": request.build_absolute_uri(reverse("home:upload")), "token": request.user.authorization}
    log.debug("context: %s", context)
    message = render_to_string("scripts/flameshot.sh", context, request)
    response = HttpResponse(message)
    response["Content-Disposition"] = 'attachment; filename="flameshot.sh"'
    return response


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
