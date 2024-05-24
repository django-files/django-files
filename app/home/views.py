import logging
import markdown
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render, reverse, get_object_or_404
from django.views.decorators.common import no_append_slash
from django.views.decorators.cache import cache_page, cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie
from fractions import Fraction

from api.views import auth_from_token, process_file_upload, parse_expire
from home.models import Files, FileStats, ShortURLs
from home.tasks import clear_shorts_cache, process_stats
from home.util.s3 import use_s3
from home.util.storage import fetch_file
from oauth.forms import UserForm
from oauth.models import CustomUser, DiscordWebhooks, UserInvites
from settings.models import SiteSettings
from settings.context_processors import site_settings_processor

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
    stats = FileStats.objects.get_request(request)
    shorts = ShortURLs.objects.get_request(request)
    context = {'stats': stats, 'shorts': shorts, 'full_context': True}
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


@login_required
def files_view(request):
    """
    View  /files/ or /gallery/
    """
    context = {'full_context': True}
    if request.user.is_superuser:
        users = CustomUser.objects.all()
        context.update({'users': users})
    log.debug('%s - gallery_view: is_secure: %s', request.method, request.is_secure())
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


@csrf_exempt
@cache_control(no_cache=True)
@login_required
def uppy_view(request):
    """
    View  /uppy/
    """
    return render(request, 'uppy.html')


@csrf_exempt
@cache_control(no_cache=True)
@login_required
def paste_view(request):
    """
    View  /paste/
    """
    context = {
        'default_upload_name_formats': CustomUser.UploadNameFormats.choices,
    }
    return render(request, 'paste.html', context=context)


@csrf_exempt
@cache_control(no_cache=True)
def pub_uppy_view(request):
    """
    View  /public/
    """
    log.debug('%s - pub_uppy_view', request.method)
    log.debug('request.user: %s', request.user)
    try:
        site_settings = SiteSettings.objects.settings()
        log.debug('site_settings: %s', site_settings)
        if not site_settings.pub_load:
            if request.user.is_authenticated:
                messages.warning(request, 'You Must Enable Public Uploads.')
                return HttpResponseRedirect(reverse('settings:site'))
            return HttpResponseRedirect(reverse('oauth:login') + '?next=' + reverse('home:public-uppy'))

        if request.method == 'POST':
            if not (f := request.FILES.get('file')):
                return JsonResponse({'error': 'No File Found at Key: file'}, status=400)
            kwargs = {'expr': parse_expire(request), 'info': request.POST.get('info')}
            if not request.user.is_authenticated:
                request.user, _ = CustomUser.objects.get_or_create(username='public')
            return process_file_upload(f, request.user.id, **kwargs)

        return render(request, 'uppy.html')
    except Exception as error:
        log.exception(error)
        return JsonResponse({'error': str(error)}, status=500)


@csrf_exempt
def invite_view(request, invite=None):
    """
    View  /i/
    """
    log.debug('request.method: %s', request.method)
    if request.user.is_authenticated:
        log.debug('request.user.is_authenticated: %s', request.user.is_authenticated)
        return redirect('home:index')
    if request.method == 'POST':
        log.debug('request.POST: %s', request.POST)
        invite = UserInvites.objects.get_invite(invite)
        log.debug('invite: %s', invite)
        if not invite or not invite.is_valid():
            return HttpResponse(status=400)

        form = UserForm(request.POST)
        if not form.is_valid():
            return JsonResponse(form.errors, status=400)
        log.debug('username: %s', form.cleaned_data['username'])
        log.debug('password: %s', form.cleaned_data['password'])
        if invite.super_user:
            user = CustomUser.objects.create_superuser(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                storage_quota=invite.storage_quota,
            )
        else:
            user = CustomUser.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                storage_quota=invite.storage_quota,
            )
        log.debug('user: %s', user)
        if not invite.use_invite(user.id):
            return JsonResponse(form.errors, status=400)
        login(request, user)
        request.session['login_redirect_url'] = reverse('settings:user')
        messages.info(request, f'Welcome to Django Files {request.user.get_name()}.')
        return HttpResponse(status=200)

    log.debug('request.GET: %s', request.GET)
    context = {}
    if invite := UserInvites.objects.get_invite(invite):
        log.debug('invite: %s', invite)
        if invite.is_valid():
            context = {'invite': invite}
    log.debug('context: %s', context)
    return render(request, 'invite.html', context=context)


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
    file = get_object_or_404(Files, pk=pk)
    if file.user != request.user:
        return HttpResponse(status=401)
    log.debug(file)
    file.delete()
    return HttpResponse(status=204)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def set_password_file_ajax(request, pk):
    """
    View  /ajax/set_password/file/<int:pk>/
    """
    log.debug('password_hook_view_a: %s', pk)
    file = get_object_or_404(Files, pk=pk)
    if file.user != request.user:
        return HttpResponse(status=401)
    log.debug(file)
    file.password = request.POST.get('password')
    file.save()
    return HttpResponse(status=200)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def set_expr_file_ajax(request, pk):
    """
    View  /ajax/set_expr/file/<int:pk>/
    """
    log.debug('expr_hook_view_a: %s', pk)
    file = get_object_or_404(Files, pk=pk)
    if file.user != request.user:
        return HttpResponse(status=401)
    log.debug(file)
    file.expr = request.POST.get('expr')
    file.save()
    return HttpResponse(status=200)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def toggle_private_file_ajax(request, pk):
    """
    View  /ajax/toggle_private/file/<int:pk>/
    """
    log.debug('toggle_private_hook_view_a: %s', pk)
    file = get_object_or_404(Files, pk=pk)
    if file.user != request.user:
        return HttpResponse(status=401)
    log.debug(file)
    if file.private:
        file.private = False
    else:
        file.private = True
    file.save()
    return HttpResponse(file.private, status=200)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def delete_short_ajax(request, pk):
    """
    View  /ajax/delete/short/<int:pk>/
    TODO: Implement into /short/ using DELETE method
    """
    log.debug('del_hook_view_a: %s', pk)
    short = get_object_or_404(ShortURLs, pk=pk)
    if short.user != request.user:
        return HttpResponse(status=401)
    log.debug(short)
    short.delete()
    return HttpResponse(status=204)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def delete_hook_ajax(request, pk):
    """
    View  /ajax/delete/hook/<int:pk>/
    """
    log.debug('delete_hook_ajax: %s', pk)
    webhook = get_object_or_404(DiscordWebhooks, pk=pk)
    if webhook.owner != request.user:
        return HttpResponse(status=404)
    log.debug(webhook)
    webhook.delete()
    return HttpResponse(status=204)


@csrf_exempt
@require_http_methods(['POST'])
def check_password_file_ajax(request, pk):
    """
    View  /ajax/check_password/file/<int:pk>/
    """
    log.debug('check_password_file_ajax: %s', pk)
    file = get_object_or_404(Files, pk=pk)
    if file.password != request.POST.get('password'):
        return HttpResponse(status=401)
    return HttpResponse(status=200)


@no_append_slash
@require_http_methods(['GET'])
@auth_from_token(no_fail=True)
def raw_redirect_view(request, filename):
    """
    View /raw/<path:filename>
    """
    # TODO: Fully Outline/Document what this does
    log.debug('url_route_raw: %s', filename)
    file = get_object_or_404(Files, name=filename)
    ctx = {"file": file}
    response = HttpResponse(status=302)
    if lock := file_lock(request, ctx):
        return lock
    if request.GET.get('thumb', False):
        # use site settings context processor for caching
        site_settings = site_settings_processor(None)['site_settings']
        if use_s3():
            response['Location'] = file.get_gallery_url()
        else:
            response['Location'] = site_settings['site_url'] + file.get_gallery_url()
        return response
    session_view = request.session.get(f'view_{file.name}', True)
    url = file.get_url(session_view, request.GET.get('download', False))
    if session_view:
        request.session[f'view_{file.name}'] = False
    response['Location'] = url
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
    session_view = request.session.get(f'view_{file.name}', True)
    log.debug(f"User {request.user} has not viewed file {file.name}: {session_view}")
    ctx = {
        'file': file,
        'render': file.mime.split('/', 1)[0],
        "static_url": file.get_url(view=session_view),
        "static_meta_url": file.get_meta_static_url(),
        "file_avatar_url": file.user.get_avatar_url(),
        'full_context': request.user.is_authenticated and request.user == file.user
    }
    if session_view:
        request.session[f'view_{file.name}'] = False
    if lock := file_lock(request, ctx=ctx):
        return lock
    log.debug('ctx: %s', ctx)
    if file.mime.startswith('image'):
        log.debug('IMAGE')
        if file.exif:
            if exposure_time := file.exif.get('ExposureTime'):
                file.exif['ExposureTime'] = str(Fraction(exposure_time).limit_denominator(5000))
            if lens_model := file.exif.get('LensModel'):
                # handle cases where lensmodel is relevant but some values are redundant
                lm_f_stripped = lens_model.replace(f"f/{file.exif.get('FNumber', '')}", "")
                lm_model_stripped = lm_f_stripped.replace(f"{file.exif.get('Model')}", "")
                file.exif['LensModel'] = lm_model_stripped
        return render(request, 'embed/preview.html', context=ctx)
    elif file.mime == 'text/markdown':
        log.debug('MARKDOWN')
        if use_s3():
            md_text = file.file.read().decode("utf-8")
        else:
            with open(file.file.path, 'r') as f:
                md_text = f.read()
        ctx['markdown'] = markdown.markdown(md_text, extensions=['extra', 'toc'])
        return render(request, 'embed/markdown.html', context=ctx)
    elif file.mime.startswith('text/') or file.mime in code_mimes or file.mime in ['application/javascript']:
        log.debug('CODE')
        ctx['render'] = 'code'
        return render(request, 'embed/preview.html', context=ctx)
    else:
        log.debug('UNKNOWN')
        return render(request, 'embed/preview.html', context=ctx)


@require_http_methods(['GET'])
def proxy_route_view(request, filename):
    """
    View  /p/<path:filename>
    """
    file = get_object_or_404(Files, name=filename)
    session_view = request.session.get(f'view_{file.name}', True)
    log.debug(f"User {request.user} has not viewed file {file.name}: {session_view}")
    ctx = {
        'file': file
    }
    if session_view:
        request.session[f'view_{file.name}'] = False
    if lock := file_lock(request, ctx=ctx):
        return lock
    return HttpResponse(fetch_file(file), content_type=file.mime)


def file_lock(request, ctx):
    """Returns a not allowed if private or file pw page if password set."""
    if (ctx["file"].private and (request.user != ctx["file"].user) and
            (ctx["file"].password is None or ctx["file"].password == '')):
        return render(request, 'error/403.html', context=ctx, status=403)
    if ctx["file"].password and (request.user != ctx["file"].user):
        if (supplied_password := (request.GET.get('password'))) != ctx["file"].password:
            if supplied_password is not None:
                messages.warning(request, 'Invalid Password!')
            return render(request, 'embed/password.html', context=ctx, status=403)
