import logging
from django import template
from django.conf import settings
from django.templatetags.static import static

logger = logging.getLogger('app')
register = template.Library()


@register.simple_tag(name='get_config')
def get_config(value):
    # get django setting value or return none
    return getattr(settings, value, None)


@register.filter(name='absolute_url')
def absolute_url(absolute_uri):
    # returns the absolute_url from the absolute_uri
    return '{0}//{2}'.format(*absolute_uri.split('/'))


@register.filter(name='avatar_url')
def avatar_url(user):
    # return discord avatar url from user model
    if user.avatar_hash:
        return f'https://cdn.discordapp.com/avatars/' \
               f'{ user.username }/{ user.avatar_hash }.png'
    else:
        return static('images/assets/default.png')


@register.filter(name='get_scheme')
def get_scheme(meta):
    # TODO: Deprecate this Shit
    if 'HTTP_X_FORWARDED_PROTO' in meta:
        return meta['HTTP_X_FORWARDED_PROTO']
    if 'HTTP_REFERER' in meta:
        return meta['HTTP_REFERER'].split(':')[0]
    return 'http'


# @register.filter(name='bytes_human')
# def bytes_human(num):
#     suffix = 'B'
#     for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
#         if abs(num) < 1024.0:
#             return f"{num:3.1f}{unit}{suffix}"
#         num /= 1024.0
#     return f"{num:.1f}Yi{suffix}"
