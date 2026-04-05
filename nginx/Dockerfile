FROM ghcr.io/django-files/docker-nginx:latest

COPY record.conf /opt/nginx/
COPY nginx.conf raw-mime.types /etc/nginx/
COPY --chmod=0755 60-sign-secret.sh /docker-entrypoint.d/60-sign-secret.sh

STOPSIGNAL SIGTERM

WORKDIR /
COPY --chmod=0755 docker-entrypoint.sh /docker-entrypoint.sh
ENTRYPOINT ["sh", "/docker-entrypoint.sh"]
