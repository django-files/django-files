#!/usr/bin/env sh

if echo "${*}" | grep -q "gun";then
    if [ -n "${DJANGO_SUPERUSER_PASSWORD}" ] &&
    [ -n "${DJANGO_SUPERUSER_USERNAME}" ] &&
    [ -n "${DJANGO_SUPERUSER_EMAIL}" ];then
        python manage.py createsuperuser --noinput
    fi
    set -ex
    python manage.py collectstatic --noinput
fi

set -ex

exec "$@"
