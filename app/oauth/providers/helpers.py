import logging
from decouple import config, Csv
from django.http import HttpRequest
from django.urls import reverse

log = logging.getLogger('app')


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


def is_super_id(oauth_id):
    if oauth_id in config('SUPER_USERS', '', Csv()):
        return True
    else:
        return False
