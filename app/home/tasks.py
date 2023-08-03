import logging
import mimetypes
import os
import httpx
from celery import shared_task
# from django.conf import settings
from django.core import management
from django.core.cache import cache
# from django.core.cache.utils import make_template_fragment_key
from django.template.loader import render_to_string
from django.utils import timezone
from pytimeparse2 import parse

from .models import Files, Webhooks, SiteSettings

log = logging.getLogger('celery')


@shared_task()
def clear_sessions():
    # Cleanup session data for supported backends
    log.info('clear_sessions')
    return management.call_command('clearsessions')


# @shared_task()
# def process_stats():
#     # Process file stats
#     log.info('process_stats')
#     files = Files.objects.all()
#     _data = {'types': {}, 'size': 0, 'files': 0}
#     data = {'_totals': _data}
#     for file in files:
#         if file.user_id not in data:
#             data[file.user_id] = _data
#
#         data['_totals']['files'] += 1
#         data[file.user_id]['files'] += 1
#
#         data['_totals']['size'] += file.size
#         data[file.user_id]['size'] += file.size
#
#         if file.mime not in data['_totals']['types']:
#             data['_totals']['types'][file.mime] = 1
#         else:
#             data[file.user_id]['types'][file.mime] += 1
#
#         if file.mime not in data['_totals']['types']:
#             data[file.user_id]['types'][file.mime] = 1
#         else:
#             data[file.user_id]['types'][file.mime] += 1
#
#     log.info(data)


@shared_task()
def delete_expired_files():
    # Delete Expired Files
    log.info('delete_expired_files')
    files = Files.objects.all()
    now = timezone.now()
    count = 0
    for file in files:
        if parse(file.expr):
            delta = now - file.date
            if delta.seconds > parse(file.expr):
                log.info('Deleting expired file: %s', file.file.name)
                file.delete()
                count += 1
    return f'Deleted/Processed: {count}/{len(files)}'


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def flush_template_cache():
    # Flush template cache on request
    log.info('flush_template_cache')
    return cache.delete_pattern('template.cache.*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_files_cache():
    # Clear Files cache on model update
    log.info('clear_files_cache')
    # Not sure how to make fragment key with addition user key
    # return cache.delete(make_template_fragment_key('files_home'))
    return cache.delete_pattern('template.cache.files_*')


# @shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
# def clear_settings_cache():
#     # Clear Settings cache on model update
#     log.info('clear_settings_cache')
#     return cache.delete(make_template_fragment_key('settings_body'))


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 5, 'countdown': 5})
def process_file_upload(pk):
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
        file.size = file.file.size
        file.save()
        send_discord_message.delay(file.pk)
        return file.pk


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
    site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
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
