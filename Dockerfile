FROM node:20-bookworm-slim AS node

ENV TZ=UTC
ENV NODE_ENV=production
WORKDIR /work
COPY ["package.json", "package-lock.json", "gulpfile.js", "swagger.yaml", "/work/"]
RUN npm install


FROM python:3.12-slim AS python

ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get -y update  &&  apt-get -y install --no-install-recommends  \
    build-essential gcc libmariadb-dev-compat pkg-config

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY app/requirements-build.txt /requirements.txt
RUN uv pip install --system --no-cache -r /requirements.txt


FROM python:3.12-slim AS nginx-builder

ENV NGINX_VERSION=1.29.1
ENV RTMP_MODULE_VERSION=master

RUN apt-get -y update && \
    apt-get -y install --no-install-recommends \
        build-essential \
        linux-headers-generic \
        libssl-dev \
        libpcre2-dev \
        git \
        zlib1g-dev \
        curl && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

# Build nginx with RTMP module
WORKDIR /tmp/build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN set -e && \
    curl --proto '=https' -L "https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz" | tar xz && \
    git clone https://github.com/arut/nginx-rtmp-module.git -b "${RTMP_MODULE_VERSION}" && \
    cp ./nginx-rtmp-module/stat.xsl /stat.xsl
WORKDIR /tmp/build/nginx-${NGINX_VERSION}
RUN ./configure \
    --user=nginx \
    --group=nginx \
    --prefix=/etc/nginx \
    --sbin-path=/usr/sbin/nginx \
    --conf-path=/etc/nginx/nginx.conf \
    --pid-path=/var/run/nginx.pid \
    --lock-path=/var/run/nginx.lock \
    --with-http_ssl_module \
    --with-http_v2_module \
    --with-http_gzip_static_module \
    --with-http_secure_link_module \
    --with-threads \
    --with-file-aio \
    --add-module=../nginx-rtmp-module
RUN make -j"$(nproc)" && make install
WORKDIR /tmp/build
RUN rm -rf /tmp/build


FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/django-files/django-files"
LABEL org.opencontainers.image.description="Django Files"
LABEL org.opencontainers.image.authors="smashedr,raluaces"
LABEL org.opencontainers.image.licenses="GPL-3.0"

ARG BUILD_SHA=''
ENV BUILD_SHA=${BUILD_SHA}
RUN touch build_sha && echo "${BUILD_SHA}" > build_sha

ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE=1

COPY --from=node /work/app/static/dist/ /app/static/dist/
COPY --from=python /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=python /usr/local/bin/ /usr/local/bin/
COPY --from=nginx-builder /usr/sbin/nginx /usr/sbin/nginx
COPY --from=nginx-builder /etc/nginx /etc/nginx
COPY --from=nginx-builder /stat.xsl /stat.xsl

RUN apt-get -y update  &&  apt-get -y install --no-install-recommends curl  &&\
    groupadd -g 1000 app  &&  useradd -r -d /app -M -u 1000 -g 1000 -s /usr/sbin/nologin app  &&\
    groupadd -g 101 nginx  &&  useradd -r -d /var/cache/nginx -M -u 101 -g 101 -s /usr/sbin/nologin nginx  &&\
    mkdir -p /app /data/media /data/static /logs  &&  touch /logs/nginx.access  &&\
    chown app:app /app /data/media /data/static /logs /logs/nginx.access  &&\
    apt-get -y install --no-install-recommends libmagic-dev libmariadb-dev-compat  \
        pkg-config redis-server supervisor libssl3 zlib1g  &&\
    apt-get -y remove --auto-remove curl  &&  apt-get -y autoremove  &&\
    apt-get -y clean  &&  rm -rf /var/lib/apt/lists/*

# Create RTMP configuration directories
RUN mkdir -p /etc/nginx/conf.rtmp.d /opt/nginx /tmp/record /tmp/hls &&\
    chown nginx /tmp/record /tmp/hls

COPY nginx/60-sign-secret.sh /docker-entrypoint.d/60-sign-secret.sh
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/raw-mime.types /etc/nginx/raw-mime.types
COPY nginx/record.conf /opt/nginx/
COPY nginx/docker-entrypoint.sh /nginx-entrypoint.sh
COPY docker/redis.conf /etc/redis/redis.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/docker-entrypoint.sh /docker-entrypoint.sh

WORKDIR /app

COPY --chown=app:app app /app

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
ENTRYPOINT ["bash", "/docker-entrypoint.sh"]
