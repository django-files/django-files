import datetime
import logging
import mimetypes
import os
import httpx
import json
from celery import shared_task
# from django.conf import settings
# from django.core import management
from django.core.cache import cache
# from django.core.cache.utils import make_template_fragment_key
from django.template.loader import render_to_string
from django.utils import timezone
from itertools import count
from pytimeparse2 import parse
from PIL import Image, ExifTags, TiffImagePlugin

from home.models import Files, Webhooks, SiteSettings, FileStats
from oauth.models import CustomUser

log = logging.getLogger('celery')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def flush_template_cache():
    # Flush all template cache on request
    log.info('flush_template_cache')
    return cache.delete_pattern('template.cache.*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_files_cache():
    # Clear Files cache
    log.info('clear_files_cache')
    return cache.delete_pattern('template.cache.files*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_shorts_cache():
    # Clear Shorts cache
    log.info('clear_shorts_cache')
    return cache.delete_pattern('template.cache.shorts*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_stats_cache():
    # Clear Stats cache
    log.info('clear_stats_cache')
    return cache.delete_pattern('template.cache.stats*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_settings_cache():
    # Clear Settings cache
    log.info('clear_settings_cache')
    return cache.delete_pattern('template.cache.settings*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 6, 'countdown': 5})
def process_file_upload(pk):
    # Process new file upload
    log.info('process_file_upload: %s', pk)
    file = Files.objects.get(pk=pk)
    log.info('-'*40)
    log.info('file: %s', file)
    log.info('file.file: %s', file.file)
    log.info('file.file.path: %s', file.file.path)
    log.info('-'*40)
    if not file or not file.file:
        return log.warning('WARNING NO FILE -- file or file.file is None --')
    file.name = os.path.basename(file.file.name)
    log.info('file.name: %s', file.name)
    file.mime, _ = mimetypes.guess_type(file.file.path, strict=False)
    if not file.mime:
        file.mime, _ = mimetypes.guess_type(file.file.name, strict=False)
    file.mime = file.mime or 'application/octet-stream'
    log.info('file.mime: %s', file.mime)
    file.size = file.file.size
    log.info('file.size: %s', file.size)
    if file.mime in ['image/jpeg', 'image/png']:
        image = Image.open(file.file.path)
        if file.user.remove_exif:
            log.debug("Stripping EXIF metadata %s", pk)
            new = Image.new(image.mode, image.size)
            new.putdata(image.getdata())
            if 'P' in image.mode:
                new.putpalette(image.getpalette())
            new.save(file.file.path)
        else:
            exif = image.getexif()
            log.debug("Parsing and storing EXIF metadata %s", pk)
            cleaned_exif = {
                ExifTags.TAGS[k]: v for k, v in exif.items()
                if k in ExifTags.TAGS and type(v) not in [bytes, TiffImagePlugin.IFDRational]
                }
            if file.user.remove_exif_geo:
                log.debug("Stripping EXIF GEO metadata %s", pk)
                exif[0x8825] = None
                image.save(file.file.path, exif=exif)
            else:
                cleaned_exif["GPSInfo"] = exif.get_ifd(ExifTags.IFD.GPSInfo)
            file.exif = json.dumps(cast(cleaned_exif))
    file.save()
    log.info('-'*40)
    send_discord_message.delay(file.pk)
    return file.pk


@shared_task()
def delete_expired_files():
    # Delete Expired Files
    log.info('delete_expired_files')
    files = Files.objects.all()
    now = timezone.now()
    i = 0
    for file in files:
        if parse(file.expr):
            delta = now - file.date
            if delta.seconds > parse(file.expr):
                log.info('Deleting expired file: %s', file.file.name)
                file.delete()
                i += 1
    return f'Deleted/Processed: {i}/{len(files)}'


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 30})
def process_stats():
    # Process file stats
    log.info('----- START process_stats -----')
    now = timezone.now()
    files = Files.objects.all()
    data = {'_totals': {'types': {}, 'size': 0, 'count': 0}}
    for file in files:
        if file.user_id not in data:
            data[file.user_id] = {'types': {}, 'size': 0, 'count': 0}

        data['_totals']['count'] += 1
        data[file.user_id]['count'] += 1

        data['_totals']['size'] += file.size
        data[file.user_id]['size'] += file.size

        if file.mime in data['_totals']['types']:
            data['_totals']['types'][file.mime]['count'] += 1
            data['_totals']['types'][file.mime]['size'] += file.size
        else:
            data['_totals']['types'][file.mime] = {'size': file.size, 'count': 1}

        if file.mime in data[file.user_id]['types']:
            data[file.user_id]['types'][file.mime]['count'] += 1
            data[file.user_id]['types'][file.mime]['size'] += file.size
        else:
            data[file.user_id]['types'][file.mime] = {'size': file.size, 'count': 1}

    users = CustomUser.objects.all()
    for user in users:
        if user.id not in data:
            data[user.id] = {'types': {}, 'size': 0, 'count': 0}

    for user_id, _data in data.items():
        _data['human_size'] = Files.get_size_of(_data['size'])
        log.info('user_id: %s', user_id)
        user_id = None if str(user_id) == '_totals' else user_id
        log.info('user_id: %s', user_id)
        log.info('_data: %s', _data)
        stats = FileStats.objects.filter(user_id=user_id, created_at__day=now.day)
        if stats:
            stats = stats[0]
            stats.stats = _data
            stats.save()
        else:
            stats = FileStats.objects.create(
                user_id=user_id,
                stats=_data,
            )
        log.info('stats.pk: %s', stats.pk)
    log.info('----- END process_stats -----')
    log.info(data)


@shared_task()
def cleanup_old_stats():
    # Delete Old Stats
    # TODO: DEPRECATED: To be removed
    log.info('cleanup_old_stats')
    now = timezone.now()
    # ft_filter = now - datetime.timedelta(days=1)
    # file_stats = FileStats.objects.filter(created_at__lt=ft_filter)
    file_stats = FileStats.objects.all()
    log.info('file_stats: %s', file_stats)
    extra_days = 10
    users = CustomUser.objects.all()
    # users = CustomUser.objects.all().values_list('id', flat=True)
    id_list = [user.id for user in users] + [0]
    for user_id in id_list:
        extra = 0
        log.info('-'*40)
        log.info('user_id: %s', user_id)
        for i in count(0):
            day = now - datetime.timedelta(days=i)
            day_stats = file_stats.filter(created_at__day=day.day)
            # log.info('day_stats: %s', day_stats)
            stats = day_stats.filter(user_id=user_id or None)
            # log.info('stats: %s', stats)
            if len(stats) > 1:
                log.info('--- start process stats for day -- %s --', day.day)
                all_but_last = stats.exclude(pk=stats.first().pk)
                log.info('all_but_last: %s', all_but_last)
                all_but_last.delete()
            else:
                extra += 1
                log.info('extra: %s, day: %s', extra, day.day)
            if extra >= extra_days:
                break


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 5, 'countdown': 60}, rate_limit='10/m')
def send_discord_message(pk):
    # Send a Discord message for a new file
    log.info('send_discord_message: pk: %s', pk)
    file = Files.objects.get(pk=pk)
    webhooks = Webhooks.objects.filter(owner=file.user)
    context = {'file': file}
    message = render_to_string('message/new-file.html', context)
    log.info(message)
    for hook in webhooks:
        send_discord.delay(hook.id, message)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 5, 'countdown': 60}, rate_limit='10/m')
def send_success_message(hook_pk):
    # Send a success message for new webhook
    site_settings = SiteSettings.objects.get(pk=1)
    log.info('send_success_message: %s', hook_pk)
    context = {'site_url': site_settings.site_url}
    message = render_to_string('message/welcome.html', context)
    send_discord.delay(hook_pk, message)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 5, 'countdown': 60}, rate_limit='10/m')
def send_discord(hook_pk, message):
    log.info('send_discord: %s', hook_pk)
    try:
        webhook = Webhooks.objects.get(pk=hook_pk)
        body = {'content': message}
        log.info(body)
        r = httpx.post(webhook.url, json=body, timeout=30)
        if r.status_code == 404:
            log.warning('Hook %s removed by owner %s', webhook.hook_id, webhook.owner.username)
            webhook.delete()
            return 404
        if not r.is_success:
            log.warning(r.content.decode(r.encoding))
            r.raise_for_status()
        return r.status_code
    except Exception as error:
        log.exception(error)
        raise


def cast(v):
    if isinstance(v, TiffImagePlugin.IFDRational):
        return float(v)
    elif isinstance(v, tuple):
        return tuple(cast(t) for t in v)
    elif isinstance(v, bytes):
        return v.decode(errors="replace")
    elif isinstance(v, dict):
        for kk, vv in v.items():
            v[kk] = cast(vv)
        return v
    else:
        return v
