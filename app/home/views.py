# import datetime
from pathlib import Path
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
from django.template.loader import render_to_string
# from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
# from itertools import count
from pygments import highlight
from pygments.lexers import get_lexer_by_name, get_lexer_for_mimetype
from pygments.formatters import HtmlFormatter
from pytimeparse2 import parse
from geopy.geocoders import Nominatim

from oauth.models import CustomUser, rand_string
from home.forms import SettingsForm
from home.models import Files, FileStats, SiteSettings, ShortURLs, Webhooks
from home.tasks import clear_shorts_cache, process_file_upload, process_stats
from fractions import Fraction

log = logging.getLogger('app')


@login_required
def home_view(request):
    """
    View  /
    """
    log.debug('%s - home_view: is_secure: %s', request.method, request.is_secure())
    files = Files.objects.get_request(request)
    stats = FileStats.objects.get_request(request)
    # stats = FileStats.objects.filter(user=request.user)
    shorts = ShortURLs.objects.get_request(request)
    context = {'files': files, 'stats': stats, 'shorts': shorts}
    return render(request, 'home.html', context)


@login_required
def stats_view(request):
    """
    View  /stats/
    """
    log.debug('%s - home_view: is_secure: %s', request.method, request.is_secure())
    # TODO: Add ShortURLs to FileStats data and task
    shorts = ShortURLs.objects.get_request(request)
    # stats = FileStats.objects.filter(user_id=2)
    stats = FileStats.objects.get_request(request)
    log.debug('stats: %s', stats)
    days, files, size = [], [], []
    # {"types": {}, "size": 0, "count": 0, "human_size": "0.0 B"}
    # TODO: Move to Template Tag for Template Fragment Caching
    for stat in reversed(stats):
        days.append(f'{stat.created_at.month}/{stat.created_at.day}')
        files.append(stat.stats['count'])
        size.append(stat.stats['size'])
    context = {'stats': stats, 'days': days, 'files': files, 'size': size, 'shorts': shorts}
    log.debug('context: %s', context)
    return render(request, 'stats.html', context=context)


@login_required
def files_view(request):
    """
    View  /files/
    """
    log.debug('%s - files_view: is_secure: %s', request.method, request.is_secure())
    files = Files.objects.get_request(request)
    # stats = FileStats.objects.get_request(request)
    # shorts = ShortURLs.objects.get_request(request)
    context = {'files': files}
    return render(request, 'files.html', context)


@login_required
def gallery_view(request):
    """
    View  /gallery/
    """
    log.debug('%s - gallery_view: is_secure: %s', request.method, request.is_secure())
    context = {'files': Files.objects.get_request(request)}
    return render(request, 'gallery.html', context)


@login_required
def shorts_view(request):
    """
    View  /shorts/
    """
    log.debug('%s - shorts_view: is_secure: %s', request.method, request.is_secure())
    # files = Files.objects.get_request(request)
    # stats = FileStats.objects.get_request(request)
    shorts = ShortURLs.objects.get_request(request)
    context = {'shorts': shorts}
    return render(request, 'shorts.html', context)


@login_required
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

    request.user.save()
    if data['reload']:
        messages.success(request, 'Settings Saved Successfully.')
    return JsonResponse(data, status=200)


@login_required
@csrf_exempt
def uppy_view(request):
    """
    View  /uppy/
    """
    if request.method in ['GET', 'HEAD']:
        return render(request, 'uppy.html')

    log.debug(request.headers)
    log.debug(request.POST)
    log.debug(request.FILES)
    file = Files.objects.create(
        file=request.FILES.get('file'),
        user=request.user,
        info=request.POST.get('info', ''),
        expr=parse_expire(request, request.user),
    )
    if not file.file:
        return HttpResponse(status=400)
    process_file_upload.delay(file.pk)
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
        file = Files.objects.create(
            file=request.FILES.get('file'),
            user=user,
            info=request.POST.get('info', ''),
            expr=parse_expire(request, user),
        )
        if not file.file:
            return JsonResponse({'error': 'File Not Created'}, status=400)
        process_file_upload.delay(file.pk)
        data = {
            'files': [file.get_url()],
            'url': file.get_url(),
            'name': file.name,
            'size': file.size,
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


def get_auth_user(request):
    if request.user.is_authenticated:
        return request.user
    authorization = request.headers.get('Authorization') or request.headers.get('Token')
    if not authorization:
        return
    return CustomUser.objects.get(authorization=authorization)


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
        'DestinationType': 'ImageUploader, FileUploader',
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
        'Name': f'Django Files - {request.get_host()} - URL Shorts',
        'DestinationType': 'URLShortener,URLSharingService',
        'RequestMethod': 'POST',
        'RequestURL': request.build_absolute_uri(reverse('home:api-shorten')),
        'Headers': {
            'Authorization': request.user.authorization,
        },
        'Body': 'JSON',
        'URL': '{json:url}',
        "Data": '{"url":"{input}"}',
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
    log.debug('message: %s', message)
    response = HttpResponse(message)
    response['Content-Disposition'] = 'attachment; filename="flameshot.sh"'
    return response


@require_http_methods(['GET'])
def url_route_view(request, filename):
    """
    View  /u/<path:filename>
    """
    log.debug('url_route_view: %s', filename)
    file = get_object_or_404(Files, name=filename)
    raw_url = request.build_absolute_uri(reverse('home:url-raw', kwargs={'filename': filename}))
    preview_url = request.build_absolute_uri(reverse('home:url-route', kwargs={'filename': filename}))
    context = {
        'file': file,
        'site_url': request.build_absolute_uri(),
        'raw_url': raw_url,
        'preview_url': preview_url,
    }
    if file.mime.startswith('image'):
        if file.exif and isinstance(file.exif, str):
            context['exif'] = json.loads(file.exif)
            if context['exif'].get('ExposureTime'):
                context['exif']['ExposureTime'] = Fraction(context['exif']['ExposureTime']).limit_denominator(5000)
            if context['exif'].get("GPSInfo"):
                context['city_state'] = city_state_from_exif(context['exif']["GPSInfo"])
            if lens_model := context['exif'].get('LensModel'):
                # handle cases where lensmodel is relevant but some values redunant
                lm_f_stripped = lens_model.replace(f"f/{context['exif'].get('FNumber', '')}", "")
                lm_model_stripped = lm_f_stripped.replace(f"{context['exif'].get('Model')}", "")
                context['exif']['LensModel'] = lm_model_stripped
        else:
            context['exif'] = {}
        return render(request, 'embed/preview.html', context=context)
    elif file.mime == 'text/plain':
        # if not md send text preview
        text_preview = Path(file.file.path).read_text()
        text_preview = open(file.file.path, 'r').read()
        # with open(file.file.path) as input_file:
        #     print("file open")
        #     num_lines = sum(1 for _ in input_file)
        #     preview_limit = 400
        #     if num_lines <= num_lines:
        #         text_preview = input_file.read()
        #     else:
        #         text_preview = [next(input_file) for _ in range(preview_limit)]
        context['text_preview'] = text_preview
        log.debug(text_preview)
        return render(request, 'embed/preview.html', context=context)
    elif file.mime == 'text/markdown':
        with open(file.file.path, 'r', encoding="utf-8") as f:
            context['markdown'] = markdown.markdown(f.read(), extensions=['extra', 'toc'])
        return render(request, 'embed/markdown.html', context=context)
    elif file.mime.startswith('text/'):
        with open(file.file.path, 'r', encoding="utf-8") as f:
            code = f.read()
        # lexer = get_lexer_by_name("python", stripall=True)
        lexer = get_lexer_for_mimetype(file.mime, stripall=True)
        formatter = HtmlFormatter(style='github-dark')
        # css = formatter.get_style_defs()
        # html = highlight(code, lexer, formatter)
        context = {
            'css': formatter.get_style_defs(),
            'html': highlight(code, lexer, formatter),
        }
        return render(request, 'embed/code.html', context=context)


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


def city_state_from_exif(gps_ifd: dict) -> str:
    geolocator = Nominatim(user_agent="django-files")
    try:
        dn, mn, sn, dw, mw, sw = strip_dms(gps_ifd)
        dms_string = f"{int(dn)}°{int(mn)}'{sn}\" N, \
        {int(dw) if dw is not None else ''}°{int(mw) if mw is not None else ''}'{sw if sw is not None else ''}\" W"
        location = geolocator.reverse(dms_string)
        if not (area := location.raw['address'].get('city')):
            area = location.raw['address'].get('county')
        state = location.raw['address'].get('state', '')
        return f"{area}, {state}"
    except Exception as error:
        log.error(error)


def strip_dms(gps_ifd: dict) -> list:
    try:
        dn, mn, sn = gps_ifd["2"]
        dw, mw, sw = gps_ifd["4"]
        return [dn, mn, sn, dw, mw, sw]
    except Exception as error:
        log.error(error)
