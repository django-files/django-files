#!/usr/bin/env sh

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

while [ ! -f "/data/media/db/secret.key" ]; do
    echo "Waiting for secret.key to be set by app..."
    sleep 1
done

secret=$(cat /data/media/db/secret.key)
sed "s/{{nginx_signing_secret}}/${secret}/g" -i /etc/nginx/nginx.conf

echo "$0 - Finished"
