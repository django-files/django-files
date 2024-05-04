[![Build](https://github.com/django-files/django-files/actions/workflows/build.yaml/badge.svg)](https://github.com/django-files/django-files/actions/workflows/build.yaml)
[![Test](https://github.com/django-files/django-files/actions/workflows/test.yaml/badge.svg)](https://github.com/django-files/django-files/actions/workflows/test.yaml)
[![Deploy](https://img.shields.io/drone/build/django-files/django-files?label=Deploy&logo=drone&server=https%3A%2F%2Fdrone.hosted-domains.com)](https://drone.hosted-domains.com/django-files/django-files)
[![Codacy](https://img.shields.io/codacy/grade/7c41f4f6526c4233ba1304bfb45981c4?label=Codacy&logo=codacy&logoColor=white)](https://app.codacy.com/gh/django-files/django-files/dashboard)
[![Coverage](https://img.shields.io/codacy/coverage/7c41f4f6526c4233ba1304bfb45981c4?label=Coverage&logo=codacy&logoColor=white)](https://app.codacy.com/gh/django-files/django-files/dashboard)
[![GitHub release (with filter)](https://img.shields.io/github/v/release/django-files/django-files?logo=github&label=Release)](https://github.com/django-files/django-files/releases/latest)
[![](https://repository-images.githubusercontent.com/672712475/52cf00a8-31de-4b0a-8522-63670bb4314a)](https://github.com/django-files/django-files)

# Django Files

A Self-Hosted Sharing Focused File Manager;
designed to work with client apps such as [ShareX](https://github.com/ShareX/ShareX),
[Flameshot](https://github.com/flameshot-org/flameshot) and [iOS Shortcuts](https://support.apple.com/guide/shortcuts/welcome/ios). Django Files is currently **Under Active Development**. Expect breaking changes until an official
major version [release](https://github.com/django-files/django-files/releases) is made.

Please open a [Feature Request](https://github.com/django-files/django-files/discussions/new?category=feature-requests)
or submit an [Issue](https://github.com/django-files/django-files/issues/new) for any bugs.

## Table of Contents

-   [Overview](#overview)
-   [Running](#running)
    -   [Docker Run](#docker-run)
    -   [Docker Compose](#docker-compose)
-   [Features](#features)
-   [Screen Shots](#screen-shots)
-   [Usage](#usage)
    -   [Files](#files)
    -   [Short URL](#short-urls)
    -   [User Settings](#user-settings)
    -   [Site Settings](#site-settings)
-   [Variables](#variables)
-   [Database](#database)
-   [Dev Deploy](#dev-deploy)
-   [Frameworks](#frameworks)

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

You must use `media_dir` or mount a volume to `/data/media` to store files (if not using s3), the database(if using sqlite), and sessions.
To use a local mount, replace `media_dir` with `/path/to/folder` you want to store the data locally
and remove the `volumes` section from the bottom.

For Extra Options See: [Variables](#variables)

### Default Login Credentials

You **should** override the default credentials with environment variables or settings.env. You will be prompted to set your password on first login.

-   **Username:** `admin`
-   **Password:** `12345`

### Docker Run:

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
        image: ghcr.io/django-files/django-files:latest
        volumes:
            - media_dir:/data/media
        ports:
            - '80:80'

volumes:
    media_dir:
```

Instead of using a settings.env you can specify any settings variables via the environment section in the docker compose file.
Or Manually Specify a Username and Password:

```yaml
version: '3'

services:
    django-files:
        image: ghcr.io/django-files/django-files:latest
        environment:
            USERNAME: 'cooluser'
            PASSWORD: 'secretpassword'
        volumes:
            - media_dir:/data/media
        ports:
            - '80:80'

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
You can find some planned features and known issues on the [TODO.md](TODO.md). Until then, feel free to
[Submit a Feature Request](https://github.com/django-files/django-files/discussions/new?category=feature-requests).

### Core

-   Local or S3 file storage
-   Ready-to-use ShareX, Flameshot, iOS Shortcuts upload scripts
-   Customizable branding and appearance. Dark + light modes.
-   Google Chrome and Mozilla Firefox Web Extension
-   Optional Sentry Error Reporting
-   Optional user and global storage quotas
-   Optional public upload function

### Auth

-   Multiple Users, Local, and Optional OAuth
-   Connect existing accounts to configured OAuth Services
-   Configure OAuth Services from the Django Admin UI (no restart required)
-   Oauth Currently Supports: Discord, GitHub, Google [Request Another](https://github.com/django-files/django-files/discussions/new?category=feature-requests)
-   Optional Duo Two-Factor Authentication
-   Generate Invite links and Invite users to your django-files instance.


### UI Features

-   Home Page; with Overview and Stats
-   Stats Page; with Stats and Graphs (WIP)
-   Gallery; to Preview Image Files
-   Upload; with Drag and Drop
-   Files; View and Delete
-   Short URLs; View, Create, and Delete Shorts
-   Settings; Configure Settings via UI
-   Django Admin to Manage all data for Superusers
-   Preview Page for Embeds with optional file metadata

### User Settings

-   Per User Default Expiration for Files
-   Metadata control: Remove EXIF Data on Upload OR Remove EXIF GPS Only
-   Theme Customization: Custom Embed Color and Navbar Colors per user
-   Avatars: Select local or oauth sourced avatar.

### Files

-   File Expiration
-   View Counting
-   EXIF Metadata Preview
-   Private Files
-   Password-Protected Files
-   Syntax highligting for code/text files.

### FileStats

-   Total Files
-   Total Size
-   Total Short URLs
-   Total Views
-   Individual MIME Type Stats

### Short URLs

-   Vanity URLs
-   Use Counting
-   Max Uses

### External

-   Firefox Extension:https://addons.mozilla.org/addon/django-files
-   Chrome Extension: https://chrome.google.com/webstore/detail/django-files/abpbiefojfkekhkjnpakpekkpeibnjej

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
- Enable Public Uploads: /public : Anonymous users can upload.
- Enable Oauth Registration: Allows ANY user to sign up via oauth login.


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
| GITHUB_CLIENT_ID          | GitHub Client ID   | `113567690-gvasdfasdf.apps.googleusercontent.com`    |
| GITHUB_CLIENT_SECRET      | GitHub Secret      | `GCSDPC-Tskdfix-klsjdf_r32489fj09jfsd`               |
| GOOGLE_CLIENT_ID          | Google Client ID   | `1135676900124135484`                                |
| GOOGLE_CLIENT_SECRET      | Google Secret      | `HbSyPWgOBx1U38MqmEEUy75KUe1Pm7dR`                   |
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

-   sqlite3 - **default** - zero configuration, works out of the box
-   mysql - must set up and maintain your own database
-   postgresql - must set up and maintain your own database

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

## Dev Deploy

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

-   Python (3.11) https://www.python.org/
-   Django (4.x) https://www.djangoproject.com/
-   Celery (5.x) https://docs.celeryproject.org/
-   Font Awesome (6.x) http://fontawesome.io/
-   Bootstrap (5.3) http://getbootstrap.com/
-   Uppy (3.x) https://uppy.io/
-   Highlight.js (11.x) https://highlightjs.org/
-   Datatables (1.13.x ) https://datatables.net/
-   Swagger (5.x) https://swagger.io/

[Feature Requests](https://github.com/django-files/django-files/discussions/new?category=feature-requests) |
[Issues](https://github.com/django-files/django-files/issues/new)
