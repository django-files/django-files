import logging
import duo_universal
from decouple import config
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import HttpResponseRedirect, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from settings.models import SiteSettings
from oauth.forms import LoginForm
from oauth.models import CustomUser, DiscordWebhooks
from oauth.providers.helpers import get_login_redirect_url, get_next_url, get_or_create_user
from oauth.providers.discord import DiscordOauth
from oauth.providers.github import GithubOauth

log = logging.getLogger('app')


@csrf_exempt
def oauth_show(request):
    """
    View  /oauth/
    """
    if request.method == 'POST':
        request.session['login_redirect_url'] = get_next_url(request)
        form = LoginForm(request.POST)
        if not form.is_valid():
            log.debug(form.errors)
            return HttpResponse(status=400)
        user = authenticate(request,
                            username=form.cleaned_data['username'],
                            password=form.cleaned_data['password'])
        if not user:
            return HttpResponse(status=401)

        if response := pre_login(request, user):
            return response
        login(request, user)
        post_login(request, user)
        messages.info(request, f'Successfully logged in as {user.username}.')
        return HttpResponse()

    if request.user.is_authenticated:
        next_url = get_next_url(request)
        return HttpResponseRedirect(next_url)
    return render(request, 'login.html')


def oauth_discord(request):
    """
    View  /oauth/discord/
    """
    request.session['login_redirect_url'] = get_next_url(request)
    return DiscordOauth.redirect_login(request)


def oauth_github(request):
    """
    View  /oauth/github/
    """
    request.session['login_redirect_url'] = get_next_url(request)
    return GithubOauth.redirect_login(request)


def oauth_callback(request):
    """
    View  /oauth/callback/
    """
    try:
        code = request.GET.get('code')
        log.debug('code: %s', code)
        if not code:
            messages.warning(request, 'User aborted or no code in response...')
            return HttpResponseRedirect(get_login_redirect_url(request))

        log.debug('oauth_callback: login_next_url: %s', request.session.get('login_next_url'))
        if not (code := request.GET.get('code')):
            messages.warning(request, 'User aborted or no code in response...')
            return HttpResponseRedirect(get_login_redirect_url(request))

        if request.session['oauth_provider'] == 'github':
            oauth = GithubOauth(code)
        elif request.session['oauth_provider'] == 'discord':
            oauth = DiscordOauth(code)
        else:
            messages.error(request, 'Unknown Provider: %s' % request.session['oauth_provider'])
            return HttpResponseRedirect(get_login_redirect_url(request))

        oauth.process_login()
        if request.session.get('webhook'):
            del request.session['webhook']
            webhook = oauth.add_webhook(request)
            messages.info(request, f'Webhook successfully added: {webhook.id}')
            return HttpResponseRedirect(get_login_redirect_url(request))

        user = get_or_create_user(request, oauth.id, oauth.username)
        log.debug('user: %s', user)
        if not user:
            messages.error(request, 'User Not Found or Already Taken.')
            return HttpResponseRedirect(get_login_redirect_url(request))

        oauth.update_profile(user)
        if response := pre_login(request, user):
            return response
        login(request, user)
        post_login(request, user)
        messages.info(request, f'Successfully logged in. {user.first_name}.')
        return HttpResponseRedirect(get_login_redirect_url(request))

    except Exception as error:
        log.exception(error)
        messages.error(request, f'Exception during login: {error}')
        return HttpResponseRedirect(get_login_redirect_url(request))


def pre_login(request, user):
    log.debug('username: %s', user.username)
    if SiteSettings.objects.settings().duo_auth:
        request.session['username'] = user.username
        url = duo_redirect(request, user.username)
        log.debug('url: %s', url)
        return JsonResponse({'redirect': url})


def post_login(request, user):
    pass


def duo_callback(request):
    """
    View  /oauth/duo/
    """
    log.debug('%s - duo_callback', request.method)
    try:
        duo_client = get_duo_client(request)
        state = request.GET.get('state')
        log.debug('state: %s', state)
        code = request.GET.get('duo_code')
        log.debug('code: %s', code)
        if state != request.session['state']:
            messages.warning(request, 'State Check Failed. Try Again!')
            return HttpResponseRedirect(get_login_redirect_url(request))
        username = request.session['username']
        log.debug('username: %s', username)
        decoded_token = duo_client.exchange_authorization_code_for_2fa_result(code, username)
        log.debug('decoded_token: %s', decoded_token)
        user = CustomUser.objects.get(username=username)
        login(request, user)

        # if 'profile' in request.session:
        #     log.debug('profile in session, updating oauth profile')
        #     update_profile(user, json.loads(request.session['profile']))
        #     del request.session['profile']

        log.debug('duo_callback: login_next_url: %s', request.session.get('login_next_url'))
        messages.success(request, f'Congrats, You Authenticated Twice, {username}!')
        return HttpResponseRedirect(get_login_redirect_url(request))

    except Exception as error:
        log.exception(error)
        return HttpResponse(status=401)


def duo_redirect(request, username):
    log.debug('duo_redirect: username: %s', username)
    duo_client = get_duo_client(request)
    try:
        duo_client.health_check()
    except duo_universal.DuoException as error:
        log.exception(error)
        raise ValueError('Duo Health Check Failed: %s', error)

    state = duo_client.generate_state()
    log.debug('state: %s', state)
    request.session['state'] = state

    prompt_uri = duo_client.create_auth_url(username, state)
    log.debug('prompt_uri: %s', prompt_uri)
    return prompt_uri


def get_duo_client(request):
    log.debug('request.build_absolute_uri: %s', request.build_absolute_uri())
    site_url = SiteSettings.objects.get(pk=1).site_url
    log.debug('site_url: %s', site_url)
    redirect_uri = site_url.rstrip('/') + reverse('oauth:duo')
    log.debug('redirect_uri: %s', redirect_uri)
    return duo_universal.Client(
        config('DUO_CLIENT_ID'),
        config('DUO_CLIENT_SECRET'),
        config('DUO_API_HOST'),
        redirect_uri,
    )


@csrf_exempt
@require_http_methods(['POST'])
def oauth_logout(request):
    """
    View  /oauth/logout/
    """
    next_url = get_next_url(request)
    log.debug('oauth_logout: next_url: %s', next_url)
    logout(request)
    request.session['login_next_url'] = next_url
    messages.info(request, 'Successfully logged out.')
    log.debug('oauth_logout: login_next_url: %s', request.session.get('login_next_url'))
    return redirect(next_url)


def oauth_webhook(request):
    """
    View  /oauth/webhook/
    """
    return DiscordOauth.redirect_webhook(request)


def add_webhook(request, profile):
    """
    Add webhook
    """
    log.debug('add_webhook')
    webhook = DiscordWebhooks(
        hook_id=profile['webhook']['id'],
        guild_id=profile['webhook']['guild_id'],
        channel_id=profile['webhook']['channel_id'],
        url=profile['webhook']['url'],
        owner=request.user,
    )
    webhook.save()
    return webhook
