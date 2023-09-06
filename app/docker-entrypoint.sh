#!/usr/bin/env sh

set -ex

if [ -z "${SECRET}" ] || [ -z "${SECRET_KEY}" ];then
    if [ ! -f "/data/media/db/secret.key" ];then
        tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 50 > "/data/media/db/secret.key"
        echo "Created Secret Key File: /data/media/db/secret.key"
    else
        echo "Using Secret Key File: /data/media/db/secret.key"
    fi
fi

if echo "${*}" | grep -q "gun\|runserver";then

    python manage.py migrate
    python manage.py collectstatic --noinput
    python manage.py clearcache

    if [ -n "${USERNAME}" ] && [ -n "${PASSWORD}" ];then
        export DJANGO_SUPERUSER_USERNAME="${USERNAME}"
        export DJANGO_SUPERUSER_PASSWORD="${PASSWORD}"
        python manage.py createsuperuser --email 'inop@example.com' --noinput || :
    fi

fi

exec "$@"
