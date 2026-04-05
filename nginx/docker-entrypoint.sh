#!/usr/bin/env sh

set -ex

if [ -d /docker-entrypoint.d ]; then
    for _file in /docker-entrypoint.d/*.sh; do
        echo "Sourcing file: ${_file}"
        # shellcheck disable=SC1090
        [ -f "${_file}" ] && . "${_file}"
    done
fi

if [ -n "${RECORD_ENABLED}" ]; then
    echo "RECORD_ENABLED - TRUE - TRUE - TRUE"
    cp /opt/nginx/record.conf /etc/nginx/conf.rtmp.d
else
    echo "RECORD_ENABLED - FALSE - FALSE"
    rm -rf /etc/nginx/conf.rtmp.d/record.conf
fi

exec nginx -g "daemon off;"
