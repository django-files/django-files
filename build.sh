#!/usr/bin/env bash
set -e

REGISTRY_HOST="ghcr.io"
REGISTRY_USER="django-files"
REGISTRY_REPO="django-files"

#if [ -f ".env" ];then
#    echo "Sourcing Environment: .env"
#    source ".env"
#fi

if [ -z "${VERSION}" ];then
    if [ -z "${1}" ];then
        VERSION="latest"
#        read -rp "Version: [latest] " VERSION
#        if [ -z "${VERSION}" ];then
#            VERSION="latest"
#        fi
    else
        VERSION="${1}"
    fi
fi

#if [ -z "${USERNAME}" ];then
#    read -rp "Username: " USERNAME
#fi
#if [ -z "${PASSWORD}" ];then
#    read -rp "Password: " PASSWORD
#fi

echo "Building: ${REGISTRY_HOST}/${REGISTRY_USER}/${REGISTRY_REPO}:${VERSION}"
#read -p "Proceed? (enter) "

#docker login --username "${USERNAME}" --password "${PASSWORD}" "${REGISTRY_HOST}"

docker build -t "${REGISTRY_HOST}/${REGISTRY_USER}/${REGISTRY_REPO}:${VERSION}" .
#docker push "${REGISTRY_HOST}/${REGISTRY_USER}/${REGISTRY_REPO}:${VERSION}"

#docker buildx create --use
#docker buildx build --platform linux/amd64,linux/arm64 --push  \
#    -t "${REGISTRY_HOST}/${REGISTRY_USER}/${REGISTRY_REPO}:${VERSION}" .
