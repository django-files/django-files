from cryptography.hazmat.primitives import serialization
from django.core.cache import cache
from py_vapid import Vapid
from py_vapid.utils import b64urlencode, num_to_bytes
from settings.models import VAPIDKeys

_VAPID_CACHE_KEY = "vapid_keys_obj"


def get_or_create_vapid_keys():
    result = cache.get(_VAPID_CACHE_KEY)
    if result is not None:
        return result
    result = VAPIDKeys.objects.first()
    if not result:
        keys = get_vapid_keypair()
        result = VAPIDKeys.objects.create(
            public=keys["public"],
            private=keys["private"],
            email="noc@hosted-domains.com",
        )
    cache.set(_VAPID_CACHE_KEY, result)
    return result


def get_vapid_keypair():
    vapid = Vapid()
    vapid.generate_keys()

    pubkey_export = vapid.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    privkey_export = num_to_bytes(vapid.private_key.private_numbers().private_value, 32)

    return {
        "public": b64urlencode(pubkey_export),
        "private": b64urlencode(privkey_export),
    }
