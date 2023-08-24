#!/usr/bin/env sh

set -ex


echo "----- APP ENTRYPOINT DEBUG - REMOVE -----"
pwd
ls -lah
if [ -f "/.env" ];then
    echo "----- SOURCE /.env -----"
    set -a
    . /.env
fi
echo "----- APP ENTRYPOINT DEBUG - REMOVE -----"

# Create /data/media directories for mount

if [ ! -d "/data/media/files" ];then
    echo "Creating Directory: /data/media/files"
    mkdir "/data/media/files"
fi

if [ ! -d "/data/media/db" ];then
    echo "Creating Directory: /data/media/db"
    mkdir "/data/media/db"
fi

if [ ! -d "/data/media/redis" ];then
    echo "Creating Directory: /data/media/redis"
    mkdir "/data/media/redis"
fi

echo "127.0.0.1 app redis" >> /etc/hosts

exec "$@"
