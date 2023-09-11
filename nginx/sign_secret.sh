#!/usr/bin/env sh

set -ex

while [ ! -f "/data/media/db/secret.key" ]; do
    echo "Waiting for secret.key to be set by app..."
done

secret=$(cat /data/media/db/secret.key)
sed "s/{{nginx_signing_secret}}/${secret}/g" -i /etc/nginx/nginx.conf
