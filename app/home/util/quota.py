from typing import List
from django.db.models import Sum, F

from oauth.models import CustomUser
from home.models import Files
from settings.models import SiteSettings


def process_storage_quotas(user: CustomUser, size: int) -> List[bool]:
    settings = SiteSettings.objects.get(id=1)
    user_quota = False
    global_quota = False
    if user.get_remaining_quota_bytes() < size:
        user_quota = True
    if settings.get_remaining_global_storage_quota_bytes() < size:
        global_quota = True
    return [user_quota, global_quota]


def increment_storage_usage(file: Files):
    # add new file to existing storage quota
    increase = (file.size // 1000000)
    SiteSettings.objects.filter(id=1).update(global_storage_usage=F('global_storage_usage') + increase)
    CustomUser.objects.filter(pk=file.user.pk).update(storage_usage=F('storage_usage') + increase)


def decrement_storage_usage(size: int, user_pk: int):
    print(f'[{ user_pk }]Bytes to remove from storage counter { size }')
    decrease = ((size // 1000000))
    print(f'TO BE REDUCED BY: { decrease }')
    CustomUser.objects.filter(pk=user_pk).update(storage_usage=F('storage_usage') - decrease)
    SiteSettings.objects.filter(pk=1).update(global_storage_usage=F('global_storage_usage') - decrease)


def regenerate_user_storage(user: CustomUser):
    if len(files := Files.objects.filter(user=user)) > 0:
        user.storage_usage = (files.aggregate(Sum('size'))['size__sum'] // 1000000)
    else:
        user.storage_usage = 0
    user.save()


def regenerate_global_storage():
    # refresh global storage ammount from scratch
    settings = SiteSettings.objects.get(id=1)
    if len(files := Files.objects.all()) > 0:
        settings.global_storage_usage = (files.aggregate(Sum('size'))['size__sum'] // 1000000)
    else:
        settings.global_storage_usage = 0
    settings.save()


def regenerate_all_storage_values():
    for user in CustomUser.objects.all():
        regenerate_user_storage(user)
    regenerate_global_storage()
