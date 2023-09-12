#!/usr/bin/env sh
# TODO: Use flock so this only runs once

set -e

echo "$0 - Starting as: $(whoami)"

if [ -n "${SECRET}" ] || [ -n "${SECRET_KEY}" ];then
    echo "Writing Secret Key Variable to File: /data/media/db/secret.key"
    printf "%s" "${SECRET}${SECRET_KEY}" > /data/media/db/secret.key
else
    if [ ! -f "/data/media/db/secret.key" ];then
        echo "Created Secret Key File: /data/media/db/secret.key"
        tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 50 > "/data/media/db/secret.key"
    else
        # TODO: Verify Key is Valid?
        echo "Using Secret Key File: /data/media/db/secret.key"
    fi
fi

echo "$0 - Finished"
