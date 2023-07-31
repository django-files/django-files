import logging
import mimetypes
import os
import httpx
from celery import shared_task
from django.conf import settings
from django.core import management
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.template.loader import render_to_string

from .models import Files, Webhooks

logger = logging.getLogger('celery')


@shared_task()
def clear_sessions():
    # Cleanup session data for supported backends
    logger.info('clear_sessions')
    return management.call_command('clearsessions')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def flush_template_cache():
    # Flush template cache on request
    logger.info('flush_template_cache')
    return cache.delete_pattern('template.cache.*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_home_cache():
    # Clear Home cache on model update
    logger.info('clear_home_cache')
    # Not sure how to make fragment key with addition user key
    # return cache.delete(make_template_fragment_key('home_body'))
    return cache.delete_pattern('template.cache.home_body.*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_settings_cache():
    # Clear Settings cache on model update
    logger.info('clear_settings_cache')
    return cache.delete(make_template_fragment_key('settings_body'))


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 5, 'countdown': 5})
def process_file_upload(pk):
    # Process new file upload
    logger.info('process_file_upload: %s', pk)
    file = Files.objects.get(pk=pk)
    logger.debug(file)
    if file and file.file:
        file.name = os.path.basename(file.file.name)
        file.mime, _ = mimetypes.guess_type(file.file.path)
        file.size = file.file.size
        file.save()
        send_discord_message.delay(file.pk)
        return file.pk


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 5, 'countdown': 60}, rate_limit='10/m')
def send_discord_message(pk):
    # Send a Discord message for a new file
    logger.info('send_discord_message: pk: %s', pk)
    file = Files.objects.get(pk=pk)
    webhooks = Webhooks.objects.filter(owner=file.user)
    context = {'file': file}
    message = render_to_string('message/new-file.html', context)
    logger.info(message)
    for hook in webhooks:
        send_discord.delay(hook.id, message)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 5, 'countdown': 60}, rate_limit='10/m')
def send_success_message(hook_pk):
    # Send a success message for new webhook
    logger.info('send_success_message: %s', hook_pk)
    context = {'site_url': settings.SITE_URL}
    message = render_to_string('message/welcome.html', context)
    send_discord.delay(hook_pk, message)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 5, 'countdown': 60}, rate_limit='10/m')
def send_discord(hook_pk, message):
    logger.info('send_discord: %s', hook_pk)
    try:
        webhook = Webhooks.objects.get(pk=hook_pk)
        body = {'content': message}
        logger.info(body)
        r = httpx.post(webhook.url, json=body, timeout=30)
        if r.status_code == 404:
            logger.warning('Hook %s removed by owner %s',
                           webhook.hook_id, webhook.owner.username)
            webhook.delete()
            return 404

        if not r.is_success:
            logger.warning(r.content.decode(r.encoding))
            r.raise_for_status()

        return r.status_code

    except Exception as error:
        logger.exception(error)
        raise
