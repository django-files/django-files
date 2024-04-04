FROM node:20-bookworm-slim AS node

ENV TZ=UTC
ENV NODE_ENV=production
WORKDIR /work
COPY ["package.json", "package-lock.json", "gulpfile.js", "swagger.yaml", "/work/"]
RUN npm install


FROM python:3.11-slim AS python

ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE 1

RUN apt-get -y update  &&  apt-get -y install --no-install-recommends  \
    build-essential gcc libmariadb-dev-compat pkg-config

COPY app/requirements-build.txt requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade pip  &&\
    python3 -m pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/django-files/django-files"
LABEL org.opencontainers.image.description="Django Files"
LABEL org.opencontainers.image.authors="smashedr,raluaces"
LABEL org.opencontainers.image.licenses="GPL-3.0"

ENV TZ=UTC
ENV PYTHONUNBUFFERED 1

COPY --from=node /work/app/static/dist/ /app/static/dist/
COPY --from=python /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=python /usr/local/bin/ /usr/local/bin/

RUN apt-get -y update  &&  apt-get -y install --no-install-recommends curl  &&\
    curl --proto '=https' --tlsv1.2 -sSfL https://sh.vector.dev | VECTOR_VERSION=0.33.0 bash -s -- -y &&\
    groupadd -g 1000 app  &&  useradd -r -d /app -M -u 1000 -g 1000 -s /usr/sbin/nologin app  &&\
    groupadd -g 101 nginx  &&  useradd -r -d /var/cache/nginx -M -u 101 -g 101 -s /usr/sbin/nologin nginx  &&\
    mkdir -p /app /data/media /data/static /logs  &&  touch /logs/nginx.access  &&\
    chown app:app /app /data/media /data/static /logs /logs/nginx.access  &&\
    apt-get -y install --no-install-recommends libmariadb-dev-compat pkg-config libmagic-dev  \
        supervisor nginx redis-server &&\
    apt-get -y remove --auto-remove curl  &&  apt-get -y autoremove  &&\
    apt-get -y clean  &&  rm -rf /var/lib/apt/lists/*

COPY nginx/60-sign-secret.sh /docker-entrypoint.d/60-sign-secret.sh
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/mime.types /etc/nginx/raw-mime.types
COPY vector/vector.toml /etc/vector/vector.toml
COPY docker/redis.conf /etc/redis/redis.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/docker-entrypoint.sh /docker-entrypoint.sh

COPY --chown=app:app app app

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
ENTRYPOINT ["bash", "/docker-entrypoint.sh"]
