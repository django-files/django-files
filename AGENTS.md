# AGENTS.md

## Repo snapshot

- Application source lives in `app/`.
- Django entrypoint: `app/manage.py`.
- Project package: `app/djangofiles/` (`settings.py`, `urls.py`, `asgi.py`, `celery.py`).
- Main first-party apps: `home`, `api`, `oauth`, `settings`; `webpush` is vendored but active.
- Top-level `django-files/` is runtime data for local/dev use (`db/database.sqlite3`), not source code.

## Commands

ALWAYS use the `npm run *` command

| Command               | Purpose                                 |
| --------------------- | --------------------------------------- |
| `npm run postinstall` | Run `npx gulp` for pacakge.json changes |
| `npm run lint`        | ESLint on `npx eslint app/static/js/`   |
| `npm run prettier`    | ALWAYS RUN AFTER EDITING FILES          |

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

## Embed / file preview — two distinct contexts

The file preview UI runs in **two separate rendering contexts** that share templates but use different JS/CSS entry points. Changes to preview behaviour almost always need to be applied in both.

| Context | URL pattern | Template | JS entry | CSS loaded |
|---|---|---|---|---|
| **Full-page embed** | `/file/<name>` | `embed/preview.html` | `static/js/preview.js` | `css/preview.css` |
| **Gallery panel** | `/file/<name>?panel=1` (AJAX) | `embed/preview_panel.html` | `static/js/file-preview-panel.js` | `css/preview.css` + `css/file-preview-panel.css` |

Shared pieces:
- `embed/_preview_sidebar.html` — sidebar HTML included by both templates.
- `css/preview.css` — loaded by `gallery.html` **and** `embed/preview.html`, so rules here affect **both** contexts. Use `.preview-panel-root` scope in `file-preview-panel.css` for panel-only overrides.

Key differences:
- Full-page embed: JS initialises on `DOMContentLoaded` in `preview.js`.
- Gallery panel: HTML is fetched via AJAX (`?panel=1`) and injected into `#previewPanelContent`; `initPanelContent()` is called after injection — there is no `DOMContentLoaded`. Do not rely on `DOMContentLoaded` for panel init.
- The gallery panel hero (`panel-hero-thumb`) is a full-viewport opaque overlay that animates the already-cached gallery thumbnail into position. It must be dismissed promptly in `initPanelImage()` — holding it until the full image loads blocks all sidebar/button chrome.

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

- Python environment: the venv is pre-activated via `settings.local.json` (`VIRTUAL_ENV` + `PATH`). Use `python`, `ruff`, `black`, `isort`, `bandit`, `manage.py` directly — no `source .venv/bin/activate` needed.
- Redis is required for tests and local runs (cache, sessions, channels layer, Celery broker/backend). Start a generic Redis container listening on `localhost:6379` before invoking tests:
  - `docker run -d --rm --name df-redis -p 6379:6379 redis:7-alpine`
  - The default config in `app/djangofiles/settings.py` points at hostname `redis:6379`; override with `CACHE_LOCATION=redis://localhost:6379/0`, `CELERY_BROKER_URL=redis://localhost:6379/1`, `CELERY_RESULT_BACKEND=redis://localhost:6379/1`, `CHANNELS_REDIS_HOST=localhost` in your shell or `app/test.env` / `app/settings.env` when running outside the docker-compose stack.
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
  - ALWAYS RUN FOR CSS AND JS CHANGES: `npx prettier --write app/static/js app/static/css`

## Test coverage reality

- Existing automated coverage is light and concentrated in:
  - `app/djangofiles/tests.py`
  - `app/api/test_views.py`
  - `app/home/tests.py`
  - `app/webpush/tests/test_vapid.py`
- `app/home/tests.py` includes Playwright/Channels coverage and is heavier than the rest of the suite.
