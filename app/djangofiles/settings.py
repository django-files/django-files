import datetime
import sentry_sdk
import sys
from celery.schedules import crontab
from decouple import config, Csv
from dotenv import find_dotenv, load_dotenv
from django.contrib.messages import constants as message_constants
from pathlib import Path
from sentry_sdk.integrations.django import DjangoIntegration

VERSION_CHECK_URL = config('VERSION_CHECK_URL', 'https://github.com/django-files/django-files/releases/latest')

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = config('DEBUG', False, bool)
print(f'DEBUG: {DEBUG}')

BUILD_SHA = config('BUILD_SHA', '')
APP_VERSION = config('APP_VERSION', f'DEV:{BUILD_SHA[:7]}')

# determine which env file to use
if 'test' in sys.argv or 'test_coverage' in sys.argv:
    dotenv_path = find_dotenv('test.env', usecwd=True)
    print(f'TEST dotenv_path: {dotenv_path}')
    env = load_dotenv(dotenv_path=dotenv_path)
    print(f'TEST env: {env}')
else:
    dotenv_path = find_dotenv('settings.env', usecwd=True) or find_dotenv(usecwd=True)
    print(f'dotenv_path: {dotenv_path}')
    env = load_dotenv(dotenv_path=dotenv_path)
    print(f'env: {env}')

# determine database type and location
database_type = config('DATABASE_TYPE', 'sqlite3')
print(f'database_type: {database_type}')
db_location = config('DATABASE_LOCATION', '/data/media/db/database.sqlite3')
print(f'db_location: {db_location}')

# read secret key from file
if Path('/data/media/db/secret.key').exists():
    print('Loading SECRET_KEY from file: /data/media/db/secret.key')
    with open('/data/media/db/secret.key') as f:
        SECRET_KEY = f.read().strip()
else:
    print('Loading SECRET_KEY from environment variable: SECRET or SECRET_KEY')
    SECRET_KEY = config('SECRET', None) or config('SECRET_KEY')

# TODO: Do Not Echo Secret Key
print(f'SECRET_KEY: {SECRET_KEY}')

SITE_URL = config('SITE_URL', None)
print(f'SITE_URL: {SITE_URL}')

ALLOWED_HOSTS = config('ALLOWED_HOSTS', '*', Csv())
SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', 3600 * 24 * 14, int)

ASGI_APPLICATION = 'djangofiles.asgi.application'
ROOT_URLCONF = 'djangofiles.urls'
AUTH_USER_MODEL = 'oauth.CustomUser'

LOGIN_REDIRECT_URL = '/'
LOGIN_URL = '/oauth/'
STATIC_URL = '/static/'
MEDIA_URL = '/r/'
STATIC_ROOT = config('STATIC_ROOT', '/data/static')
MEDIA_ROOT = config('MEDIA_ROOT', '/data/media/files')
STATICFILES_DIRS = [BASE_DIR / 'static']
TEMPLATES_DIRS = [BASE_DIR / 'templates']

LANGUAGE_CODE = config('LANGUAGE_CODE', 'en-us')
TIME_ZONE = config('TZ', 'UTC')
USE_TZ = True
USE_I18N = True
USE_L10N = True

CELERY_BROKER_URL = config('CELERY_BROKER_URL', 'redis://redis:6379/1')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', 'redis://redis:6379/1')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = config('TZ', 'UTC')

DJANGO_REDIS_IGNORE_EXCEPTIONS = config('REDIS_IGNORE_EXCEPTIONS', True, bool)
USE_X_FORWARDED_HOST = config('USE_X_FORWARDED_HOST', False, bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
X_FRAME_OPTIONS = 'SAMEORIGIN'

AWS_S3_FILE_OVERWRITE = config('AWS_S3_FILE_OVERWRITE', False, bool)
STATIC_QUERYSTRING_EXPIRE = config('STATIC_QUERYSTRING_EXPIRE', 14400, int)
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', None)
AWS_S3_REGION_NAME = config('AWS_REGION_NAME', None)
AWS_S3_CDN_URL = config('AWS_S3_CDN_URL', None)

CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', True, bool)
NGINX_ACCESS_LOGS = config('NGINX_ACCESS_LOGS', '/logs/nginx.access')

# CACHE_MIDDLEWARE_SECONDS = 0
# CSRF_TRUSTED_ORIGINS = config('CSRF_ORIGINS', '', Csv())
# SECURE_REFERRER_POLICY = config('SECURE_REFERRER_POLICY', 'no-referrer')

MESSAGE_TAGS = {
    message_constants.DEBUG: 'secondary',
    message_constants.INFO: 'primary',
    message_constants.SUCCESS: 'success',
    message_constants.WARNING: 'warning',
    message_constants.ERROR: 'danger',
}

CORS_ALLOW_HEADERS = (
    'accept',
    'authorization',
    'content-type',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'format',
    'expr',
    'info',
)

CELERY_BEAT_SCHEDULE = {
    'app_init': {
        'task': 'home.tasks.app_init',
        'schedule': datetime.timedelta(seconds=1),
        'one_off': True,
    },
    'generate_thumbs': {
        'task': 'home.tasks.generate_thumbs',
        'schedule': datetime.timedelta(seconds=1),
        'one_off': True,
    },
    'app_cleanup': {
        'task': 'home.tasks.app_cleanup',
        'schedule': datetime.timedelta(hours=config('APP_CLEANUP_HOUR', 1, int)),
    },
    'version_check': {
        'task': 'home.tasks.version_check',
        'schedule': datetime.timedelta(hours=config('VERSION_CHECK_HOUR', 8, int)),
    },
    'delete_expired_files': {
        'task': 'home.tasks.delete_expired_files',
        'schedule': datetime.timedelta(minutes=config('DELETE_EXPIRED_MIN', 15, int)),
    },
    'process_stats': {
        'task': 'home.tasks.process_stats',
        'schedule': datetime.timedelta(minutes=config('PROCESS_STATS_MIN', 15, int)),
    },
    'refresh_gallery_static_urls_cache': {
        'task': 'home.tasks.refresh_gallery_static_urls_cache',
        'schedule': crontab(minute='0', hour='9,21')
    },
    'cleanup_vector_tasks': {
        'task': 'home.tasks.cleanup_vector_tasks',
        'schedule': datetime.timedelta(seconds=1),
        'one_off': True
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('redis', 6379)],
        },
    },
}

CACHES = {
    'default': {
        'BACKEND': config('CACHE_BACKEND', 'django_redis.cache.RedisCache'),
        'LOCATION': config('CACHE_LOCATION', 'redis://redis:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    },
}

if database_type == 'sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': db_location,
        }
    }
elif database_type == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('DATABASE_NAME'),
            'USER': config('DATABASE_USER'),
            'PASSWORD': config('DATABASE_PASS'),
            'HOST': config('DATABASE_HOST'),
            'PORT': config('DATABASE_PORT', '3306'),
            'OPTIONS': {
                'isolation_level': 'repeatable read',
                'init_command': "SET sql_mode='STRICT_ALL_TABLES'",
            },
        },
    }
elif database_type == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DATABASE_NAME'),
            'USER': config('DATABASE_USER'),
            'PASSWORD': config('DATABASE_PASS'),
            'HOST': config('DATABASE_HOST'),
            'PORT': config('DATABASE_PORT', '5432'),
            'OPTIONS': {
            },
        },
    }
else:
    raise ValueError(f'Unknown DATABASE_TYPE: {database_type}')

INSTALLED_APPS = [
    'channels',
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_beat',
    'home',
    'oauth',
    'settings',
]
if DEBUG:
    INSTALLED_APPS.insert(0, 'daphne')
    INSTALLED_APPS += [
        'django_extensions',
        'debug_toolbar',
    ]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 'settings.middleware.TimezoneMiddleware',
]
if DEBUG:
    MIDDLEWARE += [
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    ]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': TEMPLATES_DIRS,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.media',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.static',
                'settings.context_processors.site_settings_processor'
            ],
        },
    },
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': ('%(asctime)s - '
                       '%(levelname)s - '
                       '%(filename)s '
                       '%(module)s.%(funcName)s:%(lineno)d - '
                       '%(message)s'),
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': config('DJANGO_LOG_LEVEL', 'WARNING'),
            'propagate': True,
        },
        'app': {
            'handlers': ['console'],
            'level': config('APP_LOG_LEVEL', 'INFO'),
            'propagate': True,
        },
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

if config('SENTRY_URL', False):
    sentry_sdk.init(
        dsn=config('SENTRY_URL'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=config('SENTRY_SAMPLE_RATE', 0.25, float),
        send_default_pii=True,
        debug=config('SENTRY_DEBUG', config('DEBUG', 'False'), bool),
        environment=config('SENTRY_ENVIRONMENT', None),
    )

if DEBUG:
    def show_toolbar(request):
        if config('DISABLE_DEBUG_TOOLBAR', False, bool):
            return False
        return True if request.user.is_superuser else False

    DEBUG_TOOLBAR_CONFIG = {'SHOW_TOOLBAR_CALLBACK': show_toolbar}
    DEBUG_TOOLBAR_PANELS = [
        'debug_toolbar.panels.versions.VersionsPanel',
        'debug_toolbar.panels.timer.TimerPanel',
        'debug_toolbar.panels.settings.SettingsPanel',
        'debug_toolbar.panels.headers.HeadersPanel',
        'debug_toolbar.panels.request.RequestPanel',
        'debug_toolbar.panels.sql.SQLPanel',
        'debug_toolbar.panels.staticfiles.StaticFilesPanel',
        'debug_toolbar.panels.templates.TemplatesPanel',
        'debug_toolbar.panels.cache.CachePanel',
        'debug_toolbar.panels.signals.SignalsPanel',
        'debug_toolbar.panels.logging.LoggingPanel',
        'debug_toolbar.panels.redirects.RedirectsPanel',
    ]
