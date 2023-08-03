[![Discord](https://img.shields.io/discord/899171661457293343?label=Discord&color=5865F2&logo=discord&logoColor=white)](https://discord.gg/wXy6m2X8wY)
[![Actions Test](https://img.shields.io/github/actions/workflow/status/django-files/django-files/test.yaml?label=Test&logo=github)](https://github.com/django-files/django-files/actions/workflows/test.yaml)
[![Drone Deploy](https://img.shields.io/drone/build/django-files/django-files?label=Deploy&logo=drone&server=https%3A%2F%2Fdrone.hosted-domains.com)](https://drone.hosted-domains.com/django-files/django-files)
[![Codacy Grade](https://img.shields.io/codacy/grade/7c41f4f6526c4233ba1304bfb45981c4?label=Codacy&logo=codacy&logoColor=white)](https://app.codacy.com/gh/django-files/django-files/dashboard)
[![Codacy Coverage](https://img.shields.io/codacy/coverage/7c41f4f6526c4233ba1304bfb45981c4?label=Coverage&logo=codacy&logoColor=white)](https://app.codacy.com/gh/django-files/django-files/dashboard)
[![](https://repository-images.githubusercontent.com/672712475/52cf00a8-31de-4b0a-8522-63670bb4314a)](https://github.com/django-files/django-files)
# Django Files

A Self-Hosted Django File Manager for Uploading and Sharing; 
designed to work with client apps such as [ShareX](https://github.com/ShareX/ShareX).  
Django Files is currently functional but **Under Active Development**. Expect breaking changes
until an official [release](https://github.com/django-files/django-files/releases) is made.  
Please open a [Feature Request](https://github.com/django-files/django-files/discussions/new?category=feature-requests)
or submit an [Issue](https://github.com/cssnr/zipline-cli/issues/new) for any bugs.

## Table of Contents

*   [Overview](#overview)
*   [Variables](#variables)
*   [Deploy](#deploy)
*   [Database](#database)
*   [Frameworks](#frameworks)

## Overview

Django Files is backwards compatible with 
[Zipline](https://zipline.diced.vercel.app/docs/api/upload) 
client upload settings.  

### Upload

Upload Endpoint: `/upload/` or `/api/upload/`  
Response Type: JSON 

```json
{
    "files": ["full-url"],
    "url": "full-url",
    "name": "file-name",
    "size": "size-bytes"
}
```

You can parse the URL with JSON keys `url` or Zipline style `files[0]`

## Variables

Both **SECRET_KEY** and **SITE_URL** are required.  
Recommended variables are in **bold** below.  
Technically you only need either Discord Variables or Local Variables.

| Variable                  | Description       | Example                                              |
|---------------------------|-------------------|------------------------------------------------------|
| **SECRET_KEY**            | App Secret        | `JYGTKLztZxVdu5NXuhXGaSkLJosiiQyBhFJ4LAHrJ5YHigQqq7` |
| **SITE_URL**              | Site URL          | `https://example.com`                                |
| **SUPER_USERS**           | Discord User IDs  | `111150265075298304,111148006983614464`              |
| **OAUTH_CLIENT_ID**       | Discord Client ID | `1135676900124135484`                                |
| **OAUTH_CLIENT_SECRET**   | Discord Secret    | `HbSyPWgOBx1U38MqmEEUy75KUe1Pm7dR`                   |
| **OAUTH_REDIRECT_URL**    | Discord Redirect  | `https://example.com/oauth/callback/`                |
| DJANGO_SUPERUSER_USERNAME | Local Username    | `admin`                                              |
| DJANGO_SUPERUSER_PASSWORD | Local Password    | `PSZX7TgiSg6aB6sZ`                                   |
| DJANGO_SUPERUSER_EMAIL    | Local E-Mail      | `abuse@aol.com`                                      |

## Deploy

Command included below to generate the required `SECRET_KEY`.  
The `SITE_URL` you are using is required for proper functionality.  

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
# copy above output for SECRET_KEY variable
vim settings.env
vim docker-compose.yaml
# create the volume you set in the docker-compose
mkdir -p /data/docker/django-files

docker compose up --build --remove-orphans --force-recreate --detach
docker compose logs -f

# expect errors on first run - wait for migration to finish, then restart
docker compose down --remove-orphans
docker compose up --build --remove-orphans --force-recreate --detach
```

*   `settings.env`
    -   edit the stuff outlined at the top, see above for more info.
*   `docker-compose.yaml` or `-swarm`
    -   edit the volume at the bottom and make sure it exist.

## Database

By default, sqlite3 is used. Available options are: 

*   sqlite3 - zero configuration, works out of the box
*   mysql - must set up and maintain your own database
*   postgresql - must set up and maintain your own database

| Variable      | Description                          |
|---------------|--------------------------------------|
| DATABASE_TYPE | `sqlite3` or `mysql` or `postgresql` |
| DATABASE_NAME | Database name.                       |
| DATABASE_USER | Database username.                   |
| DATABASE_PASS | Database password.                   |
| DATABASE_HOST | Database hostname.                   |
| DATABASE_PORT | Optional if default.                 |

Note: sqlite3 is stored by default in `media_dir/db` 
based on what is set in the `docker-compose.yaml` file.

## Frameworks

*   Django (4.x) https://www.djangoproject.com/
*   Celery (5.x) https://docs.celeryproject.org/
*   Font Awesome (6.x) http://fontawesome.io/
*   Bootstrap (5.3) http://getbootstrap.com/
*   UppyJS (3.x) https://uppy.io/

---
[Feature Requests](https://github.com/django-files/django-files/discussions/new?category=feature-requests) |
[Issues](https://github.com/cssnr/zipline-cli/issues/new) 
