#!/usr/bin/env sh

set -e

echo "$0 - Starting as: $(whoami)"

if echo "${*}" | grep -q "gun\|runserver";then
    echo "Running App Startup Tasks"
    if [ $PPID = 0 ] && [ -d "/docker-entrypoint.d/" ];then
        echo "Running Scripts in: /docker-entrypoint.d/"
        for file in $(/usr/bin/find "/docker-entrypoint.d/" -maxdepth 1 -type f -name "*.sh");do
            echo "Running: ${file}"
            sh "${file}"
        done
    fi

    # TODO: Use flock so this only runs once
    python manage.py migrate
    python manage.py collectstatic --noinput -v 0
#    python manage.py appstartup
else
    echo "Sleeping for 5 seconds: ${*}"
    sleep 5
fi

exec "$@"
