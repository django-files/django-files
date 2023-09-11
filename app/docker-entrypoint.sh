#!/usr/bin/env sh

set -ex

if echo "${*}" | grep -q "gun\|runserver";then
    if [ -n "${SECRET}" ] || [ -n "${SECRET_KEY}" ];then
        echo "Writing Secret Key Variable to File: /data/media/db/secret.key"
        printf "${SECRET}${SECRET_KEY}" > /data/media/db/secret.key
    else
        if [ ! -f "/data/media/db/secret.key" ];then
            echo "Created Secret Key File: /data/media/db/secret.key"
            tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 50 > "/data/media/db/secret.key"
        else
            echo "Using Secret Key File: /data/media/db/secret.key"
            # TODO: Verify Secret Key File contains a Valid Secret Key
        fi
    fi

#    # this requires root
#    if [ -d "/docker-entrypoint.d/" ];then
#        echo "Running Scripts in: /docker-entrypoint.d/"
#        for file in $(/usr/bin/find "/docker-entrypoint.d/" -maxdepth 1 -type f -name "*.sh");do
#            echo "Running: ${file}"
#            sh "${file}"
#        done
#    fi

    python manage.py migrate
    python manage.py collectstatic --noinput -v 0
    python manage.py appstartup
fi

exec "$@"
