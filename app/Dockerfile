FROM python:3.11-alpine AS python

ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE 1

RUN apk add --update --no-cache alpine-sdk mysql-dev gcc libffi-dev musl-dev

#RUN apt-get -y update && apt-get -y install build-essential libmariadb-dev-compat

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --upgrade pip  &&\
    python3 -m pip install --no-cache-dir -r requirements.txt


FROM python:3.11-alpine

ENV TZ=UTC
ENV PYTHONUNBUFFERED 1

COPY --from=python /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=python /usr/local/bin/ /usr/local/bin/

RUN addgroup -g 1000 app  &&\
    adduser -S -H -h /app -s /sbin/nologin -u 1000 -G app app  &&\
    mkdir -p /app /data/media/db /data/media/files /data/static /logs  &&  touch /logs/nginx.access  &&\
    chown app:app /app /data/media/db /data/media/files /data/static /logs /logs/nginx.access  &&\
    apk add --no-cache curl mysql-dev mailcap libmagic
#    mkdir -p /app /data/media/db /data/media/files /data/static  &&\
#    chown app:app /app /data/media/db /data/media/files /data/static  &&\
#    apk add --no-cache curl mysql-dev mailcap

#RUN groupadd -g 1000 app  &&\
#    useradd -r -d /app -M -u 1000 -g 1000 -G video -s /usr/sbin/nologin app  &&\
#    mkdir -p /app /data/media/db /data/media/files /data/static  &&\
#    chown app:app /app /data/media/db /data/media/files /data/static  &&\
#    apt-get -y update  &&  apt-get -y install gcc libmariadb-dev-compat pkg-config  &&\
#    apt-get -y clean  &&  rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --chown=app:app . .
USER app
ENTRYPOINT ["sh", "docker-entrypoint.sh"]
