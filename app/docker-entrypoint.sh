#!/usr/bin/env sh

set -ex


if [ -n "${SECRET}" ] || [ -n "${SECRET_KEY}" ];then
    printf "${SECRET}${SECRET_KEY}" > /data/media/db/secret.key
else
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
    python manage.py appstartup

fi

exec "$@"
