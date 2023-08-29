import logging
import datetime
from decouple import config
from django import template
from django.conf import settings
from django.templatetags.static import static

logger = logging.getLogger('app')
register = template.Library()


@register.filter(name='get_config')
def get_config(value):
    # get django setting value or empty
    return getattr(settings, value, None) or config(value, '')


@register.filter(name='avatar_url')
def avatar_url(user):
    # return discord avatar url from user model
    if user.avatar_hash:
        return f'https://cdn.discordapp.com/avatars/' \
               f'{ user.username }/{ user.avatar_hash }.png'
    else:
        return static('images/assets/default.png')


@register.filter(name='single_type')
def single_type(mime_type):
    # returns the absolute_url from the absolute_uri
    return str(mime_type.split('/', 1)[0]).lower()


@register.filter(name='bytes_human')
def bytes_human(num):
    # TODO: Update JSON to Include this...
    suffix = 'B'
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


@register.filter(name="convert_str_date")
def convert_str_date(value):
    if not value:
        return ''
    return str(datetime.datetime.strptime(value, '%Y:%m:%d %H:%M:%S').strftime('%m/%d/%Y %H:%M:%S'))


@register.filter(name="sort_mimes")
def sort_mimes(mimes, count=0):
    srt = sorted(mimes.items(), key=lambda x: x[1]['count'])
    if count:
        return list(reversed(srt))[:count]
    else:
        return list(reversed(srt))
