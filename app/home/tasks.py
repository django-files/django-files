import datetime
import logging
import mimetypes
import os
import httpx
from celery import shared_task
# from django.conf import settings
# from django.core import management
from django.core.cache import cache
# from django.core.cache.utils import make_template_fragment_key
from django.template.loader import render_to_string
from django.utils import timezone
from itertools import count
from pytimeparse2 import parse
from PIL import Image

from .models import Files, Webhooks, SiteSettings, FileStats

log = logging.getLogger('celery')


# @shared_task()
# def clear_sessions():
#     # Cleanup session data for supported backends
#     log.info('clear_sessions')
#     return management.call_command('clearsessions')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def flush_template_cache():
    # Flush template cache on request
    log.info('flush_template_cache')
    return cache.delete_pattern('template.cache.*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_files_cache():
    # Clear Files cache on model update
    log.info('clear_files_cache')
    return cache.delete_pattern('template.cache.files_*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_shorts_cache():
    # Clear Files cache on model update
    log.info('clear_shorts_cache')
    return cache.delete_pattern('template.cache.shorts*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_stats_cache():
    # Clear Files cache on model update
    log.info('clear_stats_cache')
    return cache.delete_pattern('template.cache.stats*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_settings_cache():
    # Clear Settings cache on model update
    log.info('clear_settings_cache')
    return cache.delete_pattern('template.cache.settings*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 0, 'countdown': 5})
def process_file_upload(pk, strip_geo=False, strip_exif=False):
    # Process new file upload
    log.info('process_file_upload: %s', pk)
    file = Files.objects.get(pk=pk)
    log.info(file)
    log.info('-'*40)
    if file and file.file:
        file.name = os.path.basename(file.file.name)
        file.mime, _ = mimetypes.guess_type(file.file.path, strict=False)
        if not file.mime:
            file.mime, _ = mimetypes.guess_type(file.file.name, strict=False)
        exif = None
        file.size = file.file.size
        file.save()
        if file.mime in ['image/jpeg', 'image/png'] and (strip_geo or strip_exif):
            image = Image.open(file.file.path)
            if strip_exif:
                log.debug("Stripping EXIF metadata %s", pk)
                new = Image.new(image.mode, image.size)
                new.putdata(image.getdata())
                if 'P' in image.mode:
                    new.putpalette(image.getpalette())
                new.save(file.file.path)
            elif strip_geo:
                log.debug("Stripping EXIF GEO metadata %s", pk)
                exif = image.getexif()
                exif[0x8825] = None
                image.save(file.file.path, exif=exif)
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


@shared_task()
def process_stats():
    # Process file stats
    log.info('process_stats')
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

    for user_id, _data in data.items():
        _data['human_size'] = Files.get_size_of(_data['size'])
        log.info('user_id: %s', user_id)
        user_id = None if str(user_id) == '_totals' else user_id
        log.info('user_id: %s', user_id)
        log.info('_data.type: %s', type(_data))
        log.info('_data: %s', _data)
        stats = FileStats.objects.create(
            user_id=user_id,
            stats=_data,
        )
        log.info('stats.pk: %s', stats.pk)
    log.info(data)


@shared_task()
def cleanup_old_stats():
    # Delete Old Stats
    log.info('cleanup_old_stats')
    now = timezone.now()
    ft_filter = now - datetime.timedelta(days=1)
    file_stats = FileStats.objects.filter(created_at__gt=ft_filter)
    log.info('file_stats: %s', file_stats)
    extra_days = 10
    extra = 0
    for i in count(1):
        day = now - datetime.timedelta(days=i)
        stats = file_stats.filter(created_at__day=day.day)
        log.info('stats: %s', stats)
        if len(stats) > 1:
            log.info('--- process stats for day: %s', day.day)
            log.info(stats.first())
            all_but_last = stats.exclude(pk=stats.first().pk)
            log.info(all_but_last)
            all_but_last.delete()
            log.info('--- process stats for day: %s', day.day)
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
