#!/usr/bin/env sh

#[ ! -d "/mnt/data" ] && \
#    mkdir -p "/mnt/media" && \
#    chown app:app "/mnt/media"
#
#[ ! -d "/data/media/files" ] && \
#    mkdir -p "/data/media/files" && \
#    chown app:app "/data/media/files"
#
#[ ! -d "/data/media/db" ] && \
#    mkdir -p "/data/media/db" && \
#    chown app:app "/data/media/db"

set -ex

if echo "${*}" | grep -q "gun";then
    python manage.py migrate
    python manage.py collectstatic --noinput

    if [ -n "${DJANGO_SUPERUSER_PASSWORD}" ] &&
    [ -n "${DJANGO_SUPERUSER_USERNAME}" ] &&
    [ -n "${DJANGO_SUPERUSER_EMAIL}" ];then
        python manage.py createsuperuser --noinput || :
    fi
fi

exec "$@"
