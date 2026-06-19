import hashlib
import hmac

from django.conf import settings


def hash_token(plaintext: str) -> str:
    """Return HMAC-SHA256 hex digest of a plaintext token keyed with SECRET_KEY."""
    return hmac.new(
        settings.SECRET_KEY.encode(),
        plaintext.encode(),
        hashlib.sha256,
    ).hexdigest()
