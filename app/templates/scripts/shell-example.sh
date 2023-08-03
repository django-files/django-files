#!/usr/bin/env bash
set -e

_file_name="example-file-name.txt"

_hostname='{{ site_url }}'
_auth='{{ auth }}'
_expire='{{ expire }}'

# Upload to Django Files - Requires: curl
_curl=$(curl -s -m "${_timeout:=10}" -F file=@"${_file_name}"  \
    -H "Content-Type: multipart/form-data"  \
    -H "Authorization: ${_auth}"  \
    -H "ExpiresAt: ${_expire}"  \
    "${_hostname}/upload/")

# Parse URL - Requires: jq
_url=$(echo "${_curl}" | jq -r '.url' | tr -d '\n')
echo "${_url}"

# Copy URL to Clipboard - Requires: xsel
echo "${_url}" | xsel -ib
