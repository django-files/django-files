#!/usr/bin/env sh

set -ex

echo "$0 - Starting as: $(whoami)"

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

if [ -d "/docker-entrypoint.d/" ];then
    echo "Running Scripts in: /docker-entrypoint.d/"
    for file in $(/usr/bin/find "/docker-entrypoint.d/" -maxdepth 1 -type f -name "*.sh");do
        echo "Running: ${file}"
        sh "${file}"
    done
fi

exec "$@"
