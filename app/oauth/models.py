import random
import string
from django.contrib.auth.models import AbstractUser
from django.db import models


def rand_string(length=32):
    choices = (string.ascii_uppercase + string.ascii_lowercase + string.digits)
    return ''.join(random.choices(choices, k=length))


def rand_color_hex():
    # TODO: Add distinctipy
    colors = ['483D8B', '8A2BE2', 'DC143C', '9932CC', '228B22', 'ADFF2F']
    return random.choice(colors).lower()


# def rand_color_hex():
#     rgb = ""
#     for _ in "RGB":
#         i = random.randrange(0, 2**8)
#         rgb += i.to_bytes(1, "big").hex()
#     return rgb


class CustomUser(AbstractUser):
    id = models.AutoField(primary_key=True)
    avatar_hash = models.CharField(null=True, blank=True, max_length=32)
    access_token = models.CharField(null=True, blank=True, max_length=32)
    refresh_token = models.CharField(null=True, blank=True, max_length=32)
    expires_in = models.DateTimeField(null=True, blank=True)
    authorization = models.CharField(default=rand_string, max_length=32)
    default_color = models.CharField(default=rand_color_hex, max_length=6)
    default_expire = models.CharField(default='', max_length=32)

    def __str__(self):
        return self.username
