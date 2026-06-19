import hashlib
import hmac

from django.conf import settings
from home.util.rand import rand_string

try:
    import user_agents
except ImportError:
    user_agents = None


def hash_token(plaintext: str) -> str:
    """Return HMAC-SHA256 hex digest of a plaintext token keyed with SECRET_KEY."""
    return hmac.new(
        settings.SECRET_KEY.encode(),
        plaintext.encode(),
        hashlib.sha256,
    ).hexdigest()


def _client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


_UNKNOWN_DEVICE = "Unknown Device"


def _infer_device_name(ua_string: str) -> str:
    """Return a human-readable device/browser label from a User-Agent string."""
    if not ua_string:
        return _UNKNOWN_DEVICE
    if user_agents is None:
        return ua_string[:50]
    ua = user_agents.parse(ua_string)
    if ua.is_mobile:
        return f"Django Files {ua.os.family} {ua.os.version_string}".strip()
    if ua.browser.family and ua.browser.family != "Other":
        return f"{ua.browser.family} / {ua.os.family}".strip()
    return ua.device.family or _UNKNOWN_DEVICE


def create_api_token(user, request=None, name="", expires_at=None) -> str:
    """
    Insert a new ApiToken row. Returns plaintext token (shown once to caller).
    Does NOT touch any other token belonging to this user.
    Optionally writes plaintext to request.session['api_token'] for web flows.
    """
    from oauth.models import ApiToken  # avoid circular import

    plaintext = rand_string()
    ip = _client_ip(request) if request else None
    ua = request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""
    ApiToken.objects.create(
        user=user,
        token_hash=hash_token(plaintext),
        name=name or _infer_device_name(ua),
        created_ip=ip,
        user_agent=ua,
        expires_at=expires_at,
    )
    if request is not None and hasattr(request, "session"):
        request.session["api_token"] = plaintext
    return plaintext
