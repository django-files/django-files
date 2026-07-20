FROM node:24-bookworm-slim AS node

ENV TZ=UTC
ENV NODE_ENV=production
WORKDIR /work
COPY ["package.json", "package-lock.json", "gulpfile.js", "swagger.yaml", "/work/"]
RUN npm install


FROM python:3.14-slim AS python

ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get -y update  &&  apt-get -y install --no-install-recommends  \
    build-essential gcc libmariadb-dev-compat pkg-config

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY app/requirements-build.txt /requirements.txt
RUN uv pip install --system --no-cache -r /requirements.txt


FROM ghcr.io/django-files/docker-nginx:1.31.2 AS nginx-base


# The tusproject/tusd:v2 *image* is Alpine/musl-based; its binary needs
# ld-musl-x86_64.so.1, which doesn't exist on this image's Debian/glibc final
# stage, so exec silently fails with "not found" (exit 127) — not a missing
# file, a missing dynamic loader. tusd's GitHub release tarballs are true
# static (CGO_ENABLED=0) binaries, portable to any base — use those instead.
FROM alpine:3 AS tusd-base
ARG TARGETARCH
ARG TUSD_VERSION=v2.10.0
RUN apk add --no-cache curl  &&\
    curl -fsSL -o /tmp/tusd.tar.gz "https://github.com/tus/tusd/releases/download/${TUSD_VERSION}/tusd_linux_${TARGETARCH}.tar.gz"  &&\
    tar -xzf /tmp/tusd.tar.gz -C /tmp  &&\
    mv "/tmp/tusd_linux_${TARGETARCH}/tusd" /usr/local/bin/tusd


FROM python:3.14-slim

LABEL org.opencontainers.image.source="https://github.com/django-files/django-files"
LABEL org.opencontainers.image.description="Django Files"
LABEL org.opencontainers.image.authors="smashedr,raluaces"
LABEL org.opencontainers.image.licenses="GPL-3.0"

ARG BUILD_SHA=''
ENV BUILD_SHA=${BUILD_SHA}
RUN touch build_sha && echo "${BUILD_SHA}" > build_sha

ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE=1
ENV XDG_RUNTIME_DIR=/tmp
# tusd runs as a local supervisord process in this image, not a separate
# container — nginx.conf's tusd upstream must be a literal loopback address
# instead of a hostname (see nginx/60-sign-secret.sh for why).
ENV TUSD_UPSTREAM=127.0.0.1:8080

COPY --from=node /work/app/static/dist/ /app/static/dist/
COPY --from=python /usr/local/lib/python3.14/site-packages/ /usr/local/lib/python3.14/site-packages/
COPY --from=python \
    /usr/local/bin/gunicorn \
    /usr/local/bin/celery \
    /usr/local/bin/uvicorn \
    /usr/local/bin/daphne \
    /usr/local/bin/django-admin \
    /usr/local/bin/httpx \
    /usr/local/bin/qr \
    /usr/local/bin/
COPY --from=nginx-base /usr/sbin/nginx /usr/sbin/nginx
COPY --from=nginx-base /etc/nginx /etc/nginx
COPY --from=nginx-base /stat.xsl /stat.xsl
COPY --from=tusd-base /usr/local/bin/tusd /usr/local/bin/tusd

# Create users before apt installs — redis-server claims GID 101 on Debian trixie if we don't reserve it first
RUN groupadd -g 1000 app  &&  useradd -r -d /app -M -u 1000 -g 1000 -s /usr/sbin/nologin app  &&\
    groupadd -g 101 nginx  &&  useradd -r -d /var/cache/nginx -M -u 101 -g 101 -s /usr/sbin/nologin nginx  &&\
    apt-get -y update  &&\
    apt-get -y install --no-install-recommends \
        libmagic1 libmariadb3 \
        redis-server supervisor libssl3 zlib1g libpcre2-8-0  &&\
    mkdir -p /app /data/media /data/static /logs  &&  touch /logs/nginx.access  &&\
    chown app:app /app /data/media /data/static /logs /logs/nginx.access  &&\
    mkdir -p /etc/nginx/conf.rtmp.d /opt/nginx /tmp/record /tmp/hls  &&\
    chown nginx /tmp/record /tmp/hls  &&\
    apt-get -y clean  &&  rm -rf /var/lib/apt/lists/*

COPY nginx/60-sign-secret.sh /docker-entrypoint.d/60-sign-secret.sh
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/raw-mime.types /etc/nginx/raw-mime.types
COPY nginx/record.conf /opt/nginx/
COPY nginx/docker-entrypoint.sh /nginx-entrypoint.sh
COPY docker/redis.conf /etc/redis/redis.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/docker-entrypoint.sh /docker-entrypoint.sh
COPY docker/tusd-entrypoint.sh /tusd-entrypoint.sh

WORKDIR /app

COPY --chown=app:app app /app

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
ENTRYPOINT ["bash", "/docker-entrypoint.sh"]
