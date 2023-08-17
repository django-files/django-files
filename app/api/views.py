import httpx
import io
import json
import logging
import os
import validators
import functools
from django.core.files import File
from django.core import serializers
from django.http import JsonResponse
from django.views.decorators.cache import cache_page, cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie
from pytimeparse2 import parse

from home.models import Files, FileStats
from home.tasks import process_file_upload
from oauth.models import CustomUser

log = logging.getLogger('app')


def get_auth_user(view):
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view(request, *args, **kwargs)
        authorization = request.headers.get('Authorization') or request.headers.get('Token')
        if authorization:
            user = CustomUser.objects.filter(authorization=authorization)
            if user:
                request.user = user[0]
                return view(request, *args, **kwargs)
        return JsonResponse({'error': 'Invalid Authorization'}, status=401)
    return wrapper


@get_auth_user
@require_http_methods(['OPTIONS', 'GET'])
@csrf_exempt
def api_view(request):
    """
    View  /api/
    """
    log.debug('%s - api_view: is_secure: %s', request.method, request.is_secure())
    return JsonResponse({'status': 'online', 'user': request.user.id})


@get_auth_user
@require_http_methods(['OPTIONS', 'GET'])
@cache_control(no_cache=True)
@cache_page(60*60*4, key_prefix="stats")
@vary_on_cookie
@csrf_exempt
def stats_view(request):
    """
    View  /api/stats/
    """
    log.debug('%s - stats_view: is_secure: %s', request.method, request.is_secure())
    amount = int(request.GET.get('amount', 10))
    log.debug('amount: %s', amount)
    # TODO: Format Stats
    stats = FileStats.objects.filter(user=request.user)[:amount]
    data = serializers.serialize('json', stats)
    return JsonResponse(json.loads(data), safe=False)


@get_auth_user
@require_http_methods(['OPTIONS', 'GET'])
@cache_control(no_cache=True)
@cache_page(60*60*4, key_prefix="files")
@vary_on_cookie
@csrf_exempt
def recent_view(request):
    """
    View  /api/recent/
    """
    log.debug('%s - recent_view: is_secure: %s', request.method, request.is_secure())
    amount = int(request.GET.get('amount', 10))
    log.debug('amount: %s', amount)
    files = Files.objects.filter(user=request.user).order_by('-id')[:amount]
    data = [file.preview_url() for file in files]
    log.debug('data: %s', data)
    return JsonResponse(data, safe=False)


@get_auth_user
@require_http_methods(['OPTIONS', 'POST'])
@csrf_exempt
def remote_view(request):
    """
    View  /api/remote/
    """
    log.debug('%s - remote_view: is_secure: %s', request.method, request.is_secure())
    body = request.body.decode()
    log.debug('body: %s', body)
    try:
        data = json.loads(body)
    except Exception as error:
        log.debug(error)
        return JsonResponse({'error': f'{error}'}, status=400)

    url = data.get('url')
    log.debug('url: %s', url)
    if not validators.url(url):
        return JsonResponse({'error': 'Missing/Invalid URL'}, status=400)

    r = httpx.get(url)
    if not r.is_success:
        return JsonResponse({'error': f'{r.status_code} Fetching {url}'}, status=400)

    f = File(io.BytesIO(r.content), name=os.path.basename(url))
    file = Files.objects.create(
        file=f,
        user=request.user,
        expr=parse_expire(request, request.user),
    )
    process_file_upload.delay(file.pk)
    log.debug(file)
    log.debug(file.preview_url())
    response = {'url': f'{file.preview_url()}'}
    return JsonResponse(response)


# def get_auth_user(request):
#     if request.user.is_authenticated:
#         return request.user
#     authorization = request.headers.get('Authorization') or request.headers.get('Token')
#     if authorization:
#         user = CustomUser.objects.filter(authorization=authorization)
#         if user:
#             return user[0]


def parse_expire(request, user) -> str:
    # Get Expiration from POST or Default
    expr = ''
    if request.POST.get('Expires-At') is not None:
        expr = request.POST['Expires-At'].strip()
    elif request.POST.get('ExpiresAt') is not None:
        expr = request.POST['ExpiresAt'].strip()
    elif request.headers.get('Expires-At') is not None:
        expr = request.headers['Expires-At'].strip()
    elif request.headers.get('ExpiresAt') is not None:
        expr = request.headers['ExpiresAt'].strip()
    if expr.lower() in ['0', 'never', 'none', 'null']:
        return ''
    if parse(expr) is not None:
        return expr
    return user.default_expire or ''
