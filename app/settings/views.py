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
from oauth.forms import LoginForm
from settings.forms import SiteSettingsForm, UserSettingsForm
from settings.models import SiteSettings, Webhooks

log = logging.getLogger('app')
cache_seconds = 60*60*4


@csrf_exempt
@login_required
def site_view(request):
    """
    View  /settings/site/
    """
    log.debug('site_view: %s', request.method)
    site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
    log.debug('site_settings.github_client_id: %s', site_settings.github_client_id)
    if request.method in ['GET', 'HEAD']:
        webhooks = Webhooks.objects.get_request(request)
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
    if request.user.is_superuser:
        site_settings.site_url = form.cleaned_data['site_url']
        site_settings.site_title = form.cleaned_data['site_title']
        site_settings.site_description = form.cleaned_data['site_description']
        site_settings.site_color = form.cleaned_data['site_color']
        site_settings.pub_load = form.cleaned_data['pub_load']
        site_settings.oauth_reg = form.cleaned_data['oauth_reg']
        site_settings.duo_auth = form.cleaned_data['duo_auth']
        site_settings.save()

    # # TODO: Determine if this is superuser setting or user setting
    # request.user.s3_bucket_name = form.cleaned_data.get('s3_bucket_name')

    request.user.save()
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
    site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
    if request.method in ['GET', 'HEAD']:
        webhooks = Webhooks.objects.get_request(request)
        context = {'webhooks': webhooks, 'site_settings': site_settings}
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
    log.debug('form.cleaned_data.show_exif_preview: %s', form.cleaned_data['show_exif_preview'])
    log.debug('request.user.show_exif_preview: %s', request.user.show_exif_preview)

    request.user.save()
    if data['reload']:
        messages.success(request, 'Settings Saved Successfully.')
    return JsonResponse(data, status=200)


@csrf_exempt
@login_required
def welcome_view(request):
    """
    View  /welcome/
    """
    site_settings = SiteSettings.objects.get(pk=1)
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
        user.save()
        login(request, user)

        site_settings.initial_setup = False
        log.debug('site_settings.initial_setup: %s', site_settings.initial_setup)
        site_settings.save()
        request.session['login_redirect_url'] = reverse('settings:site')
        return HttpResponse(status=200)

    if not site_settings.initial_setup:
        return redirect('settings:site')
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
