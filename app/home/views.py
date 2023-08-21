import httpx
import json
import logging
import markdown
import validators
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, reverse, get_object_or_404
from django.core.files.storage import default_storage
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_page, cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie
from fractions import Fraction
from home.util.expire import parse_expire
from home.util.s3 import use_s3

from home.forms import SettingsForm
from home.models import Files, FileStats, SiteSettings, ShortURLs, Webhooks
from home.tasks import clear_shorts_cache, process_file_upload, process_stats
from oauth.models import CustomUser, rand_string

log = logging.getLogger('app')
cache_seconds = 60*60*4


@cache_control(no_cache=True)
@login_required
@cache_page(cache_seconds, key_prefix="files.stats.shorts")
@vary_on_cookie
def home_view(request):
    """
    View  /
    """
    log.debug('%s - home_view: is_secure: %s', request.method, request.is_secure())
    files = Files.objects.get_request(request)
    stats = FileStats.objects.get_request(request)
    shorts = ShortURLs.objects.get_request(request)
    context = {'files': files, 'stats': stats, 'shorts': shorts}
    return render(request, 'home.html', context)


@cache_control(no_cache=True)
@login_required
@cache_page(cache_seconds, key_prefix="stats.shorts")
@vary_on_cookie
def stats_view(request):
    """
    View  /stats/
    """
    log.debug('%s - home_view: is_secure: %s', request.method, request.is_secure())
    shorts = ShortURLs.objects.get_request(request)
    stats = FileStats.objects.get_request(request)
    log.debug('stats: %s', stats)
    days, files, size = [], [], []
    for stat in reversed(stats):
        days.append(f'{stat.created_at.month}/{stat.created_at.day}')
        files.append(stat.stats['count'])
        size.append(stat.stats['size'])
    context = {'stats': stats, 'days': days, 'files': files, 'size': size, 'shorts': shorts}
    log.debug('context: %s', context)
    return render(request, 'stats.html', context=context)


@cache_control(no_cache=True)
@login_required
@cache_page(cache_seconds, key_prefix="files")
@vary_on_cookie
def files_view(request):
    """
    View  /files/
    """
    log.debug('%s - files_view: is_secure: %s', request.method, request.is_secure())
    files = Files.objects.get_request(request)
    context = {'files': files}
    return render(request, 'files.html', context)


@cache_control(no_cache=True)
@login_required
@cache_page(cache_seconds, key_prefix="files")
@vary_on_cookie
def gallery_view(request):
    """
    View  /gallery/
    """
    log.debug('%s - gallery_view: is_secure: %s', request.method, request.is_secure())
    context = {'files': Files.objects.get_request(request)}
    return render(request, 'gallery.html', context)


@cache_control(no_cache=True)
@login_required
@cache_page(cache_seconds, key_prefix="shorts")
@vary_on_cookie
def shorts_view(request):
    """
    View  /shorts/
    """
    log.debug('%s - shorts_view: is_secure: %s', request.method, request.is_secure())
    shorts = ShortURLs.objects.get_request(request)
    context = {'shorts': shorts}
    return render(request, 'shorts.html', context)


@cache_control(no_cache=True)
@login_required
@cache_page(cache_seconds, key_prefix="settings.webhooks")
@vary_on_cookie
def settings_view(request):
    """
    View  /settings/
    """
    log.debug('settings_view: %s', request.method)
    # site_settings = SiteSettings.objects.get(pk=1)
    site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
    if request.method in ['GET', 'HEAD']:
        webhooks = Webhooks.objects.get_request(request)
        context = {'webhooks': webhooks, 'site_settings': site_settings}
        log.debug('context: %s', context)
        return render(request, 'settings.html', context)

    log.debug(request.POST)
    form = SettingsForm(request.POST)
    if not form.is_valid():
        return JsonResponse(form.errors, status=400)
    data = {'reload': False}
    log.debug(form.cleaned_data)
    site_settings.site_url = form.cleaned_data['site_url']
    site_settings.save()
    request.user.default_expire = form.cleaned_data['default_expire']

    if request.user.default_color != form.cleaned_data['default_color']:
        request.user.default_color = form.cleaned_data['default_color']
        # data['reload'] = True

    if request.user.nav_color_1 != form.cleaned_data['nav_color_1']:
        request.user.nav_color_1 = form.cleaned_data['nav_color_1']
        data['reload'] = True

    if request.user.nav_color_2 != form.cleaned_data['nav_color_2']:
        request.user.nav_color_2 = form.cleaned_data['nav_color_2']
        data['reload'] = True

    request.user.remove_exif_geo = form.cleaned_data['remove_exif_geo']
    request.user.remove_exif = form.cleaned_data['remove_exif']
    request.user.show_exif_preview = form.cleaned_data['show_exif_preview']
    request.user.s3_bucket_name = form.cleaned_data.get('s3_bucket_name')

    request.user.save()
    if data['reload']:
        messages.success(request, 'Settings Saved Successfully.')
    return JsonResponse(data, status=200)


@login_required
@csrf_exempt
@cache_page(cache_seconds)
@vary_on_cookie
def uppy_view(request):
    """
    View  /uppy/
    """
    if request.method in ['GET', 'HEAD']:
        return render(request, 'uppy.html')

    log.debug(request.headers)
    log.debug(request.POST)
    log.debug(request.FILES)

    if not (file := request.FILES.get('file')):
        return HttpResponse(status=400)
    path = default_storage.save(file.name, file)
    process_file_upload.delay({
            'file_name': path,
            'post': request.POST,
            'user_id': request.user.id,
            'expire': parse_expire(request),
        })
    return HttpResponse()


@csrf_exempt
@require_http_methods(['POST'])
def upload_view(request):
    """
    View  /upload/ and /api/upload
    """
    log.debug(request.headers)
    log.debug(request.POST)
    log.debug(request.FILES)
    try:
        user = get_auth_user(request)
        if not user:
            return JsonResponse({'error': 'Invalid Authorization'}, status=401)
        if not (file := request.FILES.get('file')):
            return JsonResponse({'error': 'File Not Created'}, status=400)
        path = default_storage.save(file.name, file)
        file_pk = process_file_upload({
            'file_name': path,
            'post': request.POST,
            'user_id': user.id,
            'expire': parse_expire(request),
        })
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
        user = get_auth_user(request)
        if not user:
            return JsonResponse({'error': 'Invalid Authorization'}, status=401)

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
            user=user,
        )
        site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
        full_url = site_settings.site_url + reverse('home:short', kwargs={'short': url.short})
        return JsonResponse({'url': full_url}, safe=False)

    except Exception as error:
        log.exception(error)
        return JsonResponse({'error': str(error)}, status=500)


def shorten_short_view(request, short):
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


def gen_short(vanity, length=4):
    if vanity:
        # TODO: check that vanity does not exist
        return vanity
    rand = rand_string(length=length)
    while ShortURLs.objects.filter(short=rand):
        rand = rand_string(length=length)
        continue
    return rand


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def update_stats_ajax(request):
    """
    View  /ajax/update/stats/
    """
    log.debug('update_stats_ajax')
    process_stats.delay()
    messages.success(request, 'Stats Processing Queued.')
    return HttpResponse(status=204)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def delete_file_ajax(request, pk):
    """
    View  /ajax/delete/file/<int:pk>/
    TODO: Implement into /files/ using DELETE method
    """
    log.debug('del_hook_view_a: %s', pk)
    file = Files.objects.get(pk=pk)
    if file.user != request.user:
        return HttpResponse(status=401)
    log.debug(file)
    file.delete()
    return HttpResponse(status=204)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def delete_hook_ajax(request, pk):
    """
    View  /ajax/delete/hook/<int:pk>/
    """
    log.debug('delete_hook_ajax: %s', pk)
    webhook = Webhooks.objects.get(pk=pk)
    if webhook.owner != request.user:
        return HttpResponse(status=404)
    log.debug(webhook)
    webhook.delete()
    return HttpResponse(status=204)


@login_required
@require_http_methods(['GET'])
def gen_sharex(request):
    """
    View  /gen/sharex/
    """
    log.debug('gen_sharex')
    data = {
        'Version': '15.0.0',
        'Name': f'Django Files - {request.get_host()} - File',
        'DestinationType': 'ImageUploader, FileUploader, TextUploader',
        'RequestMethod': 'POST',
        'RequestURL': request.build_absolute_uri(reverse('home:api-upload')),
        'Headers': {
            'Authorization': request.user.authorization,
            'Expires-At': request.user.default_expire,
        },
        'Body': 'MultipartFormData',
        'URL': '{json:url}',
        'FileFormName': 'file',
        'ErrorMessage': '{json:error}'
    }
    # Create the HttpResponse object with the appropriate headers.
    filename = f'{request.get_host()} - Files.sxcu'
    response = JsonResponse(data, json_dumps_params={'indent': 4})
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_http_methods(['GET'])
def gen_sharex_url(request):
    """
    View  /gen/sharex-url/
    """
    log.debug('gen_sharex_url')
    data = {
        'Version': '15.0.0',
        'Name': f'Django Files - {request.get_host()} - URL',
        'DestinationType': 'URLShortener, URLSharingService',
        'RequestMethod': 'POST',
        'RequestURL': request.build_absolute_uri(reverse('home:api-shorten')),
        'Headers': {
            'Authorization': request.user.authorization,
        },
        'Body': 'JSON',
        'URL': '{json:url}',
        'Data': '{"url":"{input}"}',
        'ErrorMessage': '{json:error}',
    }
    # Create the HttpResponse object with the appropriate headers.
    filename = f'{request.get_host()} - URL.sxcu'
    response = JsonResponse(data, json_dumps_params={'indent': 4})
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_http_methods(['GET'])
def gen_flameshot(request):
    """
    View  /gen/flameshot/
    """
    # site_settings = SiteSettings.objects.get(pk=1)
    # context = {'site_url': settings.SITE_URL, 'token': request.user.authorization}
    context = {'site_url': request.build_absolute_uri(reverse('home:upload')), 'token': request.user.authorization}
    log.debug('context: %s', context)
    message = render_to_string('scripts/flameshot.sh', context)
    # log.debug('message: %s', message)
    response = HttpResponse(message)
    response['Content-Disposition'] = 'attachment; filename="flameshot.sh"'
    return response


@require_http_methods(['GET'])
def raw_redirect_view(request, filename):
    """
    View /raw/<path:filename>
    """
    view = False
    log.debug('url_route_raw: %s', filename)
    file = get_object_or_404(Files, name=filename)
    response = HttpResponse(status=302)
    if use_s3():
        view = True
    response['Location'] = file.get_url(view=view, download=request.GET.get('download', False))
    return response


@require_http_methods(['GET'])
def url_route_view(request, filename):
    """
    View  /u/<path:filename>
    """
    # TODO: Fix Type Hinting on file.exif ?
    code_mimes = [
        'application/json',
        'application/x-perl',
        'application/x-sh',
    ]
    log.debug('url_route_view: %s', filename)
    file = get_object_or_404(Files, name=filename)
    log.debug('file.mime: %s', file.mime)
    ctx = {'file': file, 'render': file.mime.split('/', 1)[0], "static_url": file.get_url(view=use_s3())}
    log.debug('ctx: %s', ctx)
    if file.mime.startswith('image'):
        log.debug('IMAGE')
        if file.exif:
            if exposure_time := file.exif.get('ExposureTime'):
                file.exif['ExposureTime'] = str(Fraction(exposure_time).limit_denominator(5000))
            if lens_model := file.exif.get('LensModel'):
                # handle cases where lensmodel is relevant but some values redunant
                lm_f_stripped = lens_model.replace(f"f/{file.exif.get('FNumber', '')}", "")
                lm_model_stripped = lm_f_stripped.replace(f"{file.exif.get('Model')}", "")
                file.exif['LensModel'] = lm_model_stripped
        return render(request, 'embed/preview.html', context=ctx)
    elif file.mime == 'text/markdown':
        log.debug('MARKDOWN')
        with open(file.file.path, 'r') as f:
            md_text = f.read()
        ctx['markdown'] = markdown.markdown(md_text, extensions=['extra', 'toc'])
        file.view += 1
        file.save()
        return render(request, 'embed/markdown.html', context=ctx)
    elif file.mime.startswith('text/') or file.mime in code_mimes:
        log.debug('CODE')
        lang_map = {
            "x-python": "python",
            "plain": "plaintext"
        }
        ctx['render'] = 'code'
        ctx['highlight_language'] = f"language-{lang_map.get(file.mime.replace('text/',''), 'plaintext')}"
        return render(request, 'embed/preview.html', context=ctx)
    else:
        log.debug('UNKNOWN')
        return render(request, 'embed/preview.html', context=ctx)


def google_verify(request: HttpRequest) -> bool:
    if 'g_verified' in request.session and request.session['g_verified']:
        return True
    try:
        url = 'https://www.google.com/recaptcha/api/siteverify'
        data = {
            'secret': settings.GOOGLE_SITE_SECRET,
            'response': request.POST['g-recaptcha-response']
        }
        r = httpx.post(url, data=data, timeout=10)
        if r.is_success:
            if r.json()['success']:
                request.session['g_verified'] = True
                return True
        return False
    except Exception as error:
        log.exception(error)
        return False


def get_auth_user(request):
    # TODO: Use function decorator from api/views.py
    if request.user.is_authenticated:
        return request.user
    authorization = request.headers.get('Authorization') or request.headers.get('Token')
    if authorization:
        user = CustomUser.objects.filter(authorization=authorization)
        if user:
            return user[0]
