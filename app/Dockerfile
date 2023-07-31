FROM python:3.11-alpine as base

ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE 1

RUN apk add --update --no-cache alpine-sdk mysql-dev

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --upgrade pip  &&\
    python3 -m pip install --no-cache-dir -r requirements.txt


FROM python:3.11-alpine

ENV TZ=UTC
ENV PYTHONUNBUFFERED 1

COPY --from=base /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=base /usr/local/bin/ /usr/local/bin/

RUN addgroup -g 1000 app  &&\
    adduser -S -H -h /app -s /sbin/nologin -u 1000 -G app app  &&\
    mkdir -p /app /data  &&  chown app:app /app /data  &&\
    apk add --no-cache curl mysql-dev

WORKDIR /app
COPY --chown=app:app . .
USER app
ENTRYPOINT ["sh", "docker-entrypoint.sh"]
