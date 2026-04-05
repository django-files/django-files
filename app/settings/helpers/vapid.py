import logging

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from py_vapid.utils import b64urlencode, num_to_bytes
from settings.models import VAPIDKeys


log = logging.getLogger("app")


def get_or_create_vapid_keys():
    result = VAPIDKeys.objects.first()
    log.debug("get_or_create_vapid_keys: result: %s", result)
    if result:
        return result
    keys = get_vapid_keypair()
    log.debug("get_or_create_vapid_keys: keys: %s", keys)
    return VAPIDKeys.objects.create(
        public=keys["public"],
        private=keys["private"],
        email="noc@hosted-domains.com",
    )


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
