import logging
from fractions import Fraction
from urllib.parse import quote, urlparse

import markdown
from api.views import auth_from_token, parse_expire, process_file_upload
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import (
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.cache import cache_control, cache_page
from django.views.decorators.common import no_append_slash
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie
from home.models import Albums, Files, FileStats, ShortURLs, Stream
from home.tasks import clear_shorts_cache, process_stats
from home.util.misc import redact_log
from home.util.s3 import use_s3
from home.util.storage import fetch_file, fetch_raw_file
from oauth.forms import UserForm
from oauth.models import CustomUser, DiscordWebhooks, UserInvites
from oauth.providers.discord import DiscordOauth
from oauth.providers.github import GithubOauth
from oauth.providers.google import GoogleOauth
from settings.context_processors import site_settings_processor
from settings.models import SiteSettings
from webpush.models import PushInformation

log = logging.getLogger("app")
cache_seconds = 60 * 60 * 4
_404_TEMPLATE = "error/404.html"

CODE_MIMES = frozenset(
    [
        "application/json",
        "application/javascript",
        "application/x-perl",
        "application/x-sh",
    ]
)

MIME_TO_DISCORD_LANG = {
    "application/json": "json",
    "application/javascript": "js",
    "application/x-sh": "bash",
    "application/x-perl": "perl",
    "text/javascript": "js",
    "text/typescript": "ts",
    "text/x-python": "python",
    "text/x-java-source": "java",
    "text/x-c": "c",
    "text/x-c++src": "cpp",
    "text/x-ruby": "ruby",
    "text/x-rust": "rust",
    "text/x-go": "go",
    "text/x-shellscript": "bash",
    "text/x-yaml": "yaml",
    "text/xml": "xml",
    "text/html": "html",
    "text/css": "css",
    "text/x-sql": "sql",
    "text/x-lua": "lua",
    "text/x-swift": "swift",
    "text/x-kotlin": "kotlin",
    "text/x-scala": "scala",
    "text/x-haskell": "haskell",
    "text/x-r": "r",
    "text/x-matlab": "matlab",
    "text/x-makefile": "makefile",
    "text/x-dockerfile": "dockerfile",
    "text/x-toml": "toml",
    "text/x-ini": "ini",
}


def get_rtmp_host(request, site_settings=None):
    """
    Return (rtmp_host, is_custom) for RTMP URL generation.

    Priority:
      1. RTMP_HOST env var — explicit admin override (is_custom=True)
      2. site_settings.site_url hostname
      3. request.get_host() stripped of port
    """
    if django_settings.RTMP_HOST:
        return django_settings.RTMP_HOST, True
    if site_settings and site_settings.site_url:
        return urlparse(site_settings.site_url).hostname, False
    return request.get_host().split(":")[0], False


def detect_cdn(request):
    """Return CDN name if a known CDN proxy is detected via request headers, else None."""
    if request.META.get("HTTP_CF_RAY"):
        return "Cloudflare"
    if request.META.get("HTTP_X_AMZ_CF_ID"):
        return "CloudFront"
    return None


def _build_chart_data(qs):
    days, chart_files, chart_size, chart_shorts = [], [], [], []
    for stat in reversed(qs):
        days.append(f"{stat.created_at.month}/{stat.created_at.day}")
        chart_files.append(stat.stats["count"])
        chart_size.append(stat.stats["size"])
        chart_shorts.append(stat.stats["shorts"])
    return days, chart_files, chart_size, chart_shorts


def _quota_bg(pct):
    if pct > 95:
        return "danger"
    if pct > 85:
        return "warning"
    return "secondary"


def _build_user_stat_cards(request, stats):
    if not stats:
        return []
    s = stats[0]
    album_count = Albums.objects.filter(user=request.user).count()
    cards = [
        {"icon": "fa-regular fa-folder-open", "bg": "primary", "value": s.stats["count"], "label": "Files"},
        {"icon": "fa-solid fa-database", "bg": "info", "value": s.stats["human_size"], "label": "Storage Used"},
        {"icon": "fa-solid fa-link", "bg": "success", "value": s.stats["shorts"], "label": "Short URLs"},
        {"icon": "fa-regular fa-images", "bg": "warning", "value": album_count, "label": "Albums"},
    ]
    if request.user.storage_quota:
        pct = request.user.get_storage_usage_pct()
        quota_label = f"My Quota &mdash; {request.user.get_storage_used_human_read()} / {request.user.get_storage_quota_human_read()}"
        cards.append(
            {"icon": "fa-solid fa-hard-drive", "bg": _quota_bg(pct), "value": f"{pct}%", "label": quota_label}
        )
    return cards


def _build_server_stat_cards(stats_server):
    if not stats_server:
        return []
    ss = stats_server[0]
    server_album_count = Albums.objects.count()
    cards = [
        {"icon": "fa-regular fa-folder-open", "bg": "primary", "value": ss.stats["count"], "label": "Server Files"},
        {
            "icon": "fa-solid fa-database",
            "bg": "info",
            "value": ss.stats["human_size"],
            "label": "Server Storage Used",
        },
        {"icon": "fa-solid fa-link", "bg": "success", "value": ss.stats["shorts"], "label": "Server Shorts"},
        {"icon": "fa-regular fa-images", "bg": "warning", "value": server_album_count, "label": "Server Albums"},
    ]
    site_settings = SiteSettings.objects.settings()
    if site_settings.global_storage_quota:
        pct = site_settings.get_global_storage_quota_usage_pct()
        quota_label = f"System Quota &mdash; {site_settings.get_global_storage_usage_human_read()} / {site_settings.get_global_storage_quota_human_read()}"
        cards.append({"icon": "fa-solid fa-server", "bg": _quota_bg(pct), "value": f"{pct}%", "label": quota_label})
    return cards


@cache_control(no_cache=True)
@login_required
@cache_page(cache_seconds, key_prefix="files.stats.shorts")
@vary_on_cookie
def home_view(request):
    """
    View  /
    """
    log.debug("%s - home_view: is_secure: %s", request.method, request.is_secure())
    stats = FileStats.objects.get_request(request)
    days, chart_files, chart_size, chart_shorts = _build_chart_data(stats)

    context = {
        "stats": stats,
        "full_context": True,
        "use_simple_bulk_btn": True,
        "days": days,
        "chart_files": chart_files,
        "chart_size": chart_size,
        "chart_shorts": chart_shorts,
        "user_stat_cards": _build_user_stat_cards(request, stats),
    }

    if request.user.is_superuser:
        stats_server = FileStats.objects.filter(user=None).order_by("-created_at")
        server_days, server_chart_files, server_chart_size, server_chart_shorts = _build_chart_data(stats_server)
        context.update(
            {
                "stats_server": stats_server,
                "server_days": server_days,
                "server_chart_files": server_chart_files,
                "server_chart_size": server_chart_size,
                "server_chart_shorts": server_chart_shorts,
                "server_stat_cards": _build_server_stat_cards(stats_server),
            }
        )

    return render(request, "home.html", context)


@vary_on_cookie
def live_view(request, key):
    """
    View  /live/:key/
    """
    log.debug("%s - live_view: is_secure: %s", request.method, request.is_secure())
    stream = get_object_or_404(Stream, name=key)
    if not stream.public and not request.user.is_authenticated:
        return render(request, _404_TEMPLATE, status=404)
    is_owner = request.user.is_authenticated and (stream.user_id == request.user.id or request.user.is_superuser)
    chat_user_info = {}
    if request.user.is_authenticated:
        chat_user_info = {
            "user_id": request.user.id,
            "username": request.user.username,
            "display_name": request.user.get_name(),
            "avatar_url": request.user.get_avatar_url(),
        }
    site_url = site_settings_processor(request)["site_settings"]["site_url"]
    context = {
        "key": key,
        "webpush": {"group": key},
        "stream": stream,
        "is_owner": is_owner,
        "chat_user_info": chat_user_info,
        "subscriber_count": PushInformation.objects.filter(group__name=key).count(),
        "native_app_arg": (
            f"djangofiles://stream/?url={site_url}"
            f"&name={quote(stream.name)}" + (f"&password={quote(stream.password)}" if stream.password else "")
        ),
    }
    if is_owner:
        site_settings = SiteSettings.objects.settings()
        rtmp_host, rtmp_host_is_custom = get_rtmp_host(request, site_settings)
        context["rtmp_host"] = rtmp_host
        context["rtmp_host_is_custom"] = rtmp_host_is_custom
        context["cdn_detected"] = None if rtmp_host_is_custom else detect_cdn(request)
        context["stream_token"] = stream.stream_token
    return render(request, "live.html", context)


@vary_on_cookie
def live_manifest_view(request, key):
    """
    View  /live/:key/manifest.json
    """
    log.debug("%s - live_manifest_view: is_secure: %s", request.method, request.is_secure())
    stream = get_object_or_404(Stream, name=key)
    if not stream.public and not request.user.is_authenticated:
        return render(request, _404_TEMPLATE, status=404)
    data = {
        "name": stream.title,
        "short_name": stream.name,
        "start_url": f"/live/{key}/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#003366",
        "icons": [{"src": "/static/images/logo.png", "sizes": "192x192", "type": "image/png"}],
        "scope": "/",
        "id": stream.name,
    }
    return JsonResponse(data)


@cache_control(no_cache=True)
@login_required
@cache_page(cache_seconds, key_prefix="stats.shorts")
@vary_on_cookie
def stats_view(request):
    """
    View  /stats/
    """
    log.debug("%s - home_view: is_secure: %s", request.method, request.is_secure())
    shorts = ShortURLs.objects.get_request(request)
    stats = FileStats.objects.get_request(request)
    log.debug("stats: %s", stats)
    days, files, size = [], [], []
    for stat in reversed(stats):
        days.append(f"{stat.created_at.month}/{stat.created_at.day}")
        files.append(stat.stats["count"])
        size.append(stat.stats["size"])
    context = {"stats": stats, "days": days, "files": files, "size": size, "shorts": shorts}
    log.debug("context: %s", context)
    return render(request, "stats.html", context=context)


def files_view(request):
    """
    View  /files/ or /gallery/
    """
    album = request.GET.get("album")
    view_mode = request.GET.get("view", "list")
    if view_mode not in {"list", "gallery", "map"}:
        view_mode = "list"
    ctx = {"full_context": False, "view_mode": view_mode}
    if album:
        try:
            album = int(album)
        except ValueError:
            pass
        if isinstance(album, int):
            album = get_object_or_404(Albums, id=album)
        elif isinstance(album, str):
            album = get_object_or_404(Albums, name=album, password=request.GET.get("password"))
            return HttpResponseRedirect(f"{request.path}?album={album.id}")
        else:
            return HttpResponseNotFound()
        if (request.user.is_authenticated and request.user == album.user) or request.user.is_superuser:
            ctx.update({"full_context": True})
        ctx.update({"album": album, "album_file_count": album.files_set.count()})
        site_url = site_settings_processor(request)["site_settings"]["site_url"]
        ctx.update(
            {
                "native_app_arg": (
                    f"djangofiles://album/?url={site_url}" f"&album_id={album.id}" f"&album_name={quote(album.name)}"
                )
            }
        )
        if lock := handle_lock(request, ctx):
            return lock
        session_view = request.session.get(f"view_album_{album.id}", True)
        log.debug(f"User {request.user} has not viewed album {album.name}: {session_view}")
        if session_view:
            if album.maxv and album.maxv <= album.view and album.user != request.user:
                return render(request, "error/403.html", status=403)
            request.session[f"view_album_{album.id}"] = False
            Albums.objects.filter(pk=album.id).update(view=F("view") + 1)
    else:
        if request.user.is_authenticated or request.user.is_superuser:
            ctx.update({"full_context": True})
    if not request.user.is_authenticated and (not album or album.private):
        return HttpResponseRedirect(reverse("oauth:login"))
    elif request.user.is_superuser:
        users = CustomUser.objects.all()
        ctx.update({"users": users})
    log.debug("%s - gallery_view: is_secure: %s", request.method, request.is_secure())
    return render(request, "gallery.html", ctx)


@cache_control(no_cache=True)
@login_required
@cache_page(cache_seconds, key_prefix="shorts")
@vary_on_cookie
def shorts_view(request):
    """
    View  /shorts/
    """
    log.debug("%s - shorts_view: is_secure: %s", request.method, request.is_secure())
    context = {}
    if request.user.is_superuser:
        context["users"] = CustomUser.objects.all()
    return render(request, "shorts.html", context)


@cache_control(no_cache=True)
@login_required
@cache_page(cache_seconds, key_prefix="albums")
@vary_on_cookie
def albums_view(request):
    """
    View  /albums/
    """
    log.debug("%s - albums_view: is_secure: %s", request.method, request.is_secure())
    albums = Albums.objects.get_request(request)
    context = {"albums": albums}
    if request.user.is_superuser:
        context["users"] = CustomUser.objects.all()
    return render(request, "albums.html", context)


@cache_control(no_cache=True)
@login_required
@cache_page(cache_seconds, key_prefix="streams")
@vary_on_cookie
def streams_view(request):
    """
    View  /streams/
    """
    log.debug("%s - streams_view: is_secure: %s", request.method, request.is_secure())
    site_settings = SiteSettings.objects.settings()
    rtmp_host, rtmp_host_is_custom = get_rtmp_host(request, site_settings)
    cdn_detected = None if rtmp_host_is_custom else detect_cdn(request)
    if request.user.is_superuser:
        users = CustomUser.objects.all()
        context = {
            "users": users,
            "full_context": True,
            "rtmp_host": rtmp_host,
            "rtmp_host_is_custom": rtmp_host_is_custom,
            "cdn_detected": cdn_detected,
        }
    else:
        context = {
            "full_context": True,
            "rtmp_host": rtmp_host,
            "rtmp_host_is_custom": rtmp_host_is_custom,
            "cdn_detected": cdn_detected,
        }
    return render(request, "streams.html", context)


@csrf_exempt
@cache_control(no_cache=True)
@login_required
def uppy_view(request):
    """
    View  /uppy/
    """
    return render(request, "uppy.html")


@csrf_exempt
@cache_control(no_cache=True)
@login_required
def paste_view(request):
    """
    View  /paste/
    """
    context = {
        "default_upload_name_formats": CustomUser.UploadNameFormats.choices,
    }
    return render(request, "paste.html", context=context)


@csrf_exempt
@cache_control(no_cache=True)
def pub_uppy_view(request):
    """
    View  /public/
    """
    log.debug("%s - pub_uppy_view", request.method)
    log.debug("request.user: %s", request.user)
    try:
        site_settings = SiteSettings.objects.settings()
        log.debug("site_settings: %s", site_settings)
        if not site_settings.pub_load:
            if request.user.is_authenticated:
                messages.warning(request, "You Must Enable Public Uploads.")
                return HttpResponseRedirect(reverse("settings:site"))
            return HttpResponseRedirect(reverse("oauth:login") + "?next=" + reverse("home:public-uppy"))

        if request.method == "POST":
            if not (f := request.FILES.get("file")):
                return JsonResponse({"error": "No File Found at Key: file"}, status=400)
            kwargs = {"expr": parse_expire(request), "info": request.POST.get("info")}
            if not request.user.is_authenticated:
                request.user, _ = CustomUser.objects.get_or_create(username="public")
            return process_file_upload(request, f, request.user.id, **kwargs)

        return render(request, "uppy.html")
    except Exception as error:
        log.exception(error)
        return JsonResponse({"error": str(error)}, status=500)


@csrf_exempt
def invite_view(request, invite=None):
    """
    View  /i/
    """
    log.debug("request.method: %s", request.method)
    if request.user.is_authenticated:
        log.debug("request.user.is_authenticated: %s", request.user.is_authenticated)
        return redirect("home:index")
    if request.method == "POST":
        log.debug("request.POST: %s", redact_log(request.POST))
        invite = UserInvites.objects.get_invite(invite)
        log.debug("invite: %s", invite)
        if not invite or not invite.is_valid():
            return HttpResponse(status=400)

        form = UserForm(request.POST)
        if not form.is_valid():
            return JsonResponse(form.errors, status=400)
        log.debug("username: %s", form.cleaned_data["username"])
        if invite.super_user:
            user = CustomUser.objects.create_superuser(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
                storage_quota=invite.storage_quota,
            )
        else:
            user = CustomUser.objects.create_user(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
                storage_quota=invite.storage_quota,
            )
        log.debug("user: %s", user)
        if not invite.use_invite(user.id):
            return JsonResponse(form.errors, status=400)
        login(request, user)
        request.session["login_redirect_url"] = reverse("settings:user")
        messages.info(request, f"Welcome to Django Files {request.user.get_name()}.")
        return HttpResponse(status=200)

    log.debug("request.GET: %s", request.GET)
    context = {}
    if invite := UserInvites.objects.get_invite(invite):
        log.debug("invite: %s", invite)
        if invite.is_valid():
            context = {"invite": invite}
    log.debug("context: %s", context)
    return render(request, "invite.html", context=context)


_invite_provider_map = {
    "discord": DiscordOauth,
    "github": GithubOauth,
    "google": GoogleOauth,
}


def invite_oauth_view(request, invite: str, provider: str):
    """
    View  /i/<invite>/oauth/<provider>/
    Stores the invite code in the session then redirects to the OAuth provider.
    """
    if request.user.is_authenticated:
        return redirect("home:index")
    site_settings = SiteSettings.objects.settings()
    invite_obj = UserInvites.objects.get_invite(invite)
    if not invite_obj or not invite_obj.is_valid():
        return HttpResponse(status=400)
    provider_cls = _invite_provider_map.get(provider)
    if not provider_cls:
        return HttpResponse(status=400)
    request.session["oauth_invite"] = invite
    return provider_cls.redirect_login(request, site_settings)


def shorten_short_view(_request, short):
    """
    View  /s/{short}
    """
    q = get_object_or_404(ShortURLs, short=short)
    url = q.url
    q.views += 1
    if q.max and q.views >= q.max:
        q.delete()
    else:
        q.save()
    clear_shorts_cache.delay()
    return HttpResponseRedirect(url)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_stats_ajax(request):
    """
    View  /ajax/update/stats/
    """
    log.debug("update_stats_ajax")
    process_stats.delay()
    messages.success(request, "Stats Processing Queued.")
    return HttpResponse(status=204)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def delete_file_ajax(request, pk):
    """
    View  /ajax/delete/file/<int:pk>/
    TODO: Implement into /files/ using DELETE method
    """
    log.debug("del_hook_view_a: %s", pk)
    file = get_object_or_404(Files, pk=pk)
    if file.user != request.user:
        return HttpResponse(status=401)
    log.debug(file)
    file.delete()
    return HttpResponse(status=204)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def set_password_file_ajax(request, pk):
    """
    View  /ajax/set_password/file/<int:pk>/
    """
    log.debug("password_hook_view_a: %s", pk)
    file = get_object_or_404(Files, pk=pk)
    if file.user != request.user:
        return HttpResponse(status=401)
    log.debug(file)
    file.password = request.POST.get("password")
    file.save()
    return HttpResponse(status=200)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def set_expr_file_ajax(request, pk):
    """
    View  /ajax/set_expr/file/<int:pk>/
    """
    log.debug("expr_hook_view_a: %s", pk)
    file = get_object_or_404(Files, pk=pk)
    if file.user != request.user:
        return HttpResponse(status=401)
    log.debug(file)
    file.expr = request.POST.get("expr")
    file.save()
    return HttpResponse(status=200)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def toggle_private_file_ajax(request, pk):
    """
    View  /ajax/toggle_private/file/<int:pk>/
    """
    log.debug("toggle_private_hook_view_a: %s", pk)
    file = get_object_or_404(Files, pk=pk)
    if file.user != request.user:
        return HttpResponse(status=401)
    log.debug(file)
    if file.private:
        file.private = False
    else:
        file.private = True
    file.save()
    return HttpResponse(file.private, status=200)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def toggle_private_album_ajax(request, pk):
    """
    View  /ajax/toggle_private/album/<int:pk>/
    """
    log.debug("toggle_private_album_ajax: %s", pk)
    album = get_object_or_404(Albums, pk=pk)
    if album.user != request.user and not request.user.is_superuser:
        return HttpResponse(status=401)
    album.private = not album.private
    album.save()
    return HttpResponse(album.private, status=200)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def delete_short_ajax(request, pk):
    """
    View  /ajax/delete/short/<int:pk>/
    TODO: Implement into /short/ using DELETE method
    """
    log.debug("del_hook_view_a: %s", pk)
    short = get_object_or_404(ShortURLs, pk=pk)
    if short.user != request.user:
        return HttpResponse(status=401)
    log.debug(short)
    short.delete()
    return HttpResponse(status=204)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def delete_hook_ajax(request, pk):
    """
    View  /ajax/delete/hook/<int:pk>/
    """
    log.debug("delete_hook_ajax: %s", pk)
    webhook = get_object_or_404(DiscordWebhooks, pk=pk)
    if webhook.owner != request.user:
        return HttpResponse(status=404)
    log.debug(webhook)
    webhook.delete()
    return HttpResponse(status=204)


@require_http_methods(["POST"])
def check_password_file_ajax(request, pk):
    """
    View  /ajax/check_password/file/<int:pk>/
    """
    log.debug("check_password_file_ajax: %s", pk)
    file = get_object_or_404(Files, pk=pk)
    if file.password != request.POST.get("password"):
        return HttpResponse(status=401)
    return HttpResponse(status=200)


@require_http_methods(["POST"])
def check_password_album_ajax(request, pk):
    """
    View  /ajax/check_password/album/<int:pk>/
    """
    log.info("check_password_album_ajax: %s", pk)
    file = get_object_or_404(Albums, pk=pk)
    if file.password != request.POST.get("password"):
        return HttpResponse(status=401)
    return HttpResponse(status=200)


@no_append_slash
@require_http_methods(["GET", "HEAD"])
@auth_from_token(no_fail=True)
def raw_redirect_view(request, filename):
    """
    View /raw/<path:filename>
    """
    # TODO: Fully Outline/Document what this does
    log.debug("url_route_raw: %s", filename)
    file = get_object_or_404(Files, name=filename)
    ctx = {"file": file}
    response = HttpResponse(status=302)
    if lock := handle_lock(request, ctx):
        return lock
    if request.GET.get("thumb", False):
        # use site settings context processor for caching
        site_settings = site_settings_processor(None)["site_settings"]
        if use_s3():
            response["Location"] = file.get_gallery_url()
        else:
            response["Location"] = site_settings["site_url"] + file.get_gallery_url()
        return response
    session_view = request.session.get(f"view_{file.name}", True)
    url = file.get_url(session_view, request.GET.get("download", False))
    if session_view:
        request.session[f"view_{file.name}"] = False
    response["Location"] = url
    return response


def _read_file_text(file, max_bytes=None, errors="strict"):
    if use_s3():
        raw = file.file.read(max_bytes) if max_bytes else file.file.read()
        return raw.decode("utf-8", errors=errors)
    with open(file.file.path, "r", errors=errors) as f:
        return f.read(max_bytes) if max_bytes else f.read()


def _build_code_snippet(file):
    try:
        raw = _read_file_text(file, max_bytes=512, errors="replace")
        snippet = raw.strip()
        triple_tick_pos = snippet.find("```")
        if triple_tick_pos != -1:
            snippet = snippet[:triple_tick_pos].rstrip()
        snippet = snippet[:220]
        if not snippet:
            return None
        lang = MIME_TO_DISCORD_LANG.get(file.mime, "")
        upload_date = file.date.strftime("%-d %b %Y at %-I:%M %p")
        footer = f"\n— {file.user.get_name()} | {upload_date}"
        return f"```{lang}\n{snippet}\n```{footer}"
    except Exception:
        log.exception("Failed to read code snippet for unfurl: %s", file.name)
        return None


@require_http_methods(["GET"])
def url_route_view(request, filename):
    """
    View  /u/<path:filename>
    """
    # TODO: Fix Type Hinting on file.exif ?
    site_url = site_settings_processor(request)["site_settings"]["site_url"]
    is_panel = bool(request.GET.get("panel"))
    log.debug("url_route_view: %s", filename)
    file = get_object_or_404(Files, name=filename)
    log.debug("file.mime: %s", file.mime)
    session_view = request.session.get(f"view_{file.name}", True)
    log.debug(f"User {request.user} has not viewed file {file.name}: {session_view}")
    ctx = {
        "file": file,
        "render": file.mime.split("/", 1)[0],
        "static_url": file.get_url(view=session_view),
        "static_meta_url": file.get_meta_static_url(),
        "file_avatar_url": file.user.get_avatar_url(),
        "full_context": request.user.is_authenticated and request.user == file.user,
        "native_app_arg": (
            f"djangofiles://preview/?url={site_url}"
            f"&file_name={quote(file.name)}&file_id={file.id}"
            f"&file_password={quote(file.password)}"
        ),
    }
    if session_view:
        request.session[f"view_{file.name}"] = False
    if lock := handle_lock(request, ctx=ctx):
        return lock
    gps_info = file.exif.get("GPSInfo", {}) if isinstance(file.exif, dict) else {}
    gps_lat, gps_lon = extract_gps_decimal(gps_info)
    ctx["gps_lat"] = gps_lat
    ctx["gps_lon"] = gps_lon
    log.debug("ctx: %s", ctx)
    embed_template = "embed/preview_panel.html" if is_panel else "embed/preview.html"
    if file.mime.startswith("image"):
        log.debug("IMAGE")
        ctx = {**ctx, **handle_image_meta(file.exif)}
        return render(request, embed_template, context=ctx)
    elif file.mime == "text/markdown":
        log.debug("MARKDOWN")
        md_text = _read_file_text(file)
        ctx["markdown"] = markdown.markdown(md_text, extensions=["extra", "toc"])
        if is_panel:
            ctx["render"] = "markdown"
            return render(request, embed_template, context=ctx)
        return render(request, "embed/markdown.html", context=ctx)
    elif file.mime.startswith("text/") or file.mime in CODE_MIMES:
        log.debug("CODE")
        ctx["render"] = "code"
        if snippet := _build_code_snippet(file):
            ctx["code_snippet"] = snippet
        return render(request, embed_template, context=ctx)
    else:
        log.debug("UNKNOWN")
        return render(request, embed_template, context=ctx)


@require_http_methods(["GET"])
def proxy_route_view(request, filename):
    """
    View  /r/<path:filename>
    This is presently only used in test to serve static files without nginx.
    """
    log.info(f"proxying file {filename}")
    raw_fetch = None
    if "thumbs" in filename:
        # thumbs does not have a file object so we use raw fetch to grab
        raw_fetch = filename
        filename = filename.replace("thumbs/", "")
    file = get_object_or_404(Files, name=filename)
    session_view = request.session.get(f"view_{file.name}", True)
    log.debug(f"User {request.user} has not viewed file {file.name}: {session_view}")
    ctx = {"file": file}
    if session_view:
        request.session[f"view_{file.name}"] = False
    if lock := handle_lock(request, ctx=ctx):
        return lock
    if raw_fetch:
        return HttpResponse(fetch_raw_file(raw_fetch), content_type=file.mime)
    return HttpResponse(fetch_file(file), content_type=file.mime)


def handle_lock(request, ctx):
    """Returns a not allowed if private or file pw page if password set."""
    obj = ctx.get("file") or ctx.get("album")
    if obj.private and (request.user != obj.user) and (obj.password is None or obj.password == ""):  # nosec
        return render(request, _404_TEMPLATE, context=ctx, status=404)
    if obj.password and (request.user != obj.user):
        if (supplied_password := (request.GET.get("password"))) != obj.password:
            if supplied_password is not None:
                messages.warning(request, "Invalid Password!")
            return render(request, "embed/password.html", context=ctx, status=403)


def extract_gps_decimal(gps_info: dict):
    """Convert GPS IFD dict (string or int keys) to decimal degrees (lat, lon)."""
    if not isinstance(gps_info, dict):
        return None, None
    try:
        lat_dms = gps_info.get("2") or gps_info.get(2)
        lon_dms = gps_info.get("4") or gps_info.get(4)
        lat_ref = gps_info.get("1") or gps_info.get(1, "N")
        lon_ref = gps_info.get("3") or gps_info.get(3, "E")
        if not lat_dms or not lon_dms or len(lat_dms) < 3 or len(lon_dms) < 3:
            return None, None
        lat = lat_dms[0] + lat_dms[1] / 60 + lat_dms[2] / 3600
        lon = lon_dms[0] + lon_dms[1] / 60 + lon_dms[2] / 3600
        if str(lat_ref).upper() == "S":
            lat = -lat
        if str(lon_ref).upper() == "W":
            lon = -lon
        return round(lat, 6), round(lon, 6)
    except Exception:
        return None, None


def handle_image_meta(exif: dict) -> dict:
    """Parses XMP from exif and handles exif formatting for clients."""
    if not isinstance(exif, dict):
        return {}
    resp = {}
    ptr = exif
    try:
        for key in ["xmpmeta", "RDF", "Description", "subject", "Bag", "li"]:
            if isinstance(ptr, dict):
                ptr = ptr[key]
            elif isinstance(ptr, list):
                ptr = {k: v for d in ptr for k, v in d.items()}[key]
    except KeyError, IndexError:
        log.debug("No image tags or failed to parse image tags.")
        ptr = []
    resp["tags"] = ptr
    resp["software"] = exif.get("Software")
    if exposure_time := exif.get("ExposureTime"):
        exif["ExposureTime"] = str(Fraction(exposure_time).limit_denominator(5000))
    if lens_model := exif.get("LensModel"):
        # handle cases where lensmodel is relevant but some values are redundant
        lm_f_stripped = lens_model.replace(f"f/{exif.get('FNumber', '')}", "")
        lm_model_stripped = lm_f_stripped.replace(f"{exif.get('Model')}", "")
        exif["LensModel"] = lm_model_stripped
    resp["exif"] = exif
    return resp
