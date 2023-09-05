import logging
import datetime
from decouple import config
from django import template
from django.conf import settings

log = logging.getLogger('app')
register = template.Library()


@register.filter(name='if_true')
def if_true(value, output):
    # return output if value is true else empty
    return output if value else ''


@register.filter(name='get_config')
def get_config(value):
    # get django setting or config value or empty
    return getattr(settings, value, None) or config(value, '')


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
