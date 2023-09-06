[![Build](https://github.com/django-files/django-files/actions/workflows/build.yaml/badge.svg)](https://github.com/django-files/django-files/actions/workflows/build.yaml)
[![Test](https://github.com/django-files/django-files/actions/workflows/test.yaml/badge.svg)](https://github.com/django-files/django-files/actions/workflows/test.yaml)
[![Deploy](https://img.shields.io/drone/build/django-files/django-files?label=Deploy&logo=drone&server=https%3A%2F%2Fdrone.hosted-domains.com)](https://drone.hosted-domains.com/django-files/django-files)
[![Codacy](https://img.shields.io/codacy/grade/7c41f4f6526c4233ba1304bfb45981c4?label=Codacy&logo=codacy&logoColor=white)](https://app.codacy.com/gh/django-files/django-files/dashboard)
[![Coverage](https://img.shields.io/codacy/coverage/7c41f4f6526c4233ba1304bfb45981c4?label=Coverage&logo=codacy&logoColor=white)](https://app.codacy.com/gh/django-files/django-files/dashboard)
[![GitHub release (with filter)](https://img.shields.io/github/v/release/django-files/django-files?logo=github&label=Release)](https://github.com/django-files/django-files/releases/latest)
[![](https://repository-images.githubusercontent.com/672712475/52cf00a8-31de-4b0a-8522-63670bb4314a)](https://github.com/django-files/django-files)
# Django Files

A Self-Hosted Django File Manager for Uploading and Sharing;
designed to work with client apps such as [ShareX](https://github.com/ShareX/ShareX) and
[Flameshot](https://github.com/flameshot-org/flameshot). Django Files is currently 
functional but **Under Active Development**. Expect breaking changes until an official 
[release](https://github.com/django-files/django-files/releases) is made.

Please open a [Feature Request](https://github.com/django-files/django-files/discussions/new?category=feature-requests)
or submit an [Issue](https://github.com/cssnr/zipline-cli/issues/new) for any bugs.

## Table of Contents

*   [Overview](#overview)
*   [Running](#running)
    -   [Docker Run](#docker-run)
    -   [Docker Compose](#docker-compose)
*   [Features](#features)
*   [Screen Shots](#screen-shots)
*   [Usage](#usage)
    -   [Files](#files)
    -   [Short URL](#short-urls)
*   [Variables](#variables)
*   [Database](#database)
*   [Dev Deploy](#dev-deploy)
*   [Frameworks](#frameworks)

## Overview

A [Django](https://github.com/django/django) application, with a
[Celery](https://github.com/celery/celery) task queue, using
[Bootstrap 5.3](https://getbootstrap.com/), built for
[Docker](https://www.docker.com/) for Uploading Files via the API
or UI using [Uppy](https://uppy.io/).

## Running

> **Warning**
>
> This is currently in Beta.  
> Expect breaking changes without migrations.  

For Extra Options See: [Variables](#variables)

### Default Login Credentials

-   **Username:** `admin`
-   **Password:** `12345`

### Docker Run:

You must use a volume mounted to `/data/media` to store files, database and sessions. 

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
You must use `media_dir` or mount a volume to `/data/media` to store files, database, and sessions. 
To use a local mount, replace `media_dir` with `/path/to/folder` you want to store the data locally
and remove the `volumes` section from the bottom. Default username/passwors is `admin/2345`

```yaml
version: '3'

services:
  django-files:
    image: ghcr.io/django-files/django-files:latest
    volumes:
      - media_dir:/data/media
    ports:
      - "80:80"

volumes:
  media_dir:
```

Or Manually Specify a Username and Password:

```yaml
version: '3'

services:
  django-files:
    image: ghcr.io/django-files/django-files:latest
    environment:
      USERNAME: "cooluser"
      PASSWORD: "secretpassword"
    volumes:
      - media_dir:/data/media
    ports:
      - "80:80"

volumes:
  media_dir:
```

Then Finally:

```bash
vim docker-compose.yaml
docker compose up --remove-orphans --force-recreate --detach
```

For a Docker Swarm and Traefik example, see: [docker-compose-prod.yaml](docker-compose-prod.yaml)

## Features

Quick Rundown of Available Features. Many more features are in-progress and not listed here.
Eventually all features will be added to this list. 
You can find some planned features and known issues on the [TODO.md](TODO.md). Until then, feel free to 
[Submit a Feature Request](https://github.com/django-files/django-files/discussions/new?category=feature-requests).

### Core
*   Local Storage with Optional S3 Storage
*   Ready-to-use ShareX and Flameshot scripts
*   Google Chrome and Mozilla Firefox Web Extension
*   Optional Duo Two-Factor Authentication
*   Optional Sentry Error Reporting

### Auth
*   Multiple Users, Local, and Optional OAuth
*   Connect account to any configured OAuth Service
*   Configure OAuth Services from the UI (no restart required)
*   Supports: Discord, GitHub

### UI Features
*   Home Page; with Overview and Stats
*   Stats Page; with Stats and Graphs (WIP)
*   Gallery; to Preview Files
*   Upload; with Drag and Drop
*   Files; View and Delete
*   Short URLs; View, Create, and Delete Shorts
*   Settings; Configure Settings via UI
*   Django Admin to Manage all data for Superusers
*   Preview Page for Embeds with optional file metadata

### User Settings
*   ShareX File and URL Configuration
*   Flameshot Script
*   Example Scripts
*   Default Expiration for Files
*   Remove EXIF Data on Upload OR Remove EXIF GPS Only
*   Custom Embed Color
*   Custom Navbar Colors
*   Connect to OAuth Account (if oauth configured)

### Site Settings
*   Site URL, Title, Description, Theme Color
*   Enable Public Uploads at `/upload`
*   Enable OAuth Registration (if oauth configured)
*   Enable Two-Factor Registration (if duo configured)

### Files
*   File Expiration
*   View Counting
*   EXIF Metadata Preview
*   Private Files (Beta)
*   Password-Protected Files (Beta)

### FileStats
*   Total Files
*   Total Size
*   Total Short URLs
*   Total Views (WIP)
*   Individual MIME Type Stats

### Short URLs
*   Vanity URLs
*   View Counting
*   Max Views

### External
*   Firefox Extension:https://addons.mozilla.org/addon/django-files
*   Chrome Extension: https://chrome.google.com/webstore/detail/django-files/abpbiefojfkekhkjnpakpekkpeibnjej

## Screen Shots

There are some Screen Shots available on the GitHub Pages site by selecting 
[Screen Shots](https://django-files.github.io/screenshots.html) from the menu.

-   [https://django-files.github.io/](https://django-files.github.io/)

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

## Variables

> **Important**
> 
> **NO VARIABLES ARE REQUIRED!** All are optional.
>
> OAuth may be configured from the UI.  
> AWS/Duo/Sentry **require** environment variables.  

| Variable                | Description       | Example                                              |
|-------------------------|-------------------|------------------------------------------------------|
| SECRET                  | App Secret        | `JYGTKLztZxVdu5NXuhXGaSkLJosiiQyBhFJ4LAHrJ5YHigQqq7` |
| SITE_URL                | Site URL          | `https://example.com`                                |
| USERNAME                | Local Username    | `admin`                                              |
| PASSWORD                | Local Password    | `PSZX7TgiSg6aB6sZ`                                   | 
| SUPER_USERS             | Discord User IDs  | `111150265075298304,111148006983614464`              |
| DISCORD_CLIENT_ID       | Discord Client ID | `1135676900124135484`                                |
| DISCORD_CLIENT_SECRET   | Discord Secret    | `HbSyPWgOBx1U38MqmEEUy75KUe1Pm7dR`                   |
| GITHUB_CLIENT_ID        | GitHub Client ID  | `1135676900124135484`                                |
| GITHUB_CLIENT_SECRET    | GitHub Secret     | `HbSyPWgOBx1U38MqmEEUy75KUe1Pm7dR`                   |
| OAUTH_REDIRECT_URL      | Discord Redirect  | `https://example.com/oauth/callback/`                |
| AWS_REGION_NAME         | AWS Region Name   | `us-east-1`                                          |
| AWS_ACCESS_KEY_ID       | AWS IAM User Key  | `AKIEAKADFGASDFASGSDAFSDF`                           |
| AWS_SECRET_ACCESS_KEY   | AWS IAM Secret    | `eVJsrhftrv2fcwyYcy323Sfhe5svy5436r557`              |
| AWS_STORAGE_BUCKET_NAME | Name of s3 bucket | `my-s3-bucket`                                       |
| AWS_QUERYSTRING_EXPIRE  | s3 urls valid for | `300`                                                |
| AWS_S3_CDN_URL          | proxy or cdn url  | `https://examples3cdndomain.com`                     |
| DUO_API_HOST            | DUO API Host      | `api-abc123.duosecurity.com`                         |
| DUO_CLIENT_ID           | DUO Client ID     | `nmoNmuLM72WB3RsNkwuv`                               |
| DUO_CLIENT_SECRET       | DUO Secret        | `nmoNmuLM72WB3RsNkwuvnmoNmuLM72WB3RsNkwuv`           |
| SENTRY_URL              | Sentry URL        | `https://a5cb357a@o133337.ingest.sentry.io/1234567`  |
| SENTRY_ENVIRONMENT      | Sentry ENV        | `prod`                                               |

## Database

No changes or additional configuration is required for `sqlite3`.

*   sqlite3 - **default** - zero configuration, works out of the box
*   mysql - must set up and maintain your own database
*   postgresql - must set up and maintain your own database

| Variable      | Description                          |
|---------------|--------------------------------------|
| DATABASE_TYPE | `sqlite3` or `mysql` or `postgresql` |
| DATABASE_NAME | Database name                        |
| DATABASE_USER | Database username                    |
| DATABASE_PASS | Database password                    |
| DATABASE_HOST | Database hostname                    |
| DATABASE_PORT | Optional if default                  |

Note: sqlite3 is stored by default in `media_dir/db`
based on what is set in the `docker-compose.yaml` file.

## Dev Deploy

> **Note**
>
> These instructions may be out of date, but should get you up and running.

Command included below to generate the required `SECRET`.  
The `SITE_URL` should be set with a variable for development, in UI Settings.
You may also want to configure an auth method from the variables above.

```text
git clone https://github.com/django-files/django-files
cd django-files
cp settings.env.example settings.env

cat /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 50
# copy above output for SECRET variable
vim settings.env

docker compose up --build --remove-orphans --force-recreate --detach
# or
docker compose -f docker-compose-dev.yaml up --build --remove-orphans --force-recreate -detach
docker compose logs -f

# bring the stack down
docker compose down --remove-orphans
```

## Frameworks/Credits

*   Django (4.x) https://www.djangoproject.com/
*   Celery (5.x) https://docs.celeryproject.org/
*   Font Awesome (6.x) http://fontawesome.io/
*   Bootstrap (5.3) http://getbootstrap.com/
*   Uppy (3.x) https://uppy.io/

---
[Feature Requests](https://github.com/django-files/django-files/discussions/new?category=feature-requests) |
[Issues](https://github.com/cssnr/zipline-cli/issues/new) 
