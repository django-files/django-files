#!/usr/bin/env sh

set -ex

if echo "${*}" | grep -q "gun\|runserver";then

    python manage.py migrate
    python manage.py collectstatic --noinput
    python manage.py clearcache

    if [ -n "${USERNAME}" ] && [ -n "${PASSWORD}" ];then
        export DJANGO_SUPERUSER_USERNAME=${USERNAME}
        export DJANGO_SUPERUSER_PASSWORD=${PASSWORD}
        python manage.py createsuperuser --email 'inop@example.com' --noinput || :
    fi

fi

exec "$@"
