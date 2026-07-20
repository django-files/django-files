import datetime
import os
import sys
from pathlib import Path

import sentry_sdk
from asgiref.sync import sync_to_async
from celery.schedules import crontab
from decouple import Csv, config
from django.contrib.messages import constants as message_constants
from djangofiles.sysinfo import cgroup_memory_limit, parse_size
from dotenv import find_dotenv, load_dotenv
from sentry_sdk.integrations.django import DjangoIntegration

BASE_DIR = Path(__file__).resolve().parent.parent

if "test" in sys.argv or "test_coverage" in sys.argv:
    dotenv_path = find_dotenv("test.env", usecwd=True)
    print(f"TEST dotenv_path: {dotenv_path}")
    env = load_dotenv(dotenv_path=dotenv_path)
    print(f"TEST env: {env}")
else:
    dotenv_path = find_dotenv("settings.env", usecwd=True) or find_dotenv(usecwd=True)
    print(f"dotenv_path: {dotenv_path}")
    env = load_dotenv(dotenv_path=dotenv_path)
    print(f"env: {env}")

VERSION_CHECK_URL = config("VERSION_CHECK_URL", "https://github.com/django-files/django-files/releases/latest")

DEBUG = config("DEBUG", False, bool)
print(f"DEBUG: {DEBUG}")

BUILD_SHA = config("BUILD_SHA", "")
APP_VERSION = config("APP_VERSION", f"DEV:{BUILD_SHA[:7] or 'source'}")

# determine database type and location
database_type = config("DATABASE_TYPE", "sqlite3")
print(f"database_type: {database_type}")
db_location = config("DATABASE_LOCATION", "/data/media/db/database.sqlite3")
print(f"db_location: {db_location}")

# read secret key from file
if Path("/data/media/db/secret.key").exists():
    print("Loading SECRET_KEY from file: /data/media/db/secret.key")
    with open("/data/media/db/secret.key") as f:
        SECRET_KEY = f.read().strip()
else:
    print("Loading SECRET_KEY from environment variable: SECRET or SECRET_KEY")
    SECRET_KEY = config("SECRET", None) or config("SECRET_KEY")


SITE_URL = config("SITE_URL", None)
print(f"SITE_URL: {SITE_URL}")

RTMP_HOST = config("RTMP_HOST", "")
print(f"RTMP_HOST: {RTMP_HOST}")

RTMP_PORT = config("RTMP_PORT", 1935, int)
print(f"RTMP_PORT: {RTMP_PORT}")

ALLOWED_HOSTS = config("ALLOWED_HOSTS", "*", Csv())
SESSION_COOKIE_AGE = config("SESSION_COOKIE_AGE", 3600 * 24 * 7 * 4, int)
SESSION_MOBILE_AGE = config("SESSION_MOBILE_AGE", 3600 * 24 * 7 * 26, int)

ASGI_APPLICATION = "djangofiles.asgi.application"
ROOT_URLCONF = "djangofiles.urls"
AUTH_USER_MODEL = "oauth.CustomUser"

LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/oauth/"
STATIC_URL = "/static/"
MEDIA_URL = "/r/"
STATIC_ROOT = config("STATIC_ROOT", "/data/static")
MEDIA_ROOT = config("MEDIA_ROOT", "/data/media/files")
STATICFILES_DIRS = [BASE_DIR / "static"]
TEMPLATES_DIRS = [BASE_DIR / "templates"]

LANGUAGE_CODE = config("LANGUAGE_CODE", "en-us")
TIME_ZONE = config("TZ", "UTC")
USE_TZ = True
USE_I18N = True

CELERY_BROKER_URL = config("CELERY_BROKER_URL", "redis://redis:6379/1")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = config("TZ", "UTC")
# File processing (image/video decode, storage copy) scales with whatever a
# user uploads, not something we control per-task. These bound the blast
# radius instead: a worker child is recycled once it has held onto this much
# RSS (catches slow leaks/fragmentation across many tasks, not just one big
# one), and any single task is killed outright if it runs unreasonably long
# (a stuck ffmpeg decode on a malformed file, a stalled disk write, etc.)
# rather than parking a worker slot forever. See docs/resource-sizing.md.
CELERY_WORKER_MAX_MEMORY_PER_CHILD = config("CELERY_WORKER_MAX_MEMORY_PER_CHILD_KB", 1_048_576, int)
CELERY_TASK_SOFT_TIME_LIMIT = config("CELERY_TASK_SOFT_TIME_LIMIT", 1500, int)
CELERY_TASK_TIME_LIMIT = config("CELERY_TASK_TIME_LIMIT", 1800, int)

DJANGO_REDIS_IGNORE_EXCEPTIONS = config("REDIS_IGNORE_EXCEPTIONS", True, bool)
USE_X_FORWARDED_HOST = config("USE_X_FORWARDED_HOST", False, bool)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

_raw_trusted_proxies = config("TRUSTED_PROXIES", "", Csv())
TRUSTED_PROXIES = (
    [_raw_trusted_proxies]
    if isinstance(_raw_trusted_proxies, str) and _raw_trusted_proxies
    else list(_raw_trusted_proxies)
)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
X_FRAME_OPTIONS = "SAMEORIGIN"

AWS_S3_FILE_OVERWRITE = config("AWS_S3_FILE_OVERWRITE", False, bool)
# Signing TTLs (seconds). Split by URL purpose so we can keep gallery views fresh,
# limit blast radius on download links, and keep OG/social-card URLs alive long
# enough for scrapers (Discord, Slack, etc.) that cache them for hours.
SIGNED_URL_TTL_SECONDS = config("SIGNED_URL_TTL_SECONDS", 14400, int)
SIGNED_DOWNLOAD_URL_TTL_SECONDS = config("SIGNED_DOWNLOAD_URL_TTL_SECONDS", 900, int)
SIGNED_META_URL_TTL_SECONDS = config("SIGNED_META_URL_TTL_SECONDS", 86400, int)
# TTL for HLS access cookies (manifest + segment fetches for a single viewing session).
HLS_SIGNED_URL_TTL_SECONDS = config("HLS_SIGNED_URL_TTL_SECONDS", 21600, int)
# Fraction of the signing TTL we keep a generated URL in the server-side cache,
# so any cached URL we serve still has >= (1 - ratio) of its signing window left.
SIGNED_URL_REFRESH_RATIO = config("SIGNED_URL_REFRESH_RATIO", 0.5, float)
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", None)
AWS_S3_REGION_NAME = config("AWS_REGION_NAME", None)
AWS_S3_CDN_URL = config("AWS_S3_CDN_URL", None)

VIDEO_THUMB_MAX_BYTES = config("VIDEO_THUMB_MAX_BYTES", 2 * 1024 * 1024 * 1024, int)

# Single knob for the upload body cap. The same env var is templated into
# nginx's client_max_body_size (nginx/60-sign-secret.sh), enforced in asgi.py
# before Django spools the request body to disk, rechecked per-file in
# upload_view, and passed to Uppy for client-side pre-flight rejection.
try:
    UPLOAD_MAX_SIZE = parse_size(config("UPLOAD_MAX_SIZE", "5G"))
except ValueError:
    print(f"Invalid UPLOAD_MAX_SIZE: {config('UPLOAD_MAX_SIZE', '5G')} - using default: 5G")
    UPLOAD_MAX_SIZE = parse_size("5G")
print(f"UPLOAD_MAX_SIZE: {UPLOAD_MAX_SIZE}")

# tus resumable uploads via tusd — a sidecar container in the multi-container
# stacks, a local supervisord program in the all-in-one image. Every image
# this project ships runs it, so TUS_ENABLED defaults on: switches the web
# uploader from XHR to chunked tus uploads at /tus/, keeping chunks under
# Cloudflare's 100MB body cap and letting dropped transfers resume from the
# last confirmed offset. Escape hatch for a custom deployment that doesn't
# run tusd: set TUS_ENABLED=False.
TUS_ENABLED = config("TUS_ENABLED", True, bool)
# Client-side chunk size (MB) for tus uploads. 90MB default stays under
# Cloudflare's 100MB request-body cap with headroom; raise it for deployments
# not fronted by Cloudflare Free/Pro to cut round trips on large files.
TUS_CHUNK_MB = config("TUS_CHUNK_MB", 90, int)
# tusd's -upload-dir on the shared media volume; must match the tusd service
# command and be visible to app + worker containers for zero-copy import.
TUS_UPLOAD_DIR = config("TUS_UPLOAD_DIR", "/data/media/tus")
# Abandoned partial uploads are swept after this many hours (cleanup_tus_uploads).
TUS_EXPIRE_HOURS = config("TUS_EXPIRE_HOURS", 24, int)
# Shared secret required on /api/tus/hook/ calls (defense in depth on top of
# the nginx 404 + internal-network containment). Empty means read it from
# TUS_HOOK_SECRET_FILE, which the nginx entrypoint generates on the shared
# media volume; the env var is an optional override for both app and tusd.
TUS_HOOK_SECRET = config("TUS_HOOK_SECRET", "")
TUS_HOOK_SECRET_FILE = config("TUS_HOOK_SECRET_FILE", "/data/media/db/tus-hook.secret")
# Minimum free space (MB) the media volume must have left over after a
# declared upload completes, checked in the pre-create hook. quota/max-size
# bound one user's own usage; this bounds the shared disk itself, which
# every user's uploads, thumbnails, and the database all live on.
TUS_DISK_HEADROOM_MB = config("TUS_DISK_HEADROOM_MB", 1024, int)
print(f"TUS_ENABLED: {TUS_ENABLED}")

# Pixel budget for in-request image processing (EXIF handling + thumbnails).
# Decoding costs roughly 3-4 bytes per pixel per copy and processing touches
# several copies, so images above this budget are stored as-is with no
# EXIF/thumbnail pass instead of risking an OOM-killed worker. 0 = derive
# from the container's cgroup memory limit; an explicit value overrides.
UPLOAD_MAX_IMAGE_PIXELS = config("UPLOAD_MAX_IMAGE_PIXELS", 0, int)
if not UPLOAD_MAX_IMAGE_PIXELS and (_mem_limit := cgroup_memory_limit()):
    # half the container limit shared across the two gunicorn workers at
    # ~16 bytes/pixel of processing headroom; floor of 8 MP so common
    # screenshots/photos still get thumbnails on tiny containers, ceiling of
    # Pillow's default so big hosts keep decompression-bomb protection.
    UPLOAD_MAX_IMAGE_PIXELS = min(max(_mem_limit // 2 // 16, 8_000_000), 178_956_970)
print(f"UPLOAD_MAX_IMAGE_PIXELS: {UPLOAD_MAX_IMAGE_PIXELS or 'unlimited'}")

CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", True, bool)
NGINX_ACCESS_LOGS = config("NGINX_ACCESS_LOGS", "/logs/nginx.access")

# CACHE_MIDDLEWARE_SECONDS = 0
if csrf_origins := config("CSRF_TRUSTED_ORIGINS", "", Csv()):
    CSRF_TRUSTED_ORIGINS = csrf_origins
# SECURE_REFERRER_POLICY = config('SECURE_REFERRER_POLICY', 'no-referrer')

MESSAGE_TAGS = {
    message_constants.DEBUG: "secondary",
    message_constants.INFO: "primary",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}

CORS_ALLOW_HEADERS = (
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "format",
    "expr",
    "info",
    "albums",
)

CELERY_BEAT_SCHEDULE = {
    "app_init": {
        "task": "home.tasks.app_init",
        "schedule": datetime.timedelta(seconds=1),
        "one_off": True,
    },
    "generate_thumbs": {
        "task": "home.tasks.generate_thumbs",
        "schedule": datetime.timedelta(seconds=1),
        "one_off": True,
    },
    "app_cleanup": {
        "task": "home.tasks.app_cleanup",
        "schedule": datetime.timedelta(hours=config("APP_CLEANUP_HOUR", 1, int)),
    },
    "version_check": {
        "task": "home.tasks.version_check",
        "schedule": datetime.timedelta(hours=config("VERSION_CHECK_HOUR", 8, int)),
    },
    "delete_expired_files": {
        "task": "home.tasks.delete_expired_files",
        "schedule": datetime.timedelta(minutes=config("DELETE_EXPIRED_MIN", 15, int)),
    },
    "enforce_stream_retention": {
        "task": "home.tasks.enforce_stream_retention",
        "schedule": datetime.timedelta(minutes=config("STREAM_RETENTION_MIN", 15, int)),
    },
    "process_stats": {
        "task": "home.tasks.process_stats",
        "schedule": datetime.timedelta(minutes=config("PROCESS_STATS_MIN", 15, int)),
    },
    "refresh_gallery_static_urls_cache": {
        "task": "home.tasks.refresh_gallery_static_urls_cache",
        "schedule": crontab(minute="0", hour="9,21"),
    },
    "flush-token-last-used": {
        "task": "home.tasks.flush_token_last_used",
        "schedule": crontab(minute=0),
    },
    "cleanup_tus_uploads": {
        "task": "home.tasks.cleanup_tus_uploads",
        "schedule": datetime.timedelta(hours=config("TUS_CLEANUP_HOUR", 1, int)),
    },
}


CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    "host": config("CHANNELS_REDIS_HOST", "redis"),
                    "port": config("CHANNELS_REDIS_PORT", 6379, int),
                    "socket_timeout": None,
                }
            ],
        },
    },
}

CACHES = {
    "default": {
        "BACKEND": config("CACHE_BACKEND", "django_redis.cache.RedisCache"),
        "LOCATION": config("CACHE_LOCATION", "redis://redis:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
}

if database_type == "sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": db_location,
            "TEST": {
                "NAME": os.path.join(BASE_DIR, "db_test.sqlite3"),
            },
        }
    }
elif database_type == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": config("DATABASE_NAME"),
            "USER": config("DATABASE_USER"),
            "PASSWORD": config("DATABASE_PASS"),
            "HOST": config("DATABASE_HOST"),
            "PORT": config("DATABASE_PORT", "3306"),
            "OPTIONS": {
                "isolation_level": "repeatable read",
                "init_command": "SET sql_mode='STRICT_ALL_TABLES'",
            },
        },
    }
elif database_type == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DATABASE_NAME"),
            "USER": config("DATABASE_USER"),
            "PASSWORD": config("DATABASE_PASS"),
            "HOST": config("DATABASE_HOST"),
            "PORT": config("DATABASE_PORT", "5432"),
            "OPTIONS": {},
        },
    }
else:
    raise ValueError(f"Unknown DATABASE_TYPE: {database_type}")

INSTALLED_APPS = [
    "channels",
    "corsheaders",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "webpush",
    "home",
    "oauth",
    "settings",
]
if DEBUG:
    INSTALLED_APPS.insert(0, "daphne")
    INSTALLED_APPS += [
        "django_extensions",
        "debug_toolbar",
    ]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "djangofiles.middleware.SessionRefreshMiddleware",
    # 'settings.middleware.TimezoneMiddleware',
]
if DEBUG:
    MIDDLEWARE += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": TEMPLATES_DIRS,
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.media",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.static",
                "settings.context_processors.site_settings_processor",
            ],
        },
    },
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": ("%(asctime)s - %(levelname)s - %(filename)s %(module)s.%(funcName)s:%(lineno)d - %(message)s"),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": config("DJANGO_LOG_LEVEL", "WARNING"),
            "propagate": True,
        },
        "app": {
            "handlers": ["console"],
            "level": config("APP_LOG_LEVEL", "INFO"),
            "propagate": True,
        },
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

if "test" in sys.argv or "test_coverage" in sys.argv:
    # PBKDF2's iteration count is a deliberate prod-only cost; tests create
    # hundreds of users and don't exercise hashing strength.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

if config("SENTRY_URL", False):
    sentry_sdk.init(
        dsn=config("SENTRY_URL"),
        integrations=[DjangoIntegration()],
        traces_sample_rate=config("SENTRY_SAMPLE_RATE", 0.25, float),
        send_default_pii=True,
        debug=config("SENTRY_DEBUG", config("DEBUG", "False"), bool),
        environment=config("SENTRY_ENVIRONMENT", None),
    )

if DEBUG:

    async def show_toolbar(request):
        if config("DISABLE_DEBUG_TOOLBAR", False, bool):
            return False
        return await sync_to_async(lambda: request.user.is_superuser)()
        # return True if request.user.is_superuser else False

    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": show_toolbar,
        "SHOW_COLLAPSED": True,
    }
    DEBUG_TOOLBAR_PANELS = [
        "debug_toolbar.panels.versions.VersionsPanel",
        "debug_toolbar.panels.timer.TimerPanel",
        "debug_toolbar.panels.settings.SettingsPanel",
        "debug_toolbar.panels.headers.HeadersPanel",
        "debug_toolbar.panels.request.RequestPanel",
        "debug_toolbar.panels.sql.SQLPanel",
        "debug_toolbar.panels.staticfiles.StaticFilesPanel",
        "debug_toolbar.panels.templates.TemplatesPanel",
        "debug_toolbar.panels.cache.CachePanel",
        "debug_toolbar.panels.signals.SignalsPanel",
        "debug_toolbar.panels.logging.LoggingPanel",
        "debug_toolbar.panels.redirects.RedirectsPanel",
    ]
