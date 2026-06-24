import base64
import hashlib
import hmac
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


def sign_hls_cookie(stream_name: str, ttl_seconds: int = None) -> tuple[str, int]:
    # Sign a token scoped to the HLS asset prefix for one stream so a single cookie
    # covers the manifest and every segment fetch the player will make.
    # Returns (md5_b64, expiry_epoch) suitable for `hls_sig` / `hls_exp` cookies.
    if ttl_seconds is None:
        ttl_seconds = settings.HLS_SIGNED_URL_TTL_SECONDS
    expiry = int(time.time()) + ttl_seconds
    secure_link = "{name}{expiry} {key}".format(name=stream_name, expiry=expiry, key=settings.SECRET_KEY).encode(
        encoding="utf-8"
    )
    # MD5 is mandated by nginx's secure_link_md5 directive; not a free algorithm choice.
    link_hash = hashlib.md5(secure_link).digest()  # nosec  # NOSONAR
    base64_hash = base64.urlsafe_b64encode(link_hash)
    str_hash = base64_hash.decode("utf-8").rstrip("=")
    return str_hash, expiry


def verify_hls_cookie(stream_name: str, sig: str | None, exp: str | None) -> bool:
    # Treat a still-valid hls_sig/hls_exp pair as proof that the bearer already
    # passed the original auth/password gate, so refreshes can be granted without
    # re-asking for the password.
    if not sig or not exp:
        return False
    try:
        exp_int = int(exp)
    except TypeError, ValueError:
        return False
    if exp_int < int(time.time()):
        return False
    secure_link = "{name}{expiry} {key}".format(name=stream_name, expiry=exp_int, key=settings.SECRET_KEY).encode(
        encoding="utf-8"
    )
    expected = (
        base64.urlsafe_b64encode(hashlib.md5(secure_link).digest()).decode("utf-8").rstrip("=")  # nosec  # NOSONAR
    )
    return hmac.compare_digest(expected, sig)


def set_hls_cookies(response, stream_name: str) -> int:
    # Attach hls_sig/hls_exp cookies to `response` so subsequent /hls/ requests pass
    # the nginx secure_link check. Scoped to /hls + httponly. Returns expiry epoch.
    sig, exp = sign_hls_cookie(stream_name)
    ttl = settings.HLS_SIGNED_URL_TTL_SECONDS
    response.set_cookie("hls_sig", sig, max_age=ttl, path="/hls", httponly=True, samesite="Lax")
    response.set_cookie("hls_exp", str(exp), max_age=ttl, path="/hls", httponly=True, samesite="Lax")
    return exp
