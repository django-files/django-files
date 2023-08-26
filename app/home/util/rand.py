import random
import string


def rand_string(length=32):
    choices = (string.ascii_uppercase + string.ascii_lowercase + string.digits)
    return ''.join(random.choices(choices, k=length))


def rand_color_hex(prefix: str = '#'):
    rgb = ""
    for _ in "RGB":
        i = random.randrange(0, 2**8)
        rgb += i.to_bytes(1, "big").hex()
    return f'{prefix or ""}{rgb}'
