import datetime
import logging
from typing import Literal, Optional, Union

from decouple import config
from django import template
from django.conf import settings
from django.http import HttpRequest


# from django.templatetags.static import static

logger = logging.getLogger("app")
register = template.Library()


@register.filter(name="if_true")
def if_true(value, output):
    # return output if value is true else empty
    return output if value else ""


@register.filter(name="if_false")
def if_false(value, output):
    # return output if value is true else empty
    return output if not value else ""


@register.filter(name="get_config")
def get_config(value: str):
    # get django setting or config value or empty
    return getattr(settings, value, None) or config(value, "")


@register.simple_tag(name="is_mobile")
def is_mobile(request: HttpRequest, platform: Optional[Literal["android", "ios"]] = None) -> Union[dict, bool]:
    """
    Returns a Dictionary of Mobile Clients else False
    If the platform is specified, only a boolean is returned
    :param request: HttpRequest: request
    :param platform: Literal: android|ios
    :return: bool|dict
    """
    if request and isinstance(request.META, dict):
        ua = request.META.get("HTTP_USER_AGENT", "")
        if "DjangoFiles" in ua:
            data = {
                "android": "Android" in ua,
                "ios": "iOS" in ua,
                "name": "Unknown",
            }
            if data["ios"]:
                data["name"] = "iOS"
            if data["android"]:
                data["name"] = "Android"
            if platform:
                if platform in data:
                    return data[platform]
                else:
                    raise ValueError(f"Unknown platform: {platform}")
            return data
    return False


@register.simple_tag(name="is_ios_browser")
def is_ios_browser(request: HttpRequest) -> bool:
    """
    Returns True if the request is from an iOS device (iPhone, iPad, iPod)
    :param request: HttpRequest: request
    :return: bool
    """
    if request and isinstance(request.META, dict):
        ua = request.META.get("HTTP_USER_AGENT", "").lower()
        return any(x in ua for x in ["iphone", "ipad"])
    return False


# @register.filter(name='avatar_url')
# def avatar_url(user):
#     # return discord avatar url from user model
#     if user.avatar_hash:
#         return f'https://cdn.discordapp.com/avatars/' \
#                f'{ user.username }/{ user.avatar_hash }.png'
#     else:
#         return static('images/assets/default.png')


@register.filter(name="single_type")
def single_type(mime_type: str):
    parts = mime_type.split("/", 1)
    return parts[0].lower() if parts else ""


@register.filter(name="bytes_human")
def bytes_human(num):
    # TODO: Update JSON to Include this...
    suffix = "B"
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


@register.filter(name="convert_str_date")
def convert_str_date(value):
    if not value:
        return ""
    try:
        return str(datetime.datetime.strptime(value, "%Y:%m:%d %H:%M:%S").strftime("%m/%d/%Y %H:%M:%S"))
    except Exception as error:
        logger.info(error)
        return ""


@register.filter(name="sort_mimes")
def sort_mimes(mimes, count=0):
    srt = sorted(mimes.items(), key=lambda x: x[1]["count"])
    if count:
        return list(reversed(srt))[:count]
    else:
        return list(reversed(srt))
