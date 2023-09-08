import logging
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, reverse, redirect
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from oauth.models import CustomUser
from oauth.forms import LoginForm, UserForm
from settings.forms import SiteSettingsForm, UserSettingsForm
from settings.models import SiteSettings
from oauth.models import DiscordWebhooks, UserInvites

log = logging.getLogger('app')
cache_seconds = 60*60*4


@csrf_exempt
@login_required
def site_view(request):
    """
    View  /settings/site/
    """
    log.debug('site_view: %s', request.method)
    if not request.user.is_superuser:
        return HttpResponse(status=401)

    site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
    log.debug('site_settings.github_client_id: %s', site_settings.github_client_id)
    if request.method in ['GET', 'HEAD']:
        webhooks = DiscordWebhooks.objects.get_request(request)
        context = {'webhooks': webhooks, 'site_settings': site_settings}
        log.debug('context: %s', context)
        return render(request, 'settings/site.html', context)

    log.debug(request.POST)
    form = SiteSettingsForm(request.POST)
    if not form.is_valid():
        log.debug('form INVALID')
        return JsonResponse(form.errors, status=400)
    data = {'reload': False}
    log.debug(form.cleaned_data)

    site_settings.site_url = form.cleaned_data['site_url']
    site_settings.site_title = form.cleaned_data['site_title']
    site_settings.site_description = form.cleaned_data['site_description']
    site_settings.site_color = form.cleaned_data['site_color']
    site_settings.pub_load = form.cleaned_data['pub_load']
    site_settings.oauth_reg = form.cleaned_data['oauth_reg']
    site_settings.duo_auth = form.cleaned_data['duo_auth']
    site_settings.save()

    if data['reload']:
        messages.success(request, 'Settings Saved Successfully.')
    return JsonResponse(data, status=200)


@csrf_exempt
@login_required
def user_view(request):
    """
    View  /settings/user/
    """
    log.debug('user_view: %s', request.method)
    if request.method != 'POST':
        webhooks = DiscordWebhooks.objects.get_request(request)
        context = {'webhooks': webhooks, 'default_upload_name_formats': CustomUser.UploadNameFormats.choices}
        log.debug('context: %s', context)
        return render(request, 'settings/user.html', context)

    log.debug(request.POST)
    form = UserSettingsForm(request.POST)
    if not form.is_valid():
        log.debug('form INVALID')
        return JsonResponse(form.errors, status=400)
    data = {'reload': False}
    log.debug(form.cleaned_data)

    request.user.default_expire = form.cleaned_data['default_expire']

    if request.user.default_color != form.cleaned_data['default_color']:
        request.user.default_color = form.cleaned_data['default_color']

    if request.user.nav_color_1 != form.cleaned_data['nav_color_1']:
        request.user.nav_color_1 = form.cleaned_data['nav_color_1']
        data['reload'] = True

    if request.user.nav_color_2 != form.cleaned_data['nav_color_2']:
        request.user.nav_color_2 = form.cleaned_data['nav_color_2']
        data['reload'] = True

    request.user.remove_exif_geo = form.cleaned_data['remove_exif_geo']
    request.user.remove_exif = form.cleaned_data['remove_exif']
    request.user.show_exif_preview = form.cleaned_data['show_exif_preview']
    request.user.default_upload_name_format = form.cleaned_data['default_upload_name_format']
    log.debug('form.cleaned_data.show_exif_preview: %s', form.cleaned_data['show_exif_preview'])
    log.debug('request.user.show_exif_preview: %s', request.user.show_exif_preview)

    request.user.save()
    if data['reload']:
        messages.success(request, 'Settings Saved Successfully.')
    return JsonResponse(data, status=200)


@csrf_exempt
def invite_view(request, invite):
    """
    View  /invite/
    """
    log.debug('request.method: %s', request.method)
    if request.user.is_authenticated:
        log.debug('request.user.is_authenticated: %s', request.user.is_authenticated)
        return redirect('home:index')
    if request.method == 'POST':
        log.debug('request.POST: %s', request.POST)
        # invite = get_invite(invite)
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
            )
        else:
            user = CustomUser.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
        log.debug('user: %s', user)
        if not invite.use_invite(user.id):
            return JsonResponse(form.errors, status=400)
        login(request, user)
        request.session['login_redirect_url'] = reverse('settings:user')
        messages.info(request, f'Welcome to Django Files {request.user.username}.')
        return HttpResponse(status=200)

    log.debug('request.GET: %s', request.GET)
    context = {}
    if invite := UserInvites.objects.get_invite(invite):
        log.debug('invite: %s', invite)
        if invite.is_valid():
            context = {'invite': invite.invite}
    log.debug('context: %s', context)
    return render(request, 'settings/invite.html', context=context)


@csrf_exempt
@login_required
def welcome_view(request):
    """
    View  /welcome/
    """
    if not request.user.show_setup:
        return redirect('settings:site')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if not form.is_valid():
            log.debug(form.errors)
            return HttpResponse(status=400)

        user = CustomUser.objects.get(pk=request.user.pk)
        user.username = form.cleaned_data['username']
        log.debug('username: %s', form.cleaned_data['username'])
        user.set_password(form.cleaned_data['password'])
        log.debug('password: %s', form.cleaned_data['password'])
        user.show_setup = False
        user.save()
        login(request, user)
        request.session['login_redirect_url'] = reverse('settings:site')
        messages.info(request, f'Welcome to Django Files {request.user.username}.')
        return HttpResponse(status=200)

    return render(request, 'settings/welcome.html')


@login_required
@require_http_methods(['GET'])
def gen_sharex(request):
    """
    View  /settings/sharex/
    """
    log.debug('gen_sharex')
    data = {
        'Version': '15.0.0',
        'Name': f'Django Files - {request.get_host()} - File',
        'DestinationType': 'ImageUploader, FileUploader, TextUploader',
        'RequestMethod': 'POST',
        'RequestURL': request.build_absolute_uri(reverse('api:upload')),
        'Headers': {
            'Authorization': request.user.authorization,
            'Expires-At': request.user.default_expire,
        },
        'Body': 'MultipartFormData',
        'URL': '{json:url}',
        'FileFormName': 'file',
        'ErrorMessage': '{json:error}'
    }
    filename = f'{request.get_host()} - Files.sxcu'
    response = JsonResponse(data, json_dumps_params={'indent': 4})
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_http_methods(['GET'])
def gen_sharex_url(request):
    """
    View  /settings/sharex-url/
    """
    log.debug('gen_sharex_url')
    data = {
        'Version': '15.0.0',
        'Name': f'Django Files - {request.get_host()} - URL',
        'DestinationType': 'URLShortener, URLSharingService',
        'RequestMethod': 'POST',
        'RequestURL': request.build_absolute_uri(reverse('api:shorten')),
        'Headers': {
            'Authorization': request.user.authorization,
        },
        'Body': 'JSON',
        'URL': '{json:url}',
        'Data': '{"url":"{input}"}',
        'ErrorMessage': '{json:error}',
    }
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
    context = {'site_url': request.build_absolute_uri(reverse('home:upload')), 'token': request.user.authorization}
    log.debug('context: %s', context)
    message = render_to_string('scripts/flameshot.sh', context)
    response = HttpResponse(message)
    response['Content-Disposition'] = 'attachment; filename="flameshot.sh"'
    return response
