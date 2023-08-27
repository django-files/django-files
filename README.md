[![Build](https://github.com/django-files/django-files/actions/workflows/build.yaml/badge.svg)](https://github.com/django-files/django-files/actions/workflows/build.yaml)
[![Test](https://github.com/django-files/django-files/actions/workflows/test.yaml/badge.svg)](https://github.com/django-files/django-files/actions/workflows/test.yaml)
[![Deploy](https://img.shields.io/drone/build/django-files/django-files?label=Deploy&logo=drone&server=https%3A%2F%2Fdrone.hosted-domains.com)](https://drone.hosted-domains.com/django-files/django-files)
[![Codacy](https://img.shields.io/codacy/grade/7c41f4f6526c4233ba1304bfb45981c4?label=Codacy&logo=codacy&logoColor=white)](https://app.codacy.com/gh/django-files/django-files/dashboard)
[![Coverage](https://img.shields.io/codacy/coverage/7c41f4f6526c4233ba1304bfb45981c4?label=Coverage&logo=codacy&logoColor=white)](https://app.codacy.com/gh/django-files/django-files/dashboard)
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

For required variables and options, see: [Variables](#variables)

### Docker Run:

You must use a volume mounted to `/data/media` to store files, database and sessions.

With inline environment variables:
```bash
docker run --name "django-files" -d --restart unless-stopped  \
  -p 80:80  -v /data/django-files:/data/media  \
  -e SECRET=07Y5uGMWF8icYIJXsKPpbdMm  \
  -e USERNAME=testuser  \
  -e PASSWORD=testpass  \
    ghcr.io/django-files/django-files:latest
```

To use a `.env` file you will need to export the variables first:
```bash
set -a; source .env
docker run --name "django-files" -d --restart unless-stopped  \
  -p 80:80  -v /data/django-files:/data/media  \
    ghcr.io/django-files/django-files:latest
```

### Docker Compose:

You must use `media_dir` or mount a volume to `/data/media` to store files, database, and sessions. 
To use a local mount, replace `media_dir` with `/path/to/folder` you want to store the data locally.

With inline environment variables:
```yaml
version: '3'

services:
  django-files:
    image: ghcr.io/django-files/django-files:latest
    environment:
      SECRET: "07Y5uGMWF8icYIJXsKPpbdMm"
      USERNAME: "testuser"
      PASSWORD: "testpass"
    volumes:
      - media_dir:/data/media
    ports:
      - "80:80"

volumes:
  media_dir:
```

With a `.env` file:
```yaml
version: '3'

services:
  django-files:
    image: ghcr.io/django-files/django-files:latest
    env_file: .env
    volumes:
      - media_dir:/data/media
    ports:
      - "80:80"

volumes:
  media_dir:
```

For a Docker Swarm and Traefik example, see: [docker-compose-prod.yaml](docker-compose-prod.yaml)

## Features

Quick Rundown of Available Features. Many more features are in-progress and not listed here.
Eventually all features will be added to this list. 
You can find some planned features and known issues on the [TODO.md](TODO.md). Until then, feel free to 
[Submit a Feature Request](https://github.com/django-files/django-files/discussions/new?category=feature-requests).

### Core
*   Multiple Users, Local, and OAuth
*   Local Storage with Optional S3 Storage
*   Ready-to-use ShareX and Flameshot scripts
*   Google Chrome and Mozilla Firefox Web Extension

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

### Site Settings
*   ShareX File and URL Configuration
*   Flameshot Script
*   Example Scripts
*   Site URL
*   Default Expiration for Files
*   Remove EXIF Data on Upload OR Remove EXIF GPS Only
*   Custom Embed Color
*   Custom Navbar Colors

### Files
*   File Expiration
*   View Counting
*   Max Views (WIP)
*   EXIF Metadata Preview

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
*   Chrome Extension: https://chrome.google.com/webstore/detail/django-files/abpbiefojfkekhkjnpakpekkpeibnjej
*   Firefox Extension:https://addons.mozilla.org/addon/django-files

## Screen Shots

Coming Soon...

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

You must configure one of the following authentication methods:
1.  Local Authentication with `DJANGO_SUPERUSER_*` Variables
2.  Discord Authentication with `OAUTH_*` Variables
    -   Variables acquired by [Creating a Discord App](#dev-deploy).

**Bold:** _Required_

| Variable                | Description       | Example                                              |
|-------------------------|-------------------|------------------------------------------------------|
| **SECRET**              | App Secret        | `JYGTKLztZxVdu5NXuhXGaSkLJosiiQyBhFJ4LAHrJ5YHigQqq7` |
| SITE_URL                | Site URL          | `https://example.com`                                |
| SUPER_USERS             | Discord User IDs  | `111150265075298304,111148006983614464`              |
| OAUTH_CLIENT_ID         | Discord Client ID | `1135676900124135484`                                |
| OAUTH_CLIENT_SECRET     | Discord Secret    | `HbSyPWgOBx1U38MqmEEUy75KUe1Pm7dR`                   |
| OAUTH_REDIRECT_URL      | Discord Redirect  | `https://example.com/oauth/callback/`                |
| USERNAME                | Local Username    | `admin`                                              |
| PASSWORD                | Local Password    | `PSZX7TgiSg6aB6sZ`                                   | 
| AWS_REGION_NAME         | AWS Region Name   | `us-east-1`                                          |
| AWS_ACCESS_KEY_ID       | AWS IAM User Key  | `AKIEAKADFGASDFASGSDAFSDF`                           |
| AWS_SECRET_ACCESS_KEY   | AWS IAM Secret    | `eVJsrhftrv2fcwyYcy323Sfhe5svy5436r557`              |
| AWS_STORAGE_BUCKET_NAME | Name of s3 bucket | `my-s3-bucket`                                       |
| AWS_QUERYSTRING_EXPIRE  | s3 urls valid for | `300`                                                |
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
The `SITE_URL` can be set with a variable or later set with UI Settings.

To make a [Discord Application](https://discord.com/developers/applications),
go to the OAuth2 section for Client ID, Client Secret, and to Set Callback URL.  
This is your SITE_URL + `/oauth/callback/`.  
Example: `https://example.com` would be `https://example.com/oauth/callback/`

Local Auth may also be used. No need to set Discord variables if so.  
**Known issues:** you can not add a Discord Webhook to a Local Auth user account.

```text
git clone https://github.com/django-files/django-files
cd django-files
cp settings.env.example settings.env

cat /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 50
# copy above output for SECRET variable
vim settings.env
vim docker-compose.yaml
# Note: both files and sqlite databse are stored in media_dir

docker compose up --build --remove-orphans --force-recreate --detach
docker compose logs -f

# expect errors on first run - wait for migration to finish, then restart
docker compose down --remove-orphans
docker compose up --build --remove-orphans --force-recreate --detach

# for development server use:
docker compose -f docker-compose-dev.yaml up --build --remove-orphans --force-recreate
```

*   `settings.env`
    -   edit the stuff outlined at the top, see above for more info.
*   `docker-compose.yaml` or `-swarm`
    -   note the database and files are stored in `media_dir` in a docker volume

## Frameworks

*   Django (4.x) https://www.djangoproject.com/
*   Celery (5.x) https://docs.celeryproject.org/
*   Font Awesome (6.x) http://fontawesome.io/
*   Bootstrap (5.3) http://getbootstrap.com/
*   Uppy (3.x) https://uppy.io/

---
[Feature Requests](https://github.com/django-files/django-files/discussions/new?category=feature-requests) |
[Issues](https://github.com/cssnr/zipline-cli/issues/new) 
