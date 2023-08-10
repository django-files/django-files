FROM nginx:alpine-slim

ENV TZ=UTC

RUN addgroup -g 1000 app  &&\
    adduser -S -H -h /app -s /sbin/nologin -u 1000 -G app app  &&\
    mkdir -p /logs  &&\
    touch /logs/nginx.access  &&\
    chown app:app /logs /logs/nginx.access

COPY nginx.conf /etc/nginx/nginx.conf
