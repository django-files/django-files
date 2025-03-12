import io
import json
import logging
import os
import random
from functools import wraps
from typing import Any, BinaryIO, Callable, Optional, Union
from urllib.parse import urlparse

import httpx
import validators
from api.utils import extract_albums, extract_files
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.core.paginator import Paginator
from django.forms.models import model_to_dict
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.cache import cache_control, cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie, vary_on_headers
from home.models import Albums, Files, FileStats, ShortURLs
from home.tasks import new_album_websocket
from home.util.file import process_file
from home.util.misc import anytobool, human_read_to_byte
from home.util.quota import process_storage_quotas
from home.util.rand import rand_string
from oauth.models import CustomUser, UserInvites
from pytimeparse2 import parse
from settings.context_processors import site_settings_processor
from settings.models import SiteSettings


log = logging.getLogger("app")
cache_seconds = 60 * 60 * 4


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


@require_http_methods(["OPTIONS", "POST", "GET"])
@auth_from_token
def album_view(request):
    """
    View  /api/album
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
        else:
            album = get_object_or_404(Albums, id=request.GET.get("id"))
            return JsonResponse(album)
    except Exception as error:
        log.error(error)
        return JsonResponse({"error": f"{error}"}, status=400)


@csrf_exempt
@require_http_methods(["GET"])
@auth_from_token(no_fail=True)
def random_album(request, user_album: str, idname: str = None):
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
    data = serializers.serialize("json", stats)
    return JsonResponse(json.loads(data), safe=False)


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
    amount = int(request.GET.get("amount", 10))
    log.debug("amount: %s", amount)
    files = Files.objects.filter(user=request.user).order_by("-id")[:amount]
    log.debug("files: %s", files)
    log.debug(files)
    response = extract_files(files)
    log.debug("response: %s", response)
    return JsonResponse(response, safe=False, status=200)


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
    if request.user.is_superuser:
        user = request.GET.get("user") or request.user.id
    else:
        user = request.user.id
    log.debug("user: %s", user)
    if album := request.GET.get("album"):
        q = Files.objects.filtered_request(request, albums__id=album)
    else:
        if user == "0":
            q = Files.objects.filtered_request(request)
        else:
            q = Files.objects.filtered_request(request, user_id=int(user))
    paginator = Paginator(q, count)
    page_obj = paginator.get_page(page)
    files = extract_files(page_obj.object_list)
    log.debug("files: %s", files)
    _next = page_obj.next_page_number() if page_obj.has_next() else None
    response = {
        "files": files,
        "next": _next,
        "count": count,
    }
    return JsonResponse(response, safe=False, status=200)


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
    log.debug("file_view: " + request.method + ": " + file.name)
    try:
        if request.method == "DELETE":
            file.delete()
            return HttpResponse(status=204)
        elif request.method == "POST":
            log.debug(request.POST)
            data = get_json_body(request)
            log.debug("data: %s", data)
            if not data:
                return JsonResponse({"error": "Error Parsing JSON Body"}, status=400)
            if "expr" in data and not parse(data["expr"]):
                data["expr"] = ""
            # TODO: We should probably not use .update here and convert to a function, see below TODO
            Files.objects.filter(id=file.id).update(**data)
            file = Files.objects.get(id=file.id)
            response = model_to_dict(file, exclude=["file", "thumb", "albums"])
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


def get_json_body(request):
    try:
        return json.loads(request.body.decode())
    except Exception as error:
        log.debug(error)
        return {}


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
        return JsonResponse({"error": "Error Parsing JSON Body"}, status=400)

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


@require_http_methods(["POST", "GET"])
def token_view(request):
    """
    View  /api/token
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
    returns list of configured methods of oauth.
    """
    site_settings = SiteSettings.objects.settings()
    methods = []
    if site_settings.local_auth:
        methods.append({"name": "local", "url": reverse("oauth:login")})
    if site_settings.discord_client_id:
        methods.append({"name": "discord", "url": reverse("oauth:discord")})
    if site_settings.github_client_id:
        methods.append({"name": "github", "url": reverse("oauth:github")})
    if site_settings.google_client_id:
        methods.append({"name": "google", "url": reverse("oauth:google")})
    return JsonResponse({"auth_methods": methods})