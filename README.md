[![CI](https://img.shields.io/github/actions/workflow/status/django-files/django-files/ci.yaml?logo=github&logoColor=white&label=ci)](https://github.com/django-files/django-files/actions/workflows/ci.yaml)
[![Test](https://img.shields.io/github/actions/workflow/status/django-files/django-files/test.yaml?logo=github&logoColor=white&label=test)](https://github.com/django-files/django-files/actions/workflows/test.yaml)
[![Lint](https://img.shields.io/github/actions/workflow/status/django-files/django-files/lint.yaml?logo=github&logoColor=white&label=lint)](https://github.com/django-files/django-files/actions/workflows/lint.yaml)
[![Coverage](https://img.shields.io/codacy/coverage/7c41f4f6526c4233ba1304bfb45981c4?label=Coverage&logo=codacy&logoColor=white)](https://app.codacy.com/gh/django-files/django-files/dashboard)
[![Codacy](https://img.shields.io/codacy/grade/7c41f4f6526c4233ba1304bfb45981c4?label=Codacy&logo=codacy&logoColor=white)](https://app.codacy.com/gh/django-files/django-files/dashboard)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=django-files_django-files&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=django-files_django-files)
[![GitHub Release Version](https://img.shields.io/github/v/release/django-files/django-files?logo=github)](https://github.com/django-files/django-files/releases/latest)
[![GitHub Top Language](https://img.shields.io/github/languages/top/django-files/django-files?logo=htmx&logoColor=white)](https://github.com/django-files/django-files)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/django-files/django-files?logo=github&logoColor=white&label=updated)](https://github.com/django-files/django-files/graphs/commit-activity)
[![GitHub Repo Stars](https://img.shields.io/github/stars/django-files/django-files?style=flat&logo=github&logoColor=white)](https://github.com/django-files/django-files/stargazers)
[![GitHub Org Stars](https://img.shields.io/github/stars/django-files?style=flat&logo=github&logoColor=white&label=org%20stars)](https://django-files.github.io/)
[![](https://repository-images.githubusercontent.com/672712475/52cf00a8-31de-4b0a-8522-63670bb4314a)](https://github.com/django-files/django-files)

# Django Files

A Self-Hosted File Manager designed for seamless file sharing, with built-in support for client apps like ShareX, Flameshot, and iOS Shortcuts.

🚀 Currently in Active Development – Expect breaking changes until an official major version release.

🔹 Have an idea? Submit a [Feature Request](https://github.com/django-files/
🐛 Found a bug? Report an [Issue](https://github.com/django-files/django-files/issues/new) for any bugs.

## Table of Contents

- [Overview](#overview)
- [Running](#running)
  - [Docker Run](#docker-run)
  - [Docker Compose](#docker-compose)
- [Features](#features)
- [Screen Shots](#screen-shots)
- [Usage](#usage)
  - [Files](#files)
  - [Short URL](#short-urls)
  - [User Settings](#user-settings)
  - [Site Settings](#site-settings)
- [Variables](#variables)
- [Database](#database)
- [Dev Deploy](#dev-deploy)
- [Frameworks](#frameworks)

## Overview

Django Files is a Django-based web application with a Celery task queue, built using Bootstrap 5.3 and containerized with Docker. It enables file uploads via API or UI using Uppy, offering a robust and flexible self-hosted solution for file management.

## 🚀 Getting Started

> ⚠️ Important Notice
>
> 🔸 This project is in Beta – Expect breaking changes without migrations.
> 🔸 If not using S3, you must mount media_dir to /data/media for file storage and SQLite database persistence.

For Extra Options See: [Variables](#variables)

### Login Credentials

You **should** override the default credentials with environment variables or settings.env. You will be prompted to set your password on first login.

### 🔧 Quick Start with Docker

Short one-liner to run in foreground:

```bash
docker run --rm -p 80:80 -v ./django-files:/data/media ghcr.io/django-files/django-files:latest
```

Run it in the background:

```bash
docker run --name "django-files" -d --restart unless-stopped  \
  -p 80:80  -v ./django-files:/data/media  \
    ghcr.io/django-files/django-files:latest
```

Or Manually Specify a Username and Password:

```bash
docker run --name "django-files" -d --restart unless-stopped  \
  -p 80:80  -v ./django-files:/data/media  \
  -e USERNAME=cooluser  \
  -e PASSWORD=secretpassword  \
    ghcr.io/django-files/django-files:latest
```

### Docker Compose:

```yaml
version: '3'

services:
  django-files:
    environment:
      USERNAME: 'cooluser'
      PASSWORD: 'secretpassword'
    image: ghcr.io/django-files/django-files:latest
    volumes:
      - media_dir:/data/media
    ports:
      - '80:80'

volumes:
  media_dir:
```

Then Finally:

```bash
nano docker-compose.yaml # write your compose file
docker compose up --remove-orphans --force-recreate --detach
```

For a Docker Swarm and Traefik example, see: [docker-compose-prod.yaml](docker-compose-prod.yaml)

## Features

Django Files is packed with features for seamless file management and sharing. More features are in progress!
[Request a Feature](https://github.com/django-files/django-files/discussions/new?category=feature-requests).

### 🔹 Core Features

- Local or S3 storage support
- One-click integration with ShareX, Flameshot, and iOS Shortcuts
- Customizable UI with light/dark mode
- OAuth support (Discord, GitHub, Google) & two-factor authentication (Duo)
- Web extensions for Chrome and Firefox
- Public upload support (optional)

### 🔒 Authentication & Security

- Multi-user support with local & OAuth authentication options
- Invite system for user onboarding
- OAuth configuration via Django Admin (no restart required)

### 📊 UI & File Management

- Drag & Drop file uploads
- Short URLs with vanity support
- Private & password-protected files
- Configurable EXIF metadata removal on upload
- Bulk file actions
- Albums & galleries for organizing files

### 📈 Stats & Insights

- Dashboard with user-friendly overview & stats
- Graph-based analytics (work in progress)
- File expiration & view counting

### External

- Firefox Extension:https://addons.mozilla.org/addon/django-files
- Chrome Extension: https://chrome.google.com/webstore/detail/django-files/abpbiefojfkekhkjnpakpekkpeibnjej

## Screen Shots

Screenshots and UI previews are available on the
[Django Files Github Site.](https://django-files.github.io/screenshots.html) from the menu.

## Usage

Django Files is backwards compatible with
[Zipline](https://zipline.diced.vercel.app/docs/api/upload)
client upload settings.

### Files

Upload Endpoint: `/api/upload/`  
Response Type: JSON

```json
{
  "files": ["full-url"],
  "url": "full-url",
  "name": "file-name",
  "size": "size-bytes"
}
```

### Short URLs

Upload Endpoint: `/api/shorten/`  
Response Type: JSON

```json
{
  "url": "full-short-url"
}
```

You can parse the URL with JSON keys `url` or Zipline style `files[0]`

### User Settings

- Avatar: Can be reuploaded if set to Local/Cloud.
- Avatar Source: If to use oauth avatars, or local avatars. (Oauth avatars cannot be changed via django files.)
- First Name: User's first name, for personalization of username display.
- Timezone: User's timezone, will show times in user's local time when logged in.
- Default Expire: The default file expiration for files uploaded with out an expiration for this user.
- Default Upload Format: The default file name format for files uploaded without a specific file name format.
- Strip All EXIF Data: Strips all EXIF metadata from images on upload. (Changes do not apply to existing uploads)
- Strip GPS EXIF Data: Strips GPS meta data from images on upload. (Changes do not apply to existing uploads)
- Private Files: Make uploads private by default unless otherwise specified. (Changes do not apply to existing uploads)
- Password Protected File: Make uploads password protected by default unless otherwise specified. (Changes do not apply to existing uploads)
- Enabled EXIF Embeds: If to show EXIF metadata on unfurls/embeds.
- Appearance Embed Color: Color of embeds/unfurls for shared links.
- Appearance Nav Colors: Color of navbar for this user and anonymous users viewing shared user files.
- Discord Webhooks: Discord webhooks to trigger when a file is uploaded.

### Site Settings

- Site URL: The site url to use, used to generate links.
- Site Title: Site title in browser and unfurls.
- Global Storage Quota: The storage quota for the entire django files deployment.
- User Default Storage Quota: The default storage quota for new users without a specified quota.
- Timezone: global timezone for django files deployment. Default TZ anonymous users see.
- Site Description: Site description shown on unfurled links for clients that show url unfurls.
- Public Uploads: /public : When enabled anonymous users can upload.
- Oauth Registration: When enabled ANY user may sign up via oauth login.
- Local Authentication: When disabled, only oauth authentication can be performed. (Falls back to enabled when oauth not configured)

## Variables

> **Important**
>
> **NO VARIABLES ARE REQUIRED!** All are optional.
>
> OAuth may be configured from the UI.  
> AWS/Duo/Sentry **require** environment variables.
> Switching between local storage and s3 is not supported and WILL cause problems.

| Variable                  | Description        | Example                                              |
| ------------------------- | ------------------ | ---------------------------------------------------- |
| SECRET                    | App Secret         | `JYGTKLztZxVdu5NXuhXGaSkLJosiiQyBhFJ4LAHrJ5YHigQqq7` |
| SITE_URL                  | Site URL           | `https://example.com`                                |
| USERNAME                  | Local Username     | `admin`                                              |
| PASSWORD                  | Local Password     | `PSZX7TgiSg6aB6sZ`                                   |
| SUPER_USERS               | oAuth Sup User IDs | `111150265075298304,111148006983614464`              |
| DISCORD_CLIENT_ID         | Discord Client ID  | `1135676900124135484`                                |
| DISCORD_CLIENT_SECRET     | Discord Secret     | `HbSyPWgOBx1U38MqmEEUy75KUe1Pm7dR`                   |
| GITHUB_CLIENT_ID          | GitHub Client ID   | `1135676900124135484`                                |
| GITHUB_CLIENT_SECRET      | GitHub Secret      | `HbSyPWgOBx1U38MqmEEUy75KUe1Pm7dR`                   |
| GOOGLE_CLIENT_ID          | Google Client ID   | `113567690-gvasdfasdf.apps.googleusercontent.com`    |
| GOOGLE_CLIENT_SECRET      | Google Secret      | `GCSDPC-Tskdfix-klsjdf_r32489fj09jfsd`               |
| OAUTH_REDIRECT_URL        | Discord Redirect   | `https://example.com/oauth/callback/`                |
| AWS_REGION_NAME           | AWS Region Name    | `us-east-1`                                          |
| AWS_ACCESS_KEY_ID         | AWS IAM User Key   | `AKIEAKADFGASDFASGSDAFSDF`                           |
| AWS_SECRET_ACCESS_KEY     | AWS IAM Secret     | `eVJsrhftrv2fcwyYcy323Sfhe5svy5436r557`              |
| AWS_STORAGE_BUCKET_NAME   | Name of s3 bucket  | `my-s3-bucket`                                       |
| STATIC_QUERYSTRING_EXPIRE | static link expire | `300`                                                |
| AWS_S3_CDN_URL            | proxy or cdn url   | `https://examples3cdndomain.com`                     |
| DUO_API_HOST              | DUO API Host       | `api-abc123.duosecurity.com`                         |
| DUO_CLIENT_ID             | DUO Client ID      | `nmoNmuLM72WB3RsNkwuv`                               |
| DUO_CLIENT_SECRET         | DUO Secret         | `nmoNmuLM72WB3RsNkwuvnmoNmuLM72WB3RsNkwuv`           |
| SENTRY_URL                | Sentry URL         | `https://a5cb357a@o133337.ingest.sentry.io/1234567`  |
| SENTRY_ENVIRONMENT        | Sentry ENV         | `prod`                                               |

## Database

- sqlite3 - **default** - zero configuration, works out of the box
- mysql - must set up and maintain your own database
- postgresql - must set up and maintain your own database

| Variable      | Description                          |
| ------------- | ------------------------------------ |
| DATABASE_TYPE | `sqlite3` or `mysql` or `postgresql` |
| DATABASE_NAME | Database name                        |
| DATABASE_USER | Database username                    |
| DATABASE_PASS | Database password                    |
| DATABASE_HOST | Database hostname                    |
| DATABASE_PORT | Optional if default                  |

Note: sqlite3 is stored by default in `media_dir/db`
based on what is set in the `docker-compose.yaml` file.

## 🛠 Development Deployment

Command included below to generate the required `SECRET`.  
The `SITE_URL` should be set with a variable for development, in UI Settings.
You may also want to configure an auth method from the variables above.

```text
git clone https://github.com/django-files/django-files
cd django-files
cp settings.env.example settings.env

cat /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 50
# copy above output for SECRET variable, add to settings or as environment variable
vim settings.env

docker compose up --build --remove-orphans --force-recreate --detach
# or
docker compose -f docker-compose-dev.yaml up --build --remove-orphans --force-recreate -detach
docker compose logs -f

# bring the stack down
docker compose down --remove-orphans
```

Auto restarting dev deployment using settings.env for config. (ctrl+c to restart, double ctrl+c to exit)

```text
_file="docker-compose-dev.yaml";while true;do docker compose -f "${_file}" down --remove-orphans;sep 10;docker compose -f "${_file}" up --build --remove-orphans -d --force-recreate;docker compose -f "${_file}" logs -f;echo sleep 1;sleep 1;done
```

## Frameworks/Credits

- [Python](https://www.python.org/)
- [Django](https://www.djangoproject.com/)
- [Celery](https://docs.celeryproject.org/)
- [Font Awesome](http://fontawesome.io/)
- [Bootstrap](http://getbootstrap.com/)
- [Uppy](https://uppy.io/)
- [Highlight.js](https://highlightjs.org/)
- [Datatables](https://datatables.net/)
- [Swagger](https://swagger.io/)

[Feature Requests](https://github.com/django-files/django-files/discussions/new?category=feature-requests) |
[Issues](https://github.com/django-files/django-files/issues/new)
