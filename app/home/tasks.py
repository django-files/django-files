import logging
import os
import httpx
import json
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.forms.models import model_to_dict
from django.template.loader import render_to_string
from django.utils import timezone
from packaging import version
from pytimeparse2 import parse
from PIL import UnidentifiedImageError

from home.util.storage import use_s3
from home.util.image import thumbnail_processor
from home.models import Files, FileStats, ShortURLs
from home.util.quota import regenerate_all_storage_values
from oauth.models import CustomUser
from settings.models import SiteSettings
from oauth.models import DiscordWebhooks
from django_celery_beat import models

log = logging.getLogger('app')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 10, 'countdown': 1})
def app_init():
    # App Init Task - Only Runs on First Startup, then is Disabled
    log.info('app_init')

    # site_settings = SiteSettings.objects.settings()
    # if settings.SITE_URL:
    #     log.info('site_settings.site_url updated')
    #     site_settings.site_url = settings.SITE_URL
    #     site_settings.save()

    username = os.environ.get('USERNAME', 'admin')
    password = os.environ.get('PASSWORD', '12345')
    local = bool(os.environ.get('USERNAME') and os.environ.get('PASSWORD'))
    oauth = bool(os.environ.get('OAUTH_REDIRECT_URL'))
    if not oauth or local:
        CustomUser.objects.create_superuser(username=username, password=password)
        log.info('Initial User Created')
        log.info(f'Username: {username}')
        log.info(f'Password: {password}')
    return 'app_init - finished'

    # public_user, created = CustomUser.objects.get_or_create(username='public')
    # if created:
    #     log.info('public_user created: public')
    # else:
    #     log.warning('public_user already created: public')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60, "default_retry_delay": 180})
def generate_thumbs(user_pk: int = None, only_missing: bool = True):
    log.info("Generating Thumbnails - only_missing: %s - user_pk: %s", only_missing,  user_pk)
    users = CustomUser.objects.filter(pk=user_pk) if user_pk else CustomUser.objects.all()
    if only_missing:
        files = Files.objects.filter(thumb=None, user__in=users, mime__startswith='image/')
    else:
        files = Files.objects.filters(user__in=users, mime__startswith='image')
    log.info("Processing thumbnails for %d objects: %s", len(files), files)
    for file in files:
        log.info("Generating thumbnail for: %s", file.name)
        try:
            thumbnail_processor(file)
        except (ValueError, UnidentifiedImageError):
            # if we hit a file that cannot be processed ignore and continue
            log.error("Unable to process thumbnail for %s", file.name)
            continue


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def app_startup():
    log.info('app_startup')
    # Ensure SiteSettings model
    site_settings = SiteSettings.objects.settings()
    # Queue Version Check
    version_check.apply_async(countdown=5)
    # Flush template cache
    cache.delete_pattern('*.decorators.cache.*')
    log.info('Flushed Template Cache')
    # Warm site_settings cache
    cache.set('site_settings', model_to_dict(site_settings))
    log.info('Created Cache: site_settings')
    # Ensure USERNAME and PASSWORD are set
    if bool(os.environ.get('USERNAME') and os.environ.get('PASSWORD')):
        users = CustomUser.objects.all()
        if user := users.filter(username=os.environ.get('USERNAME')):
            user[0].set_password(os.environ.get('PASSWORD'))
            log.info('Password Ensured for user: %s', user[0].username)
        else:
            user = CustomUser.objects.create_superuser(
                username=os.environ.get('USERNAME'),
                password=os.environ.get('PASSWORD'),
            )
            log.info('Custom User Created: %s', user.username)
    regenerate_all_storage_values()
    return 'app_startup - finished'


@shared_task()
def version_check():
    log.info('version_check')
    app_version = os.environ.get('APP_VERSION')
    if not app_version or app_version.lower() in ['dev', 'latest']:
        return 'Skipping Version Check due to APP_VERSION not set or invalid.'
    app_version = version.parse(app_version)
    log.info('app_version: %s', app_version)
    r = httpx.head(settings.VERSION_CHECK_URL, timeout=10)
    if r.status_code != 302:
        return 'Error: Version Check URL Response did not return a 302.'
    log.info('location: %s', r.headers['location'])
    latest_version = version.parse(os.path.basename(r.headers['location']))
    log.info('latest_version: %s', latest_version)
    site_settings = SiteSettings.objects.settings()
    log.info('site_settings.latest_version: %s', site_settings.latest_version)
    if latest_version > app_version:
        if str(latest_version) != site_settings.latest_version:
            site_settings.latest_version = str(latest_version)
            site_settings.save()
            return f'New Update Found. Setting version to: {latest_version}'
        return f'New Update already set. latest_version: {latest_version}'
    else:
        if site_settings.latest_version:
            site_settings.latest_version = ''
            site_settings.save()
            return f'App Updated. Clearing latest_version: {latest_version}'
        return f'No Update Available. Current Version: {app_version}'


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 300})
def app_cleanup():
    # App Cleanup Task
    log.info('app_cleanup')
    with open(settings.NGINX_ACCESS_LOGS, 'a') as f:
        f.truncate(0)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def flush_template_cache():
    # Flush all template cache on request
    log.info('flush_template_cache')
    return cache.delete_pattern('*.decorators.cache.*') + cache.delete_pattern('*.urlcache.*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_files_cache():
    # Clear Files cache
    log.info('clear_files_cache')
    return cache.delete_pattern('*.files.*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_shorts_cache():
    # Clear Shorts cache
    log.info('clear_shorts_cache')
    return cache.delete_pattern('*.shorts.*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def clear_stats_cache():
    # Clear Stats cache
    log.info('clear_stats_cache')
    return cache.delete_pattern('*.stats.*')


# @shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
# def clear_settings_cache():
#     # Clear Settings cache
#     log.info('clear_settings_cache')
#     return cache.delete_pattern('*.settings.*')


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 30})
def refresh_gallery_static_urls_cache():
    # Refresh cached gallery files to handle case where url signing expired
    log.info('----- START gallery cache refresh -----')
    if use_s3:
        files = Files.objects.all()
        for file in files:
            cache.delete(f'file.urlcache.gallery.{file.pk}')
            file.get_gallery_url()
    log.info('----- COMPLETE gallery cache refresh -----')


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
    data = {'_totals': {'types': {}, 'size': 0, 'count': 0, 'shorts': 0}}
    for file in files:
        if file.user_id not in data:
            data[file.user_id] = {'types': {}, 'size': 0, 'count': 0, 'shorts': 0}

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

    shorts = ShortURLs.objects.all()
    users = CustomUser.objects.all()
    for user in users:
        s = shorts.filter(user=user)
        if user.id not in data:
            data[user.id] = {'types': {}, 'size': 0, 'count': 0, 'shorts': len(s)}
        else:
            data[user.id]['shorts'] = len(s)

    for user_id, _data in data.items():
        # TODO: Look into type warning on next line
        _data['human_size'] = Files.get_size_of(_data['size'])
        log.info('user_id: %s', user_id)
        user_id = None if str(user_id) == '_totals' else user_id
        log.info('user_id: %s', user_id)
        log.info('_data: %s', _data)
        stats = FileStats.objects.filter(user_id=user_id, created_at__date=now)
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
    log.info(data)
    log.info('----- END process_stats -----')


@shared_task()
def new_file_websocket(pk):
    log.debug('new_file_websocket: %s', pk)
    file = Files.objects.get(pk=pk)
    log.debug('file: %s', file)
    data = model_to_dict(file, exclude=['file', 'info', 'exif', 'date', 'edit', 'meta'])
    log.debug('data: %s', data)
    # TODO: Backwards Compatibility
    data['pk'] = pk
    data['event'] = 'file-new'
    channel_layer = get_channel_layer()
    event = {
        'type': 'websocket.send',
        'text': json.dumps(data),
    }
    log.debug('event: %s', event)
    async_to_sync(channel_layer.group_send)(f'user-{file.user_id}', event)


@shared_task()
def delete_file_websocket(data: dict, user_id):
    log.debug('delete_file_websocket')
    log.debug('data: %s', data)
    log.debug('delete_file_websocket pk: %s user_id: %s', data['id'], user_id)
    data['event'] = 'file-delete'
    data['pk'] = data['id']
    channel_layer = get_channel_layer()
    event = {
        'type': 'websocket.send',
        'text': json.dumps(data),
    }
    async_to_sync(channel_layer.group_send)(f'user-{user_id}', event)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 6, 'countdown': 30})
def send_discord_message(pk):
    # Send a Discord message for a new file
    log.info('send_discord_message: pk: %s', pk)
    file = Files.objects.filter(pk=pk)
    if not file:
        log.warning('send_discord_message: 404 File Not Found - pk: %s', pk)
        return f'404 File Not Found - pk: {pk}'
    file = file[0]
    webhooks = DiscordWebhooks.objects.filter(owner=file.user)
    context = {'file': file}
    message = render_to_string('message/new-file.html', context)
    log.info(message)
    for hook in webhooks:
        send_discord.delay(hook.id, message)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 6, 'countdown': 30})
def send_success_message(hook_pk):
    # Send a success message for new webhook
    site_settings = SiteSettings.objects.settings()
    log.info('send_success_message: %s', hook_pk)
    context = {'site_url': site_settings.site_url}
    message = render_to_string('message/welcome.html', context)
    send_discord.delay(hook_pk, message)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 6, 'countdown': 30})
def cleanup_vector_tasks():
    models.PeriodicTask.objects.get(name="process_vector_stats").delete()


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 5, 'countdown': 60}, rate_limit='10/m')
def send_discord(hook_pk, message):
    log.info('send_discord: %s', hook_pk)
    try:
        webhook = DiscordWebhooks.objects.get(pk=hook_pk)
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
