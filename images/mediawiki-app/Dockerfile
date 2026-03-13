ARG MW_BASE=mediawiki:1.43.6-fpm@sha256:362dea8298d14f018f528b6777d3ae0df1dcd09100ba1349c592d3e41395e280
ARG VISUALEDITOR_REF=3de88ce69e0b43d1565b5fc21adbe506fa71f78f

FROM ${MW_BASE} AS mw-source

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --filter=blob:none --no-checkout https://gerrit.wikimedia.org/r/mediawiki/extensions/VisualEditor.git /var/www/html/extensions/VisualEditor \
    && git -C /var/www/html/extensions/VisualEditor checkout "${VISUALEDITOR_REF}" \
    && git -C /var/www/html/extensions/VisualEditor submodule update --init --recursive --depth 1

FROM mw-source AS mw-runtime

RUN pecl install apcu \
    && docker-php-ext-enable apcu

COPY php/zz-mediawiki.ini /usr/local/etc/php/conf.d/zz-mediawiki.ini
COPY entrypoint/bootstrap-instance.sh /usr/local/bin/bootstrap-instance.sh

RUN test -d /var/www/html/extensions/VisualEditor \
    && chmod +x /usr/local/bin/bootstrap-instance.sh

ENTRYPOINT ["/usr/local/bin/bootstrap-instance.sh"]
CMD ["php-fpm"]

FROM caddy:2 AS caddy-runtime

COPY --from=mw-source /var/www/html /var/www/html
