# AGENTS.md

## Repo snapshot

- Application source lives in `app/`.
- Django entrypoint: `app/manage.py`.
- Project package: `app/djangofiles/` (`settings.py`, `urls.py`, `asgi.py`, `celery.py`).
- Main first-party apps: `home`, `api`, `oauth`, `settings`; `webpush` is vendored but active.
- Top-level `django-files/` is runtime data for local/dev use (`db/database.sqlite3`), not source code.

## Where behavior lives

- `app/home/`: core product logic.
  - Models for `Files`, `Albums`, `ShortURLs`, `Stream`, `StreamHistory`.
  - Main HTML views in `home/views.py`.
  - Background jobs in `home/tasks.py`.
  - Websocket protocol in `home/consumers.py`.
  - Signals in `home/signals.py` clear caches, delete storage objects, and enqueue websocket updates.
- `app/api/`: JSON/API surface, including upload, shorten, file/album CRUD-ish endpoints, auth helpers, and stream endpoints.
  - `api/views.py` is large and is the main upload/REST entrypoint.
- `app/oauth/`: login/logout, OAuth providers (Discord/GitHub/Google), Duo, webhook setup, and the custom user model.
  - `oauth.models.CustomUser` is `AUTH_USER_MODEL`.
- `app/settings/`: singleton site settings model, settings UI, ShareX/Flameshot config generation, and template context processing.
- `app/webpush/`: push subscription and VAPID plumbing.

## Runtime architecture

- Root URLConf is `app/djangofiles/urls.py`.
  - `/` -> `home.urls`
  - `/settings/` -> `settings.urls`
  - `/oauth/` -> `oauth.urls`
  - `/api/` -> `api.urls`
  - `/webpush/` -> `webpush.urls`
- ASGI + Channels:
  - `app/djangofiles/asgi.py`
  - websocket route `/ws/home/` -> `home.consumers.HomeConsumer`
- Celery:
  - app in `app/djangofiles/celery.py`
  - beat schedule declared in `app/djangofiles/settings.py`
  - worker startup hook is registered in `app/home/signals.py`
- Redis is the default cache, session store, channels layer, and Celery broker/backend.

## Storage and config

- Environment loading is in `app/djangofiles/settings.py`:
  - tests use `test.env`
  - normal runs use `settings.env`
- File storage switches on `AWS_STORAGE_BUCKET_NAME`:
  - local filesystem by default
  - S3 via `app/home/util/storage.py` and `app/home/util/s3.py`
- File URL generation, signed raw URLs, thumbnails, and download URLs are implemented on `home.models.Files`.
- `settings.context_processors.site_settings_processor` caches the singleton `SiteSettings` object and activates timezone per request.

## Frontend map

- Templates: `app/templates/`
- App JS: `app/static/js/`
- App CSS: `app/static/css/`
- Bundled/vendor assets copied to `app/static/dist/` by `npm install` / `npx gulp`
- API docs source: `swagger.yaml`

## High-value files to open first

- `app/djangofiles/settings.py`
- `app/djangofiles/urls.py`
- `app/home/models.py`
- `app/home/views.py`
- `app/api/views.py`
- `app/oauth/models.py`
- `app/settings/models.py`

## Repo-specific gotchas

- The app named `settings` is a Django app, not the project settings package.
- `home/views.py`, `api/views.py`, and especially `home/consumers.py` are large, central modules; expect broad coupling.
- `HomeConfig.ready()` and `SettingsConfig.ready()` load signal handlers, so model saves/deletes often trigger Celery/cache side effects.
- Deleting `Files` also deletes backing storage and thumb files via signals.
- Local static/media defaults point at `/data/...` paths in containerized runs.
- `settings.py` prints config/debug values during startup, so noisy stdout is expected.

## Validation defaults

- Python deps: `uv pip install --system -r app/requirements-dev.txt`
- Node deps: `npm install`
- Static/vendor asset sync: `npx gulp`
- Migration check:
  - `cd app && python manage.py migrate`
  - `cd app && python manage.py makemigrations --dry-run --check --noinput`
- Tests:
  - `cd app && python manage.py test --verbosity 2 --keepdb`
- Lint/format checks used in CI:
  - `ruff check .`
  - `black --check .`
  - `isort --check .`
  - `bandit -c pyproject.toml -r app`
  - `npm run lint`

## Test coverage reality

- Existing automated coverage is light and concentrated in:
  - `app/djangofiles/tests.py`
  - `app/api/test_views.py`
  - `app/home/tests.py`
  - `app/webpush/tests/test_vapid.py`
- `app/home/tests.py` includes Playwright/Channels coverage and is heavier than the rest of the suite.
