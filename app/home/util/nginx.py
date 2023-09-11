import base64
import hashlib
import datetime
import calendar

from django.conf import settings


def sign_nginx_urls(uri: str) -> str:
    future = datetime.datetime.now() + datetime.timedelta(seconds=settings.STATIC_QUERYSTRING_EXPIRE)
    expiry = calendar.timegm(future.timetuple())
    secure_link = "{uri}{expiry} {key}".format(uri=uri, expiry=expiry,
                                               key=settings.SECRET_KEY_FROM_FILE).encode(encoding='utf-8')
    hash = hashlib.md5(secure_link).digest()
    base64_hash = base64.urlsafe_b64encode(hash)
    str_hash = base64_hash.decode('utf-8').rstrip('=')
    return f"?md5={str_hash}&expires={expiry}"
