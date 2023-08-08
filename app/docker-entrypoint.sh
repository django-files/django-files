#!/usr/bin/env sh

set -ex

if echo "${*}" | grep -q "gun\|runserver";then
#    python manage.py makemigrations
    python manage.py migrate
    python manage.py collectstatic --noinput
    python manage.py clearcache
#    python manage.py loaddata sitesettings

    if [ -n "${DJANGO_SUPERUSER_PASSWORD}" ] &&
    [ -n "${DJANGO_SUPERUSER_USERNAME}" ] &&
    [ -n "${DJANGO_SUPERUSER_EMAIL}" ];then
        python manage.py createsuperuser --noinput || :
    fi
fi

exec "$@"
