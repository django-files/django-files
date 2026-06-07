import base64
import hashlib
import time

from django.conf import settings


def sign_nginx_urls(uri: str) -> str:
    # nginx interprets $secure_link_expires as a Unix epoch (UTC); use time.time()
    # so signing matches regardless of the Django process timezone.
    expiry = int(time.time()) + settings.SIGNED_URL_TTL_SECONDS
    secure_link = "{uri}{expiry} {key}".format(uri=uri, expiry=expiry, key=settings.SECRET_KEY).encode(
        encoding="utf-8"
    )
    link_hash = hashlib.md5(secure_link).digest()  # nosec
    base64_hash = base64.urlsafe_b64encode(link_hash)
    str_hash = base64_hash.decode("utf-8").rstrip("=")
    return f"?md5={str_hash}&expires={expiry}"
