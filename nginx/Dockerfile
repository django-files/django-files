FROM nginx:alpine-slim

ENV TZ=UTC

COPY nginx.conf /etc/nginx/nginx.conf
COPY mime.types /etc/nginx/raw-mime.types

COPY --chmod=0755 99-sign-secret.sh /docker-entrypoint.d/99-sign-secret.sh
