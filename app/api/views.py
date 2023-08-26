import httpx
import io
import json
import logging
import os
import validators
import functools
from django.core import serializers
from django.http import JsonResponse
from django.shortcuts import reverse
from django.views.decorators.cache import cache_page, cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie, vary_on_headers
from pytimeparse2 import parse
from typing import Optional

from home.models import Files, FileStats, SiteSettings, ShortURLs
from home.util.file import process_file
from oauth.models import CustomUser
from home.util.rand import rand_string

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


@csrf_exempt
@require_http_methods(['OPTIONS', 'GET'])
@auth_from_token
def api_view(request):
    """
    View  /api/
    """
    log.debug('%s - api_view: is_secure: %s', request.method, request.is_secure())
    return JsonResponse({'status': 'online', 'user': request.user.id})


@csrf_exempt
@require_http_methods(['POST'])
@auth_from_token
def upload_view(request):
    """
    View  /upload/ and /api/upload
    """
    log.debug(request.headers)
    log.debug(request.POST)
    log.debug(request.FILES)
    try:
        if not (f := request.FILES.get('file')):
            return JsonResponse({'error': 'No File Found at Key: file'}, status=400)
        kwargs = {'expr': parse_expire(request), 'info': request.POST.get('info')}
        file = process_file(f.name, f, request.user.id, **kwargs)
        data = {
            'files': [file.preview_url()],
            'url': file.preview_url(),
            'raw': file.get_url(),
            'name': file.name,
            'size': file.size,
        }
        return JsonResponse(data)
    except Exception as error:
        log.exception(error)
        return JsonResponse({'error': str(error)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
@auth_from_token
def shorten_view(request):
    """
    View  /shorten/ and /api/shorten
    """
    body = request.body.decode()
    log.debug(body)
    log.debug('-'*40)
    log.debug(request.headers)
    log.debug('-'*40)
    log.debug(request.POST)
    try:
        url = request.headers.get('url')
        vanity = request.headers.get('vanity')
        max_views = request.headers.get('max-views')
        if not url:
            try:
                data = json.loads(body)
                log.debug('data: %s', data)
                url = data.get('url', url)
                vanity = data.get('vanity', vanity)
                max_views = data.get('max-views', max_views)
            except Exception as error:
                log.debug(error)
        if not url:
            return JsonResponse({'error': 'Missing Required Value: url'}, status=400)

        log.debug('url: %s', url)
        if not validators.url(url):
            return JsonResponse({'error': 'Unable to Validate URL'}, status=400)
        if max_views and not str(max_views).isdigit():
            return JsonResponse({'error': 'max-views Must be an Integer'}, status=400)
        if vanity and not validators.slug(vanity):
            return JsonResponse({'error': 'vanity Must be a Slug'}, status=400)
        short = gen_short(vanity)
        log.debug('short: %s', short)
        url = ShortURLs.objects.create(
            url=url,
            short=short,
            max=max_views or 0,
            user=request.user,
        )
        site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
        full_url = site_settings.site_url + reverse('home:short', kwargs={'short': url.short})
        return JsonResponse({'url': full_url}, safe=False)

    except Exception as error:
        log.exception(error)
        return JsonResponse({'error': str(error)}, status=500)


@csrf_exempt
@require_http_methods(['OPTIONS', 'GET'])
@auth_from_token
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix='stats')
@vary_on_headers('Authorization')
@vary_on_cookie
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


@csrf_exempt
@require_http_methods(['OPTIONS', 'GET'])
@auth_from_token
@cache_control(no_cache=True)
@cache_page(cache_seconds, key_prefix='files')
@vary_on_headers('Authorization')
@vary_on_cookie
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

    kwargs = {'expr': parse_expire(request), 'info': request.POST.get('info')}
    file = process_file(os.path.basename(url), io.BytesIO(r.content), request.user.id, **kwargs)
    response = {'url': f'{file.preview_url()}'}
    log.debug('url: %s', url)
    return JsonResponse(response)


def gen_short(vanity: Optional[str] = None, length: int = 4) -> str:
    if vanity:
        if not ShortURLs.objects.filter(short=vanity):
            return vanity
        else:
            raise ValueError(f'Vanity Taken: {vanity}')
    rand = rand_string(length=length)
    while ShortURLs.objects.filter(short=rand):
        rand = rand_string(length=length)
        continue
    return rand


def parse_expire(request) -> str:
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
    return request.user.default_expire or ''
