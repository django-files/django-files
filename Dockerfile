FROM python:3.11-slim as base

ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE 1

RUN apt-get -y update  &&  apt-get -y install --no-install-recommends  \
    build-essential gcc libmariadb-dev-compat pkg-config

COPY app/requirements.txt .
RUN ls -lah
RUN python3 -m pip install --no-cache-dir --upgrade pip  &&\
    python3 -m pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/django-files/django-files"
LABEL org.opencontainers.image.description="Django Files"
LABEL org.opencontainers.image.authors="smashedr,raluaces"
LABEL org.opencontainers.image.licenses="GPL-3.0"

ENV TZ=UTC
ENV PYTHONUNBUFFERED 1

COPY --from=base /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=base /usr/local/bin/ /usr/local/bin/

RUN apt-get -y update  &&  apt-get -y install --no-install-recommends curl  &&\
    curl -1sLf 'https://repositories.timber.io/public/vector/cfg/setup/bash.deb.sh' | bash  &&\
    groupadd -g 1000 app  &&  useradd -r -d /app -M -u 1000 -g 1000 -G video -s /usr/sbin/nologin app  &&\
    mkdir -p /app /data/media /data/static /logs  &&  touch /logs/nginx.access  &&\
    chown app:app /app /data/media /data/static /logs /logs/nginx.access  &&\
    apt-get -y install --no-install-recommends libmariadb-dev-compat pkg-config  \
        supervisor nginx redis-server vector  &&\
    apt-get -y remove --auto-remove curl  &&  apt-get -y autoremove  &&\
    apt-get -y clean  &&  rm -rf /var/lib/apt/lists/*

COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/mime.types /etc/nginx/raw-mime.types
COPY vector/vector.toml /etc/vector/vector.toml
COPY docker/redis.conf /etc/redis/redis.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY --chmod=0755 docker/docker-entrypoint.sh /docker-entrypoint.sh

COPY --chown=app:app . .

CMD ["/usr/bin/supervisord"]
ENTRYPOINT ["bash", "/docker-entrypoint.sh"]
