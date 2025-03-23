FROM nginx:alpine-slim

ENV TZ=UTC

COPY nginx.conf /etc/nginx/nginx.conf
COPY raw-mime.types /etc/nginx/raw-mime.types

COPY --chmod=0755 60-sign-secret.sh /docker-entrypoint.d/60-sign-secret.sh
