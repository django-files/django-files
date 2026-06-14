FROM node:24-bookworm-slim AS node

ENV TZ=UTC
ENV NODE_ENV=production
WORKDIR /work
COPY ["package.json", "package-lock.json", "gulpfile.js", "swagger.yaml", "/work/"]
RUN npm install


FROM python:3.14-alpine AS python

ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE=1

RUN apk add --update --no-cache alpine-sdk gcc libffi-dev musl-dev mysql-dev

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY app/requirements.txt /
RUN uv pip install --system --no-cache -r /requirements.txt


FROM python:3.14-alpine

ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE=1

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

RUN addgroup -g 1000 app  &&\
    adduser -S -H -h /app -s /sbin/nologin -u 1000 -G app app  &&\
    mkdir -p /app /data/media/db /data/media/files /data/static /logs  &&  touch /logs/nginx.access  &&\
    chown app:app /app /data/media/db /data/media/files /data/static /logs /logs/nginx.access  &&\
    apk add --no-cache curl libmagic mailcap mysql-dev

ARG BUILD_SHA=''
ENV BUILD_SHA=${BUILD_SHA}
RUN touch build_sha && echo "${BUILD_SHA}" > build_sha

WORKDIR /app
COPY --chmod=555 --chown=root:root app/ .
USER app
ENTRYPOINT ["sh", "docker-entrypoint.sh"]
