#!/usr/bin/env sh

set -e

# The hook secret file already exists by the time supervisord starts it
# (written by nginx/60-sign-secret.sh, which runs in docker-entrypoint.sh
# before `exec "$@"` launches supervisord) — no wait-loop needed here,
# unlike the sidecar wrapper script in the compose stacks.
secret="${TUS_HOOK_SECRET:-$(cat /data/media/db/tus-hook.secret 2>/dev/null)}"
[ -n "$secret" ] || echo "WARNING: no tus hook secret found; the app will reject hook calls"

# -max-size backs up the Django pre-create hook's UPLOAD_MAX_SIZE check
# directly at the transport layer, so an oversized upload is rejected even
# if the hook is ever down or misconfigured. tusd wants raw bytes, not the
# K/M/G suffix nginx/Django accept, so convert here.
upload_max="${UPLOAD_MAX_SIZE:-5G}"
case "${upload_max}" in
    ''|*[!0-9kKmMgG]*) upload_max="5G";;
esac
num=$(echo "${upload_max}" | sed 's/[a-zA-Z]*$//')
case "${upload_max}" in
    *[kK]) bytes=$((num * 1024));;
    *[mM]) bytes=$((num * 1024 * 1024));;
    *[gG]) bytes=$((num * 1024 * 1024 * 1024));;
    *) bytes=${num};;
esac

exec tusd -behind-proxy -host 127.0.0.1 -port 8080 -base-path /tus/ \
    -upload-dir /data/media/tus -max-size "${bytes}" \
    -hooks-http "http://app:9000/api/tus/hook/?secret=${secret}" \
    -hooks-enabled-events pre-create,post-finish
