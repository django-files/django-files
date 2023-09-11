#!/usr/bin/env sh

set -e

echo "$0 - Starting as: $(whoami)"

while [ ! -f "/data/media/db/secret.key-ready" ]; do
    echo "Waiting for secret.key to be set by app..."
    sleep 1
done

rm -f "/data/media/db/secret.key-ready"

secret=$(cat /data/media/db/secret.key)
sed "s/{{nginx_signing_secret}}/${secret}/g" -i /etc/nginx/nginx.conf

echo "$0 - Finished"
