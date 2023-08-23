#!/bin/bash
set -e

# Setup Logging and CWD
_log_file="/tmp/django-files.log"
[[ -n "${_log_file}" ]] && exec > >(tee -a "${_log_file}") 2>&1
_cwd=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Configure Script Variables
_upload_url="{{ site_url }}{% url 'api:upload' %}"
_token="{{ token }}"
#_success="${_cwd}/success.ogg"  # Unset to not use
#_failure="${_cwd}/error.ogg"  # Unset to not use
_timeout="10"  # Upload timeout in seconds
_save_dir="/tmp"  # Temporary directory

# Set Exit Trap
function _exit_trap() {
    _ST="$?"
    if [ "$_ST" == "0" ];then
        if [ -n "${_success}" ];then
            paplay "${_success}"
        fi
    elif [ "$_ST" == "123" ];then
        :
    else
        if [ -n "${_failure}" ];then
            paplay "${_failure}"
        fi
    fi
    exit "${_ST}"
}
trap _exit_trap EXIT HUP INT QUIT PIPE TERM

# Set File Name
_window=$(cat "/proc/$(xdotool getwindowpid $(xdotool getwindowfocus))/comm" | tr -dc '[:alnum:]\n\r')
_title=$(xdotool getactivewindow getwindowname | tr -dc '[:alnum:]\n\r')
_date=$(date "+%F-%T")
_file_name="${_window:0:10}-${_title:0:10}-${_date}.png"

# Capture Screen Shot and Check if Empty (Aborted)
flameshot gui -r > "${_save_dir:=/tmp}/${_file_name}"
if [ ! -s "${_save_dir:=/tmp}/${_file_name}" ];then
    rm -f "${_save_dir:=/tmp}/${_file_name}"
    exit 123
fi

# Upload to Django Files
_curl=$(curl -s -m "${_timeout:=10}" -F file=@"${_save_dir:=/tmp}/${_file_name}" \
    -H "authorization: ${_token}" \
    -H "Content-Type: multipart/form-data" \
    "${_upload_url}" )

# Parse URL and Copy to Clipboard
_url=$(echo "${_curl}" | jq -r '.url' | tr -d '\n')
echo "${_url}" | xsel -ib

# Remove File (Optional)
rm -f "${_save_dir:=/tmp}/${_file_name}"
