import httpx
import io
import json
import logging
import os
import validators
from django.core.files import File
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie
from pytimeparse2 import parse

from home.models import Files
from home.tasks import process_file_upload
from oauth.models import CustomUser

log = logging.getLogger('app')


@require_http_methods(['OPTIONS', 'GET'])
@csrf_exempt
def api_view(request):
    """
    View  /api/
    """
    log.debug('%s - api_view: is_secure: %s', request.method, request.is_secure())
    return JsonResponse({'status': 'online'})


@require_http_methods(['OPTIONS', 'GET', 'POST'])
@cache_page(None, key_prefix="users")
@vary_on_cookie
@csrf_exempt
def users_view(request):
    """
    View  /api/users/
    """
    # TODO: Add signals to CustomUser model to flush cache
    log.debug('NOT CACHED')
    return JsonResponse({'error': 'Not Implemented'}, safe=False, status=400)


@require_http_methods(['OPTIONS', 'GET'])
@cache_page(None, key_prefix="files")
@vary_on_cookie
@csrf_exempt
def recent_view(request):
    """
    View  /api/recent/
    """
    count = 10
    log.debug('%s - recent_view: is_secure: %s', request.method, request.is_secure())
    user = get_auth_user(request)
    log.debug('user: %s', user)
    if not user:
        return JsonResponse({'error': 'Invalid Authorization'}, status=401)
    files = Files.objects.filter(user=user).order_by('-id')[:count]
    data = [file.preview_url() for file in files]
    log.debug('data: %s', data)
    return JsonResponse(data, safe=False)


@require_http_methods(['OPTIONS', 'POST'])
@csrf_exempt
def remote_view(request):
    """
    View  /api/remote/
    """
    log.debug('%s - remote_view: is_secure: %s', request.method, request.is_secure())
    user = get_auth_user(request)
    if not user:
        return JsonResponse({'error': 'Invalid Authorization'}, status=401)

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
        user=user,
        expr=parse_expire(request, user),
    )
    process_file_upload.delay(file.pk)
    log.debug(file)
    log.debug(file.preview_url())
    response = {'url': f'{file.preview_url()}'}
    return JsonResponse(response)


def get_auth_user(request):
    if request.user.is_authenticated:
        return request.user
    authorization = request.headers.get('Authorization') or request.headers.get('Token')
    if not authorization:
        return
    user = CustomUser.objects.filter(authorization=authorization)
    if user:
        return user[0]


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
