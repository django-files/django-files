import httpx
import io
import json
import logging
import os
import validators
import functools
from django.core.files.storage import default_storage
from django.core import serializers
from django.http import JsonResponse
from django.views.decorators.cache import cache_page, cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie, vary_on_headers

from home.models import Files, FileStats
from home.tasks import process_file_upload
from home.util.expire import parse_expire
from oauth.models import CustomUser

log = logging.getLogger('app')
cache_seconds = 60*60*4


def auth_from_token(view):
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        # TODO: Only Allow Token Auth, or else cache will prevent user switching
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


@require_http_methods(['OPTIONS', 'GET'])
@auth_from_token
@csrf_exempt
def api_view(request):
    """
    View  /api/
    """
    log.debug('%s - api_view: is_secure: %s', request.method, request.is_secure())
    return JsonResponse({'status': 'online', 'user': request.user.id})


@require_http_methods(['OPTIONS', 'GET'])
@auth_from_token
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix="stats")
@vary_on_headers('Authorization')
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


@require_http_methods(['OPTIONS', 'GET'])
@auth_from_token
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix="files")
@vary_on_headers('Authorization')
@vary_on_cookie
@csrf_exempt
def recent_view(request):
    """
    View  /api/recent/
    """
    log.debug('request.user: %s', request.user)
    log.debug('%s - recent_view: is_secure: %s', request.method, request.is_secure())
    amount = int(request.GET.get('amount', 10))
    log.debug('amount: %s', amount)
    files = Files.objects.filter(user=request.user).order_by('-id')[:amount]
    log.debug(files)
    data = [file.preview_url() for file in files]
    log.debug('data: %s', data)
    return JsonResponse(data, safe=False, status=200)


@csrf_exempt
@require_http_methods(['OPTIONS', 'POST'])
@auth_from_token
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

    # f = File(io.BytesIO(r.content), name=os.path.basename(url))
    path = default_storage.save(os.path.basename(url), io.BytesIO(r.content))
    file_pk = process_file_upload({
        'file_name': path,
        'post': request.POST,
        'user_id': request.user.id,
        'expire': parse_expire(request),
    })
    uploaded_file = Files.objects.get(pk=file_pk)
    # file = Files.objects.create(
    #     file=f,
    #     user=request.user,
    #     expr=parse_expire(request, request.user),
    # )
    # process_file_upload.delay(file.pk)
    # log.debug(file)
    log.debug(uploaded_file.preview_url())
    response = {'url': f'{uploaded_file.preview_url()}'}
    return JsonResponse(response)


# def parse_expire(request, user) -> str:
#     # Get Expiration from POST or Default
#     expr = ''
#     if request.POST.get('Expires-At') is not None:
#         expr = request.POST['Expires-At'].strip()
#     elif request.POST.get('ExpiresAt') is not None:
#         expr = request.POST['ExpiresAt'].strip()
#     elif request.headers.get('Expires-At') is not None:
#         expr = request.headers['Expires-At'].strip()
#     elif request.headers.get('ExpiresAt') is not None:
#         expr = request.headers['ExpiresAt'].strip()
#     if expr.lower() in ['0', 'never', 'none', 'null']:
#         return ''
#     if parse(expr) is not None:
#         return expr
#     return user.default_expire or ''
