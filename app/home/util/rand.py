import random
import secrets
import string

_TOKEN_ALPHABET = string.ascii_uppercase + string.ascii_lowercase + string.digits


def rand_string(length=32):
    return "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(length))


def rand_color_hex(prefix: str = "#"):
    rgb = ""
    for _ in "RGB":
        i = random.randrange(0, 2**8)
        rgb += i.to_bytes(1, "big").hex()
    return f"{prefix or ''}{rgb}"
