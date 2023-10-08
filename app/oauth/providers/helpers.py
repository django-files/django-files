import logging
from decouple import config, Csv
from django.urls import reverse
from typing import Optional

from oauth.models import CustomUser
from settings.models import SiteSettings

log = logging.getLogger('app')


def get_or_create_user(request, _id, username) -> Optional[CustomUser]:
    log.debug('_id: %s', _id)
    log.debug('username %s', username)

    # get user by Oauth Provider ID
    user = CustomUser.objects.filter(discord__id=_id) or CustomUser.objects.filter(github__id=_id)
    if user:
        # if oauth user already exists and is trying to be claimed
        if request.session.get('oauth_claim_username'):
            del request.session['oauth_claim_username']
            log.info('OAuth ID Already Claimed!')
            return None
        # use found by oauth provider id
        log.debug('got user by ID')
        log.debug(user)
        return user[0]

    # user is connecting to oauth, get user from session claim
    if request.session.get('oauth_claim_username'):
        username = request.session['oauth_claim_username']
        del request.session['oauth_claim_username']
        log.info('OAuth Used oauth_claim_username: %s', username)
        if user := CustomUser.objects.filter(username=username):
            return user[0]

    # get user by username and check if the user has logged in or not
    user = CustomUser.objects.filter(username=username)
    if user:
        log.debug('got user by Username')
        log.debug(user)
        if user[0].last_login:
            # local user exists but has already logged in
            log.warning('Hijacking Attempt BLOCKED! Connect account via Settings page.')
            return None
        # local user matching oauth username exist and has never logged in
        log.info('User %s claimed by OAuth ID: %s', user[0].id, _id)
        return user[0]

    # # no matching accounts found, if registration is enabled, create user
    # if is_super_id(_id):
    #     log.info('%s SUPERUSER by oauth_reg with id: %s', username, _id)
    #     return CustomUser.objects.create(username=username, is_staff=True, is_superuser=True)

    # no matching accounts found, if registration is enabled, create user
    if SiteSettings.objects.settings().oauth_reg or is_super_id(_id):
        log.info('%s created by oauth_reg with id: %s', username, _id)
        return CustomUser.objects.create(username=username)

    log.debug('User does not exist locally and oauth_reg is off: %s', _id)
    return None


def get_next_url(request) -> str:
    """
    Determine 'next' parameter
    """
    site_settings = SiteSettings.objects.settings()
    log.debug('get_next_url')
    if request.user.is_authenticated and site_settings.show_setup:
        return reverse('settings:welcome')
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


def get_login_redirect_url(request) -> str:
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


def is_super_id(_id):
    log.debug('_id: %s', _id)
    log.debug('SUPER_USERS: %s', config('SUPER_USERS', '', Csv()))
    if _id in config('SUPER_USERS', '', Csv()):
        return True
    return False
