#!/usr/bin/env sh

set -ex

if [ ! -d "/data/media/files" ];then
    echo "Creating Directory: /data/media/files"
    mkdir "/data/media/files"
fi
chown "app:app" "/data/media/files"

if [ ! -d "/data/media/db" ];then
    echo "Creating Directory: /data/media/db"
    mkdir "/data/media/db"
fi
chown "app:app" "/data/media/db"

if [ ! -d "/data/media/redis" ];then
    echo "Creating Directory: /data/media/redis"
    mkdir "/data/media/redis"
fi
chown "app:app" "/data/media/redis"

echo "127.0.0.1 app redis" >> /etc/hosts

exec "$@"
