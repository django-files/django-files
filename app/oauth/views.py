import httpx
import logging
import urllib.parse
from datetime import datetime, timedelta
from decouple import config, Csv
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.http import HttpRequest, HttpResponse
from django.shortcuts import HttpResponseRedirect, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from home.models import Webhooks
from oauth.forms import LoginForm
from oauth.models import CustomUser

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
        login(request, user)
        messages.info(request, f'Successfully logged in as {user.username}.')
        return HttpResponse()

    if request.user.is_authenticated:
        next_url = get_next_url(request)
        return HttpResponseRedirect(next_url)
    else:
        return render(request, 'login.html')


def oauth_start(request):
    """
    View  /oauth/start/
    """
    request.session['login_redirect_url'] = get_next_url(request)
    log.debug('oauth_start: login_redirect_url: %s', request.session.get('login_redirect_url'))
    params = {
        'redirect_uri': config('OAUTH_REDIRECT_URL'),
        'client_id': config('OAUTH_CLIENT_ID'),
        'response_type': config('OAUTH_RESPONSE_TYPE', 'code'),
        'scope': config('OAUTH_SCOPE', 'identify'),
        'prompt': config('OAUTH_PROMPT', 'none'),
    }
    url_params = urllib.parse.urlencode(params)
    url = f'https://discord.com/api/oauth2/authorize?{url_params}'
    log.debug('url: %s', url)
    return HttpResponseRedirect(url)


def oauth_callback(request):
    """
    View  /oauth/callback/
    """
    log.debug('oauth_callback: login_next_url: %s', request.session.get('login_next_url'))
    if 'code' not in request.GET:
        messages.warning(request, 'User aborted or no code in response...')
        return HttpResponseRedirect(get_login_redirect_url(request))
    try:
        log.debug('code: %s', request.GET['code'])
        auth_data = get_access_token(request.GET['code'])
        log.debug('auth_data: %s', auth_data)
        profile = get_user_profile(auth_data)
        log.debug('profile: %s', profile)
        user, _ = CustomUser.objects.get_or_create(username=profile['id'])
        update_profile(user, profile)
        login(request, user)
        if 'webhook' in auth_data:
            log.debug('webhook in profile')
            webhook = add_webhook(request, auth_data)
            messages.info(request, f'Webhook successfully added: {webhook.id}')
        else:
            messages.info(request, f'Successfully logged in. {user.first_name}.')
    except Exception as error:
        log.exception(error)
        messages.error(request, f'Exception during login: {error}')
    return HttpResponseRedirect(get_login_redirect_url(request))


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
    request.session['login_redirect_url'] = get_next_url(request)
    log.debug('oauth_webhook: login_redirect_url: %s', request.session.get('login_redirect_url'))
    params = {
        'redirect_uri': config('OAUTH_REDIRECT_URL'),
        'client_id': config('OAUTH_CLIENT_ID'),
        'response_type': config('OAUTH_RESPONSE_TYPE', 'code'),
        'scope': config('OAUTH_SCOPE', 'identify') + ' webhook.incoming',
    }
    url_params = urllib.parse.urlencode(params)
    url = f'https://discord.com/api/oauth2/authorize?{url_params}'
    return HttpResponseRedirect(url)


def add_webhook(request, profile):
    """
    Add webhook
    """
    webhook = Webhooks(
        hook_id=profile['webhook']['id'],
        guild_id=profile['webhook']['guild_id'],
        channel_id=profile['webhook']['channel_id'],
        url=profile['webhook']['url'],
        owner=request.user,
    )
    webhook.save()
    return webhook


def get_access_token(code: str) -> dict:
    """
    Post OAuth code and Return access_token
    """
    log.debug('get_access_token')
    url = 'https://discord.com/api/v8/oauth2/token'
    data = {
        'redirect_uri': config('OAUTH_REDIRECT_URL'),
        'client_id': config('OAUTH_CLIENT_ID'),
        'client_secret': config('OAUTH_CLIENT_SECRET'),
        'grant_type': config('OAUTH_GRANT_TYPE', 'authorization_code'),
        'code': code,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = httpx.post(url, data=data, headers=headers, timeout=10)
    if not r.is_success:
        log.info('status_code: %s', r.status_code)
        log.error('content: %s', r.content)
        r.raise_for_status()
    return r.json()


def get_user_profile(token_data: dict) -> dict:
    """
    Get Profile for Authenticated User
    """
    log.debug('get_user_profile')
    url = 'https://discord.com/api/v8/users/@me'
    headers = {'Authorization': f"Bearer {token_data['access_token']}"}
    r = httpx.get(url, headers=headers, timeout=10)
    if not r.is_success:
        log.info('status_code: %s', r.status_code)
        log.error('content: %s', r.content)
        r.raise_for_status()
    log.debug('r.json(): %s', r.json())
    p = r.json()
    # profile - Custom user data from oauth provider
    return {
        'id': p['id'],
        'username': p['username'],
        'discriminator': p['discriminator'],
        'avatar': p['avatar'],
        'access_token': token_data['access_token'],
        'refresh_token': token_data['refresh_token'],
        'expires_in': datetime.now() + timedelta(0, token_data['expires_in']),
    }


def update_profile(user: CustomUser, profile: dict) -> None:
    """
    Update Django user profile with provided data
    """
    log.debug('update_profile')
    user.first_name = profile['username']
    user.last_name = profile['discriminator']
    user.avatar_hash = profile['avatar']
    user.access_token = profile['access_token']
    user.refresh_token = profile['refresh_token']
    user.expires_in = profile['expires_in']
    if profile['id'] in config('SUPER_USERS', '', Csv()):
        log.info('Super user login: %s', profile['id'])
        user.is_staff, user.is_admin, user.is_superuser = True, True, True
    user.save()


def get_next_url(request: HttpRequest) -> str:
    """
    Determine 'next' parameter
    """
    log.debug('get_next_url')
    if 'next' in request.GET:
        log.debug('next in request.GET: %s', str(request.GET['next']))
        return str(request.GET['next'])
    if 'next' in request.POST:
        log.debug('next in request.POST: %s', str(request.POST['next']))
        return str(request.POST['next'])
    if 'login_next_url' in request.session:
        log.debug('login_next_url in request.session: %s', request.session['login_next_url'])
        url = request.session['login_next_url']
        del request.session['login_next_url']
        request.session.modified = True
        return url
    if 'HTTP_REFERER' in request.META:
        log.debug('HTTP_REFERER in request.META: %s', request.META['HTTP_REFERER'])
        return request.META['HTTP_REFERER']
    log.info('----- get_next_url FAILED -----')
    return reverse('home:index')


def get_login_redirect_url(request: HttpRequest) -> str:
    """
    Determine 'login_redirect_url' parameter
    """
    log.debug('get_login_redirect_url: login_redirect_url: %s', request.session.get('login_redirect_url'))
    if 'login_redirect_url' in request.session:
        url = request.session['login_redirect_url']
        del request.session['login_redirect_url']
        request.session.modified = True
        return url
    return reverse('home:index')
