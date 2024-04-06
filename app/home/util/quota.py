from typing import List
from xmlrpc.client import Boolean
from django.db.models import Sum

from oauth.models import CustomUser
from home.models import Files
from settings.models import SiteSettings


def process_storage_quotas(user: CustomUser, size: int) -> List[bool]:
    settings = SiteSettings.objects.get(id=1)
    user_quota = False
    global_quota = False
    if user.get_remaining_quota_bytes() < size :
        user_quota = True
    if settings.get_remaining_global_storage_quota_bytes() < size:
        global_quota = True
    return [user_quota, global_quota]


def increment_user_storage(file: Files):
    # add new file to existing storage quota
    settings = SiteSettings.objects.get(id=1)
    user = file.user
    user.storage_usage += file.size // 1000000
    settings.global_storage_usage += file.size // 1000000
    user.save()
    settings.save()


def remove_file_storage(file: Files):
    user = file.user
    settings = SiteSettings.objects.get(id=1)
    user.storage_usage -= file.size // 1000000
    settings.global_storage_usage -= file.size // 1000000
    print(user.storage_usage)
    print(settings.global_storage_quota)
    # value should never be negative, guard against it, we should probably regen the usage values if this happens
    # if user.storage_usage < 0:
    #     user.storage_usage = 0
    # if settings.global_storage_usage < 0:
    #     settings.global_storage_usage = 0
    user.save()
    settings.save()


def generate_user_storage(user: CustomUser):
    # if user has files aggergate total usage and write to user field
    # this should only run in the case of a old user being migrated to the current version
    # of if we need to refresh storage ammount from scratch
    if len(files := Files.objects.filter(user=user)) > 0:
        user.storage_usage = (files.aggregate(Sum('size'))['size__sum'] // 1000000)
    else:
        user.storage_usage = 0
    user.save()


def generate_global_storage():
    # refresh global storage ammount from scratch
    settings = SiteSettings.objects.get(id=1)
    if len(files := Files.objects.all()) > 0:
        settings.global_storage_usage = (files.aggregate(Sum('size'))['size__sum'] // 1000000)
    else:
        settings.global_storage_usage = 0
    settings.save()
