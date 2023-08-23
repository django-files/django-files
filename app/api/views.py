import httpx
import io
import json
import logging
import os
import validators
import functools
from django.core.files.storage import storages
from django.core import serializers
from django.http import JsonResponse
from django.shortcuts import reverse
from django.views.decorators.cache import cache_page, cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie, vary_on_headers

from home.models import Files, FileStats, SiteSettings, ShortURLs
from home.tasks import process_file_upload
from oauth.models import CustomUser, rand_string

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
        if not (file := request.FILES.get('file')):
            return JsonResponse({'error': 'File Not Created'}, status=400)
        # TODO: Start DEBUGGING HERE
        # https://docs.djangoproject.com/en/4.2/ref/files/storage/#django.core.files.storage.Storage.save
        storage = storages['temp']
        file_name = storage.save(file.name, file)
        file_pk = process_file_upload(file_name, request.user.id)
        uploaded_file = Files.objects.get(pk=file_pk)
        data = {
            'files': [uploaded_file.preview_url()],
            'url': uploaded_file.preview_url(),
            'raw': uploaded_file.get_url(),
            'name': uploaded_file.name,
            'size': uploaded_file.size,
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

    # f = File(io.BytesIO(r.content), name=os.path.basename(url))
    storage = storages['temp']
    file_name = storage.save(os.path.basename(url), io.BytesIO(r.content))
    # path = default_storage.save(os.path.basename(url), io.BytesIO(r.content))
    file_pk = process_file_upload(file_name, request.user.id)
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


def gen_short(vanity, length=4):
    if vanity:
        # TODO: check that vanity does not exist
        return vanity
    rand = rand_string(length=length)
    while ShortURLs.objects.filter(short=rand):
        rand = rand_string(length=length)
        continue
    return rand
