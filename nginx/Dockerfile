FROM alpine:latest

ENV NGINX_VERSION=1.25.3
ENV RTMP_MODULE_VERSION=master
ENV TZ=UTC

RUN apk add --no-cache \
    build-base \
    curl \
    linux-headers \
    openssl-dev \
    git \
    pcre-dev \
    zlib-dev

WORKDIR /tmp/build
RUN curl --proto '=https' -L https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz | tar xz &&\
    git clone https://github.com/arut/nginx-rtmp-module.git -b ${RTMP_MODULE_VERSION} &&\
    cp ./nginx-rtmp-module/stat.xsl /stat.xsl &&\
    cd nginx-${NGINX_VERSION} &&\
    ./configure \
        --user=nginx \
        --group=nginx \
        --prefix=/etc/nginx \
        --sbin-path=/usr/sbin/nginx \
        --conf-path=/etc/nginx/nginx.conf \
        --error-log-path=/var/log/nginx/error.log \
        --http-log-path=/var/log/nginx/access.log \
        --pid-path=/var/run/nginx.pid \
        --lock-path=/var/run/nginx.lock \
        --with-http_ssl_module \
        --with-http_v2_module \
        --with-http_gzip_static_module \
        --with-http_secure_link_module \
        --with-threads \
        --with-file-aio \
        --add-module=../nginx-rtmp-module &&\
    make -j$(nproc) && make install && rm -rf /tmp/build

RUN mkdir -p /etc/nginx/conf.rtmp.d /opt/nginx /tmp/record &&\
    addgroup nginx && adduser -S nginx -G nginx && chown nginx /tmp/record

COPY record.conf /opt/nginx
COPY nginx.conf raw-mime.types /etc/nginx/
COPY --chmod=0755 60-sign-secret.sh /docker-entrypoint.d/60-sign-secret.sh

STOPSIGNAL SIGTERM

WORKDIR /
COPY --chmod=0755 docker-entrypoint.sh /docker-entrypoint.sh
#USER nginx
ENTRYPOINT ["sh", "docker-entrypoint.sh"]
