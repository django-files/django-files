#!/usr/bin/env sh

set -ex

echo "127.0.0.1 app redis" >> /etc/hosts

exec "$@"
