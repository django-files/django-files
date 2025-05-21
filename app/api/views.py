import io
import json
import logging
import os
import random
from functools import wraps
from typing import Any, BinaryIO, Callable, List, Optional, Union
from urllib.parse import urlparse

import httpx
import validators
from api.utils import extract_albums, extract_files
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core import serializers
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.forms.models import model_to_dict
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.cache import cache_control, cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie, vary_on_headers
from home.models import Albums, Files, FileStats, ShortURLs
from home.tasks import clear_files_cache, new_album_websocket
from home.util.file import process_file
from home.util.misc import anytobool, human_read_to_byte
from home.util.quota import process_storage_quotas
from home.util.rand import rand_string
from home.util.storage import file_rename
from oauth.models import CustomUser, UserInvites
from oauth.providers.discord import DiscordOauth
from oauth.providers.github import GithubOauth
from oauth.providers.google import GoogleOauth
from packaging import version
from packaging.version import InvalidVersion
from pytimeparse2 import parse
from settings.context_processors import site_settings_processor
from settings.models import SiteSettings


log = logging.getLogger("app")
cache_seconds = 60 * 60 * 4

json_error_message = "Error Parsing JSON Body"


def auth_from_token(view=None, no_fail=False):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if getattr(request, "user", None) and request.user.is_authenticated:
            return view(request, *args, **kwargs)
        authorization = (
            request.headers.get("Authorization") or request.headers.get("Token") or request.GET.get("token")
        )
        # log.debug('authorization: %s', authorization)
        if authorization:
            user = CustomUser.objects.filter(authorization=authorization)
            if user:
                request.user = user[0]
                return view(request, *args, **kwargs)
        if not no_fail:
            return JsonResponse({"error": "Invalid Authorization"}, status=401)
        return view(request, *args, **kwargs)

    if view:
        return wrapper
    else:
        return lambda func: auth_from_token(func, no_fail)


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
@auth_from_token
def upload_view(request):
    """
    View  /upload/ and /api/upload
    """
    log.debug("upload_view")
    # log.debug(request.headers)
    post = request.POST.dict().copy()
    log.debug(post)
    log.debug(request.FILES)
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
        return process_file_upload(f, request.user.id, **extra_args)
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
        if not validators.url(url):
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


@csrf_exempt
@require_http_methods(["OPTIONS", "POST", "GET", "DELETE"])
@auth_from_token
def album_view(request, id: int = None):
    """
    View  /api/album/
    """
    try:
        if request.method == "POST":
            log.debug("request.headers: %s", request.headers)
            data = get_json_body(request)
            log.debug("data: %s", data)
            album = Albums.objects.create(
                user=request.user,
                name=data_or_header(request, data, "name"),
                maxv=data_or_header(request, data, "max-views", 0, cast=int),
                info=data_or_header(request, data, "description"),
                password=data_or_header(request, data, "password"),
                private=data_or_header(request, data, "private", False, cast=bool),
                expr=data_or_header(request, data, "expire"),
            )
            site_settings = SiteSettings.objects.settings()
            full_url = site_settings.site_url + reverse("home:files") + f"?album={album.id}"
            # clear_albums_cache.delay()  # this is redundant and handled by a signal
            new_album_websocket.apply_async(args=[extract_albums([album])[0]])  # no time to de-tangle this line
            return JsonResponse({"url": full_url}, safe=False)
        elif request.method == "DELETE":
            album = get_object_or_404(Albums, id=id)
            album.delete()
            return HttpResponse(status=204)
        else:
            album = get_object_or_404(Albums, id=id if id else request.GET.get("id"))
            return JsonResponse(album)
    except Exception as error:
        log.error(error)
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


@csrf_exempt
@require_http_methods(["OPTIONS", "GET"])
@auth_from_token
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix="stats")
@vary_on_headers("Authorization")
@vary_on_cookie
def stats_view(request):
    """
    View  /api/stats/
    """
    log.debug("%s - stats_view: is_secure: %s", request.method, request.is_secure())
    amount = int(request.GET.get("amount", 10))
    log.debug("amount: %s", amount)
    # TODO: Format Stats
    stats = FileStats.objects.filter(user=request.user)[:amount]
    # current = stats.first()
    # log.debug("current.stats: %s", current.stats)
    # data = {
    #     "current": current.stats,
    #     "stats": json.loads(serializers.serialize("json", stats)),
    # }
    # return JsonResponse(data)
    data = serializers.serialize("json", stats)
    return JsonResponse(json.loads(data), safe=False)


@csrf_exempt
@require_http_methods(["OPTIONS", "GET"])
@auth_from_token
@cache_control(no_cache=True)
@vary_on_headers("Authorization")
@vary_on_cookie
def stats_current_view(request):
    """
    View  /api/stats/current/
    """
    log.debug("%s - stats_view: is_secure: %s", request.method, request.is_secure())
    stats = FileStats.objects.filter(user=request.user).first()
    log.debug("stats: %s", stats)
    if stats is not None:
        data = model_to_dict(stats)
        log.debug("data: %s", data)
        if stats := data.get("stats"):
            if "types" in stats:
                del stats["types"]
            return JsonResponse(stats)
    return JsonResponse({})


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
        query = Files.objects.filtered_request(request).select_related("user")
        if album := request.GET.get("album"):
            query.filter(albums__id=album)

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


@csrf_exempt
@require_http_methods(["OPTIONS", "GET"])
@auth_from_token()
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix="files")
@vary_on_headers("Authorization")
@vary_on_cookie
def files_view(request, page, count=25):
    """
    View  /api/files/{page}/{count}/
    """
    log.debug("%s - files_page_view: %s", request.method, page)
    if request.user.is_superuser:
        user = request.GET.get("user") or request.user.id
    else:
        user = request.user.id
    log.debug("user: %s", user)
    if album := request.GET.get("album"):
        q = Files.objects.filtered_request(request, albums__id=album).select_related("user")
    else:
        if user == "0":
            q = Files.objects.filtered_request(request).select_related("user")
        else:
            q = Files.objects.filtered_request(request, user_id=int(user)).select_related("user")
    paginator = Paginator(q, count)
    page_obj = paginator.get_page(page)
    files = extract_files(page_obj.object_list)
    # log.debug("files: %s", files)
    _next = page_obj.next_page_number() if page_obj.has_next() else None
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
        log.error(error)
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
@auth_from_token
def file_view(request, idname):
    """
    View  /api/file/{id or name}
    """
    kwargs = id_or_name(idname)
    log.debug("kwargs: %s", kwargs)
    if not request.user.is_superuser:
        kwargs["user"] = request.user
    file = get_object_or_404(Files, **kwargs)
    log.debug("file_view: %s: %s", request.method, file.name)
    try:
        if request.method == "DELETE":
            file.delete()
            return HttpResponse(status=204)
        elif request.method == "POST":
            log.debug(request.POST)
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
            queryset.update(**data)
            if "name" in data and data["name"] != file.name:
                if Files.objects.filter(name=data["name"]).exists():
                    return JsonResponse({"error": "File name already in use."}, status=400)
                file = file_rename(file, data["name"])
                del data["name"]
            else:
                file = Files.objects.get(id=file.id)
            response = model_to_dict(file, exclude=["file", "thumb", "albums"])
            file.file.name = data["name"]
            # TODO: Determine why we have to manually flush file cache here
            #       The Website seems to flush, but not the api/recent/ endpoint
            #       ANSWER: This is not called on .update(), you must call .save()
            # clear_files_cache.delay()
            # TODO: Calling .save after .update is redundant but fires a .save() method!
            file.save(update_fields=list(data.keys()))
            log.debug("response: %s" % response)
            return JsonResponse(response, status=200)
        elif request.method == "GET":
            response = model_to_dict(file, exclude=["file", "thumb", "albums"])
            response["date"] = file.date  # not sure why this is not getting included
            response["albums"] = [album.id for album in Albums.objects.filter(files__id=file.id)]
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
        q = Albums.objects.filtered_request(request)
    else:
        q = Albums.objects.filtered_request(request, user_id=int(user))
    paginator = Paginator(q, count)
    page_obj = paginator.get_page(page)
    albums = extract_albums(page_obj.object_list)
    log.debug("albums: %s", albums)
    _next = page_obj.next_page_number() if page_obj.has_next() else None
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
    log.debug("request.POST: %s", request.POST)
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
    response = {"url": f'{site_settings["site_url"] + file.preview_uri()}'}
    log.debug("response: %s", response)
    return JsonResponse(response)


@require_http_methods(["POST", "GET"])
def token_view(request):
    """
    View  /api/token/
    GET to fetch token value
    POST to refresh and fetch token value
    """
    if not request.user:
        return HttpResponse(status=401)
    if request.method == "POST":
        user = request.user
        user.authorization = rand_string()
        user.save()
    return HttpResponse(request.user.authorization)


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
    if site_settings.discord_client_id:
        methods.append({"name": "discord", "url": DiscordOauth.get_login_url(site_settings) + state_string})
    if site_settings.github_client_id:
        methods.append({"name": "github", "url": GithubOauth.get_login_url(site_settings) + state_string})
    if site_settings.google_client_id:
        methods.append({"name": "google", "url": GoogleOauth.get_login_url(site_settings) + state_string})
    return JsonResponse({"authMethods": methods, "siteName": site_settings.site_title})


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
        return JsonResponse({"token": request.user.authorization})

    data = get_json_body(request)
    if not data:
        return JsonResponse({"error": json_error_message}, status=400)

    site_settings = SiteSettings.objects.settings()
    if site_settings.get_local_auth():
        user = authenticate(request, username=data.get("username"), password=data.get("password"))
        if user:
            login(request, user)
            return JsonResponse({"token": request.user.authorization})

    return HttpResponse(status=401)


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
    ]
    data = {}
    # TODO: IMPORTANT: Determine why these values are not 1:1 - meta_preview:embed
    difference_mapping = {"embed": "meta_preview"}
    # TODO: This should probably do the same thing in both loops
    for key in allowed:
        if key in headers:
            value = headers[key]
            if key in difference_mapping:
                key = difference_mapping[key]
            data[key.replace("-", "_")] = value
    # data.update(**kwargs)
    for key, value in kwargs.items():
        if key.lower() in allowed:
            data[key] = value
    return data


def process_file_upload(f: BinaryIO, user_id: int, **kwargs):
    log.debug("user_id: %s", user_id)
    log.debug("kwargs: %s", kwargs)
    site_settings = site_settings_processor(None)["site_settings"]
    name = kwargs.pop("name", f.name)
    file = process_file(name, f, user_id, **kwargs)
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
    if data:
        if result := data.get(value):
            return cast(result)
    return cast(request.headers.get(value, default))


def id_or_name(id_name: Union[str, int], name="name") -> dict:
    if id_name.isnumeric():
        return {"id": int(id_name)}
    else:
        return {name: id_name}


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
            shorts = query.filter(id__gt=before)
            return JsonResponse([model_to_dict(short) for short in shorts], safe=False)

        amount = int(request.GET.get("amount", 10))
        log.debug("amount: %s", amount)

        after = int(request.GET.get("after", 0))
        log.debug("after: %s", after)
        if after:
            shorts = query.filter(id__lt=after)[:amount]
            return JsonResponse([model_to_dict(short) for short in shorts], safe=False)

        start = int(request.GET.get("start", 0))
        log.debug("start: %s", start)
        shorts = query[start : start + amount]

        # TODO: Determine why this data only gets modified at this stage
        site_settings = site_settings_processor(None)["site_settings"]
        shorts_data = []
        for short in shorts:
            short_dict = model_to_dict(short)
            short_dict["full_url"] = site_settings["site_url"] + reverse("home:short", kwargs={"short": short.short})
            shorts_data.append(short_dict)
        return JsonResponse(shorts_data, safe=False)

    except ValueError as error:
        log.debug(error)
        return JsonResponse({"error": f"{error}"}, status=400)
