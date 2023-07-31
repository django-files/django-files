import random
import string
from django.contrib.auth.models import AbstractUser
from django.db import models


def rand_string(length=32):
    choices = (string.ascii_uppercase + string.ascii_lowercase + string.digits)
    return ''.join(random.choices(choices, k=length))


class CustomUser(AbstractUser):
    id = models.AutoField(primary_key=True)
    avatar_hash = models.CharField(null=True, blank=True, max_length=32)
    access_token = models.CharField(null=True, blank=True, max_length=32)
    refresh_token = models.CharField(null=True, blank=True, max_length=32)
    expires_in = models.DateTimeField(null=True, blank=True)
    authorization = models.CharField(default=rand_string, max_length=32)

    def __str__(self):
        return self.username
