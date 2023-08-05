import httpx
import json
import logging
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, reverse, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from pytimeparse2 import parse
# import plotly.graph_objects as go
# import plotly.express as px
# import plotly.io as pio

from oauth.models import CustomUser, rand_string
from .forms import SettingsForm
from .models import Files, FileStats, SiteSettings, ShortURLs, Webhooks
from .tasks import process_file_upload, process_stats

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
def gallery_view(request):
    """
    View  /gallery/
    """
    log.debug('%s - gallery_view: is_secure: %s', request.method, request.is_secure())
    context = {'files': Files.objects.get_request(request)}
    return render(request, 'gallery.html', context)


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

    request.user.save()
    if data['reload']:
        messages.success(request, 'Settings Saved Successfully.')
    return JsonResponse(data, status=200)


@login_required
@csrf_exempt
def files_view(request):
    """
    View  /files/
    """
    if request.method in ['GET', 'HEAD']:
        return render(request, 'files.html')

    log.debug(request.headers)
    log.debug(request.POST)
    log.debug(request.FILES)
    file = Files.objects.create(
        file=request.FILES.get('file'),
        user=request.user,
        info=request.POST.get('info', ''),
        expr=parse_expire(request, request.user),
    )
    if not file:
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
        if not file:
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
    log.debug('-'*40)
    log.debug(request.headers)
    log.debug('-'*40)
    log.debug(request.POST)
    log.debug('-'*40)
    log.debug(request.body)
    log.debug('-'*40)
    try:
        user = get_auth_user(request)
        if not user:
            return JsonResponse({'error': 'Invalid Authorization'}, status=401)

        # We Are Go
        views = request.headers.get('max-views')
        url = request.headers.get('url')
        vanity = request.headers.get('vanity')
        if not url:
            try:
                body = json.loads(request.body.decode())
                log.debug('body: %s', body)
                views = body.get('max-views')
                url = body.get('url')
                vanity = body.get('vanity')
            except Exception:
                pass
        if not url:
            return JsonResponse({'error': 'Missing Required Value: url'}, status=400)

        log.debug('url: %s', url)
        short = gen_short(vanity)
        log.debug('short: %s', short)
        url = ShortURLs.objects.create(
            url=url,
            short=short,
            views=views or 0,
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
    authorization = request.headers.get('Authorization') or request.headers.get('Token')
    if not authorization:
        return
    return CustomUser.objects.get(authorization=authorization)

# @csrf_exempt
# def get_graph_ajax(request):
#     # View: /ajax/graph/
#     log.debug('get_graph_ajax')
#     stats = FileStats.objects.all()
#     fig = render_graph_fig(stats)
#     fig.update_layout(margin=dict(t=10, l=16, b=10, r=10))
#     fig_html = fig.to_html(
#         include_plotlyjs=False,
#         full_html=False,
#         config={'displaylogo': False},
#     )
#     return HttpResponse(fig_html)
#
#
# def render_graph_fig(stats: FileStats.stats) -> go.Figure:
#     dates, files = [], []
#     for stat in stats:
#         dates.append(stat)
#         files.append(stat)
#     lines = [('Files', files)]
#     pio.templates.default = "plotly_dark"
#     fig = go.Figure()
#     for name, data in lines:
#         fig.add_trace(go.Scatter(x=dates, y=data, name=name))
#     fig.update_layout(xaxis_title='Date', yaxis_title='Count')
#     return fig


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
        'Version': '14.1.0',
        'Name': f'Django Files - {request.get_host()} - File',
        'DestinationType': 'ImageUploader, FileUploader',
        'RequestMethod': 'POST',
        'RequestURL': request.build_absolute_uri(reverse('home:upload')),
        'Headers': {
            'Authorization': request.user.authorization,
            'Expires-At': request.user.default_expire,
        },
        'Body': 'MultipartFormData',
        'FileFormName': 'file',
        'URL': '{json:url}',
        'ErrorMessage': '{json:error}'
    }
    # Create the HttpResponse object with the appropriate headers.
    filename = f'{request.get_host()} - Files.sxcu'
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
