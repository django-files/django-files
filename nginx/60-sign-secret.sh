#!/usr/bin/env sh

set -e

echo "$0 - Starting as: $(whoami)"

mkdir -p /data/media/record
# nginx (uid 101, `user nginx;`) writes the .flv here; the app/worker
# containers (uid 1000, group 1000 there) read it, remux it, and delete it.
# Neither side owns the other's files, so make the directory group-writable
# by gid 1000 with setgid so files nginx creates are still deletable/writable
# by the app/worker containers (and vice versa) regardless of which side
# reused an inode first.
chown nginx:1000 /data/media/record
chmod 2775 /data/media/record

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
