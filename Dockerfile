FROM python:3.11-slim as base

ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE 1

RUN apt-get -y update && apt-get -y install build-essential gcc libmariadb-dev-compat pkg-config

COPY app/requirements.txt .
RUN ls -lah
RUN python3 -m pip install --no-cache-dir --upgrade pip  &&\
    python3 -m pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim

ENV TZ=UTC
ENV PYTHONUNBUFFERED 1

COPY --from=base /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=base /usr/local/bin/ /usr/local/bin/

RUN groupadd -g 1000 app  &&\
    useradd -r -d /app -M -u 1000 -g 1000 -G video -s /usr/sbin/nologin app  &&\
    mkdir -p /app /data/media/db /data/media/files /data/static /logs  &&  touch /logs/nginx.access  &&\
    chown app:app /app /data/media/db /data/media/files /data/static /logs /logs/nginx.access  &&\
    apt-get -y update  &&  apt-get -y install libmariadb-dev-compat pkg-config curl  &&\
    apt-get -y clean  &&  rm -rf /var/lib/apt/lists/*

RUN curl -1sLf 'https://repositories.timber.io/public/vector/cfg/setup/bash.deb.sh' | bash
RUN apt-get update && apt-get install -y supervisor nginx redis-server vector

COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY nginx/mime.types /etc/nginx/raw-mime.types
COPY vector/vector.toml /etc/vector/vector.toml
COPY docker/redis.conf /etc/redis/redis.conf

COPY --chown=app:app . .

CMD ["/usr/bin/supervisord"]

#COPY docker/docker-entrypoint.sh /docker-entrypoint.sh
#ENTRYPOINT ["sh", "docker-entrypoint.sh"]

#WORKDIR /app
#COPY --chown=app:app . .
#USER app
#ENTRYPOINT ["sh", "docker-entrypoint.sh"]
