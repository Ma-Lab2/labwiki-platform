ARG MW_BASE=mediawiki:1.43.6-fpm@sha256:362dea8298d14f018f528b6777d3ae0df1dcd09100ba1349c592d3e41395e280

FROM ${MW_BASE} AS mw-source

USER root

COPY images/mediawiki-app/theme /var/www/html/labwiki/theme
COPY images/mediawiki-app/extensions/PageForms /var/www/html/extensions/PageForms

FROM mw-source AS mw-runtime

RUN if php -m | grep -iq '^apcu$'; then \
      docker-php-ext-enable apcu; \
    else \
      pecl install apcu && docker-php-ext-enable apcu; \
    fi

COPY images/mediawiki-app/php/zz-mediawiki.ini /usr/local/etc/php/conf.d/zz-mediawiki.ini
COPY images/mediawiki-app/entrypoint/bootstrap-instance.sh /usr/local/bin/bootstrap-instance.sh
COPY images/mediawiki-app/seed /opt/labwiki/seed

RUN test -d /var/www/html/extensions/VisualEditor \
    && test -d /var/www/html/extensions/PageForms \
    && chmod +x /usr/local/bin/bootstrap-instance.sh

ENTRYPOINT ["/usr/local/bin/bootstrap-instance.sh"]
CMD ["php-fpm"]

FROM caddy:2 AS caddy-runtime

COPY --from=mw-source /var/www/html /var/www/html
