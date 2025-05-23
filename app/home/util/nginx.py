import base64
import calendar
import datetime
import hashlib

from django.conf import settings


def sign_nginx_urls(uri: str) -> str:
    future = datetime.datetime.now() + datetime.timedelta(seconds=settings.STATIC_QUERYSTRING_EXPIRE)
    expiry = calendar.timegm(future.timetuple())
    secure_link = "{uri}{expiry} {key}".format(uri=uri, expiry=expiry, key=settings.SECRET_KEY).encode(
        encoding="utf-8"
    )
    link_hash = hashlib.md5(secure_link).digest()  # nosec
    base64_hash = base64.urlsafe_b64encode(link_hash)
    str_hash = base64_hash.decode("utf-8").rstrip("=")
    return f"?md5={str_hash}&expires={expiry}"
