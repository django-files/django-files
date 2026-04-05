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

COPY app/requirements-build.txt /requirements.txt
RUN python3 -m pip install --no-cache-dir -U pip  &&\
    python3 -m pip install --no-cache-dir -r /requirements.txt


FROM ghcr.io/django-files/docker-nginx:1.29.7 AS nginx-base


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
COPY --from=nginx-base /usr/sbin/nginx /usr/sbin/nginx
COPY --from=nginx-base /etc/nginx /etc/nginx
COPY --from=nginx-base /stat.xsl /stat.xsl

RUN apt-get -y update  &&  apt-get -y install --no-install-recommends curl  &&\
    groupadd -g 1000 app  &&  useradd -r -d /app -M -u 1000 -g 1000 -s /usr/sbin/nologin app  &&\
    groupadd -g 101 nginx  &&  useradd -r -d /var/cache/nginx -M -u 101 -g 101 -s /usr/sbin/nologin nginx  &&\
    mkdir -p /app /data/media /data/static /logs  &&  touch /logs/nginx.access  &&\
    chown app:app /app /data/media /data/static /logs /logs/nginx.access  &&\
    apt-get -y install --no-install-recommends libmagic-dev libmariadb-dev-compat  \
        pkg-config redis-server supervisor libssl3 zlib1g libpcre2-8-0  &&\
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
