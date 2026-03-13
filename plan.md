`PLAN.md` 全文。  
这版是按你前面确认的 **MediaWiki Docker V3 最佳实践基线** 来写的：当前官方支持版本里，`1.45.1` 是 stable，`1.43.6` 是 LTS；MediaWiki 需要 PHP 8.2+，并推荐 MariaDB/MySQL。官方还明确区分了两条 Docker 路线：**MediaWiki-Docker 是开发环境**，而 Docker Hub 上的 `mediawiki` 官方镜像更适合拿来**扩展成自定义环境，也可用于生产**。对于“公开内容 + 内部内容”并存的场景，官方对细粒度访问控制很谨慎，明确列出了 **separate wikis** 作为更稳妥的方案；同时也提醒，关闭匿名 `read` 只会限制 wiki 页面，**上传文件默认仍可能通过直链访问**。`install` 脚本支持 `--confpath`、`--dbpassfile`、`--passfile`；`LocalSettings.php` 需要重点保护；性能 quick start 推荐 bytecode cache、APCu、本地/主缓存；Docker Compose 则支持 secrets 和 `service_healthy` 启动依赖。([MediaWiki](https://www.mediawiki.org/wiki/Download/en "Download - MediaWiki"))

* * *

PLAN.md
=======

MediaWiki 课题组网站 / 内部知识库
-----------------------

Docker Compose V3 实施计划（Codex 执行版）
---------------------------------

1. 项目目标

-------

为课题组建设一套 **可长期维护的 MediaWiki 平台**，采用 **双 Wiki 分离架构**：

* **公开站（public wiki）**
  
  * 课题组简介
  
  * 成员介绍
  
  * 论文成果
  
  * 新闻动态
  
  * 装置平台简介
  
  * 招生/合作信息

* **内部站（private wiki）**
  
  * SOP
  
  * 实验记录
  
  * 组会纪要
  
  * 项目页面
  
  * 设备使用规范
  
  * 内部知识沉淀

本项目目标不是搭一个“能打开”的 demo，而是形成一套：

* 一键部署

* 幂等初始化

* 可升级

* 可备份

* 可恢复

* 可扩展（后续加 Cargo / Page Forms / LDAP）

* 安全边界明确

的 **单机生产基线**。

* * *

2. 设计原则

-------

### 2.1 双 Wiki 分离，而不是单 Wiki 强行做公开/私有混合

本项目默认使用：

* `lab.example.com` → public wiki

* `wiki.lab.internal` 或 `wiki.lab.example.com` → private wiki

原因：

1. MediaWiki 官方对细粒度查看权限长期持谨慎态度。

2. 官方明确列出 **separate wikis** 作为更稳妥的方案之一。

3. 单 Wiki 靠命名空间权限或第三方扩展切公开/私有，长期风险更高。

4. 上传文件的访问控制与页面访问控制不是同一层。([MediaWiki](https://www.mediawiki.org/wiki/Manual%3APreventing_access "Manual:Preventing access - MediaWiki"))

### 2.2 使用 Docker Hub 的 `mediawiki` 官方镜像做自定义镜像

不使用 MediaWiki-Docker 作为生产方案。

原因：

* **MediaWiki-Docker** 是开发环境，不是第三方生产镜像。

* **Docker Hub 的 `mediawiki` 镜像** 被官方文档描述为适合设计自定义环境，也可用于生产。

* 官方还明确说该镜像是极简基础镜像，**更适合“extended from”**，而不是直接拿来当最终形态。([MediaWiki](https://www.mediawiki.org/wiki/MediaWiki-Docker "MediaWiki-Docker - MediaWiki"))

### 2.3 密钥不放 `.env` 明文

所有真正敏感的信息走 `secrets/` 文件：

* 数据库 root 密码

* public DB 密码

* private DB 密码

* public 管理员密码

* private 管理员密码

Compose secrets 会把密钥挂到 `/run/secrets/<name>`。([Docker Documentation](https://docs.docker.com/compose/how-tos/use-secrets/ "Secrets in Compose | Docker Docs"))

### 2.4 使用 healthcheck + `service_healthy`

数据库 ready 不能只靠“容器已启动”。  
所有关键依赖都要显式声明健康检查，MediaWiki 容器在数据库 healthy 后再初始化。([Docker Documentation](https://docs.docker.com/compose/how-tos/startup-order/ "Control startup order | Docker Docs"))

### 2.5 镜像版本固定到 digest

Dockerfile 必须 pin 到：
    FROM mediawiki:1.43.6-fpm@sha256:<REAL_DIGEST>

理由：

* 标签是 mutable 的。

* digest pin 更有利于复现、审计和回滚。([Docker Documentation](https://docs.docker.com/build/building/best-practices/ "Best practices | Docker Docs"))

### 2.6 private wiki 默认不直接公网暴露

推荐策略：

* public wiki 正常 80/443 暴露

* private wiki 默认只绑定本机回环地址，交给 VPN / 校园网 / SSH 隧道 / 内网反代使用

理由：

* 即使 `read=false`，默认也**不能自动保护上传文件直链**。

* 对敏感实验资料，网络暴露面应尽可能缩小。([MediaWiki](https://www.mediawiki.org/wiki/Manual%3APreventing_access "Manual:Preventing access - MediaWiki"))

* * *

3. 版本基线

-------

### 3.1 MediaWiki 版本

默认使用：

* **MediaWiki 1.43.6 LTS**

原因：

* 课题组场景重稳定，不追最新 feature。

* 当前官方支持版本中，`1.43.6` 是 LTS，适合长期维护。([MediaWiki](https://www.mediawiki.org/wiki/Download/en "Download - MediaWiki"))

### 3.2 运行时

* PHP 8.2+

* MariaDB 10.3+（建议 MariaDB 11.x 容器）

* Docker Compose

* Caddy 2 作为反向代理

MediaWiki 官方下载页当前要求 PHP 8.2+，并推荐 MariaDB/MySQL。([MediaWiki](https://www.mediawiki.org/wiki/Download/en "Download - MediaWiki"))

* * *

4. 目标架构

-------

    Internet
       │
       ▼
    Caddy Public (80/443)
       │
       └── mw_public (MediaWiki, FPM)
             │
             └── MariaDB (public_db)
    
    Private Access Path
       │
       ▼
    Caddy Private (127.0.0.1:8443 only)
       │
       └── mw_private (MediaWiki, FPM)
             │
             └── MariaDB (private_db)
    
    Shared:
    - One MariaDB container
    - Two separate DBs
    - Two separate LocalSettings.php
    - Two separate uploads directories
    - One custom MediaWiki app image

* * *

5. 仓库目录结构

---------

    labwiki/
    ├─ compose.yaml
    ├─ compose.override.yaml
    ├─ .env.example
    ├─ .gitignore
    ├─ README.md
    ├─ secrets/
    │  ├─ db_root_password.txt
    │  ├─ public_db_password.txt
    │  ├─ private_db_password.txt
    │  ├─ public_admin_password.txt
    │  └─ private_admin_password.txt
    ├─ images/
    │  └─ mediawiki-app/
    │     ├─ Dockerfile
    │     ├─ php/
    │     │  └─ zz-mediawiki.ini
    │     └─ entrypoint/
    │        └─ bootstrap-instance.sh
    ├─ ops/
    │  ├─ caddy/
    │  │  ├─ Caddyfile.public
    │  │  └─ Caddyfile.private
    │  ├─ db-init/
    │  │  └─ 01-create-wikis.sh
    │  └─ scripts/
    │     ├─ backup.sh
    │     ├─ restore.sh
    │     ├─ upgrade.sh
    │     └─ smoke-test.sh
    ├─ state/
    │  ├─ public/
    │  │  └─ LocalSettings.php
    │  └─ private/
    │     └─ LocalSettings.php
    ├─ uploads/
    │  ├─ public/
    │  └─ private/
    └─ backups/

* * *

6. 交付物清单

--------

Codex 最终必须产出：

1. `compose.yaml`

2. `compose.override.yaml`

3. `.env.example`

4. `.gitignore`

5. `README.md`

6. `images/mediawiki-app/Dockerfile`

7. `images/mediawiki-app/php/zz-mediawiki.ini`

8. `images/mediawiki-app/entrypoint/bootstrap-instance.sh`

9. `ops/caddy/Caddyfile.public`

10. `ops/caddy/Caddyfile.private`

11. `ops/db-init/01-create-wikis.sh`

12. `ops/scripts/backup.sh`

13. `ops/scripts/restore.sh`

14. `ops/scripts/upgrade.sh`

15. `ops/scripts/smoke-test.sh`

* * *

7. Compose 设计要求

---------------

7.1 服务清单
--------

必须包含这些服务：

* `mariadb`

* `mw_public`

* `mw_private`

* `caddy_public`

* `caddy_private`

可选保留扩展位，但 V3 默认不强制：

* `memcached`

* `redis`

* `watchtower`

* `backup-cron`

7.2 存储要求
--------

必须持久化：

* `/var/lib/mysql`

* `/var/www/html/images`（public/private 各自独立）

* `/state/LocalSettings.php`

* Caddy 证书/配置（至少 public）

不允许把 `LocalSettings.php` 留在“只存在于容器层”的状态。  
`LocalSettings.php` 含数据库凭据，必须被视为敏感配置文件。([MediaWiki](https://www.mediawiki.org/wiki/Manual%3ALocalSettings.php "Manual:LocalSettings.php - MediaWiki"))
7.3 依赖关系
--------

* `mw_public` 依赖 `mariadb: service_healthy`

* `mw_private` 依赖 `mariadb: service_healthy`

* `caddy_public` 依赖 `mw_public: service_healthy`

* `caddy_private` 依赖 `mw_private: service_healthy`

7.4 网络暴露策略
----------

* `caddy_public`：`80:80`、`443:443`

* `caddy_private`：默认 `127.0.0.1:8443:443`

private wiki 不应默认对公网开放。
7.5 日志策略
--------

建议在 Compose 中为主要服务配置：
    logging:
      driver: local

避免默认日志无限膨胀。

* * *

8. `compose.yaml` 参考骨架

----------------------

    services:
      mariadb:
        image: mariadb:11.4
        restart: unless-stopped
        command:
          - --character-set-server=utf8mb4
          - --collation-server=utf8mb4_unicode_ci
          - --binlog-format=ROW
        secrets:
          - db_root_password
        environment:
          MARIADB_ROOT_PASSWORD_FILE: /run/secrets/db_root_password
        volumes:
          - db_data:/var/lib/mysql
          - ./ops/db-init:/docker-entrypoint-initdb.d:ro
        healthcheck:
          test: ["CMD-SHELL", "mariadb-admin ping -uroot -p$$(cat /run/secrets/db_root_password) --silent"]
          interval: 10s
          timeout: 5s
          retries: 12
        logging:
          driver: local
    
      mw_public:
        build:
          context: ./images/mediawiki-app
        restart: unless-stopped
        depends_on:
          mariadb:
            condition: service_healthy
        secrets:
          - public_db_password
          - public_admin_password
        environment:
          MW_DB_NAME: labwiki_public
          MW_DB_USER: labwiki_public_user
          MW_DB_PASS_FILE: /run/secrets/public_db_password
          MW_ADMIN_USER: admin
          MW_ADMIN_PASS_FILE: /run/secrets/public_admin_password
          MW_SERVER: https://lab.example.com
          MW_SITE_NAME: Lab Public Wiki
          MW_LANG: zh-cn
        volumes:
          - ./state/public:/state
          - ./uploads/public:/var/www/html/images
        healthcheck:
          test: ["CMD-SHELL", "php-fpm -t && test -s /state/LocalSettings.php"]
          interval: 20s
          timeout: 5s
          retries: 6
        logging:
          driver: local
    
      mw_private:
        build:
          context: ./images/mediawiki-app
        restart: unless-stopped
        depends_on:
          mariadb:
            condition: service_healthy
        secrets:
          - private_db_password
          - private_admin_password
        environment:
          MW_DB_NAME: labwiki_private
          MW_DB_USER: labwiki_private_user
          MW_DB_PASS_FILE: /run/secrets/private_db_password
          MW_ADMIN_USER: admin
          MW_ADMIN_PASS_FILE: /run/secrets/private_admin_password
          MW_SERVER: https://wiki.lab.internal
          MW_SITE_NAME: Lab Internal Wiki
          MW_LANG: zh-cn
          MW_PRIVATE_MODE: "true"
        volumes:
          - ./state/private:/state
          - ./uploads/private:/var/www/html/images
        healthcheck:
          test: ["CMD-SHELL", "php-fpm -t && test -s /state/LocalSettings.php"]
          interval: 20s
          timeout: 5s
          retries: 6
        logging:
          driver: local
    
      caddy_public:
        image: caddy:2
        restart: unless-stopped
        depends_on:
          mw_public:
            condition: service_healthy
        ports:
          - "80:80"
          - "443:443"
        volumes:
          - ./ops/caddy/Caddyfile.public:/etc/caddy/Caddyfile:ro
          - caddy_public_data:/data
          - caddy_public_config:/config
        logging:
          driver: local
    
      caddy_private:
        image: caddy:2
        restart: unless-stopped
        depends_on:
          mw_private:
            condition: service_healthy
        ports:
          - "127.0.0.1:8443:443"
        volumes:
          - ./ops/caddy/Caddyfile.private:/etc/caddy/Caddyfile:ro
        logging:
          driver: local
    
    secrets:
      db_root_password:
        file: ./secrets/db_root_password.txt
      public_db_password:
        file: ./secrets/public_db_password.txt
      private_db_password:
        file: ./secrets/private_db_password.txt
      public_admin_password:
        file: ./secrets/public_admin_password.txt
      private_admin_password:
        file: ./secrets/private_admin_password.txt
    
    volumes:
      db_data:
      caddy_public_data:
      caddy_public_config:

* * *

9. 自定义镜像要求

----------

9.1 Dockerfile
--------------

必须基于 `mediawiki:1.43.6-fpm@sha256:<REAL_DIGEST>` 构建。  
不要使用 `latest`。  
不要直接用无 digest 的 `mediawiki:1.43.6-fpm` 作为最终提交版本。([Docker Documentation](https://docs.docker.com/build/building/best-practices/ "Best practices | Docker Docs"))

参考：
    FROM mediawiki:1.43.6-fpm@sha256:<REAL_DIGEST>

    RUN pecl install apcu \
        && docker-php-ext-enable apcu

    COPY php/zz-mediawiki.ini /usr/local/etc/php/conf.d/zz-mediawiki.ini
    COPY entrypoint/bootstrap-instance.sh /usr/local/bin/bootstrap-instance.sh

    RUN chmod +x /usr/local/bin/bootstrap-instance.sh

    ENTRYPOINT ["/usr/local/bin/bootstrap-instance.sh"]
    CMD ["php-fpm"]
9.2 PHP 配置文件 `zz-mediawiki.ini`
-------------------------------

至少包含：
    memory_limit=512M
    upload_max_filesize=64M
    post_max_size=64M
    max_execution_time=120

    opcache.enable=1
    opcache.memory_consumption=192
    opcache.interned_strings_buffer=16
    opcache.max_accelerated_files=20000
    opcache.validate_timestamps=1

    apc.enabled=1

MediaWiki 性能 quick start 推荐 bytecode cache 和 APCu；对 PHP 7+，官方明确建议 APCu。([MediaWiki](https://www.mediawiki.org/wiki/Manual%3APerformance_tuning "Manual:Performance tuning - MediaWiki"))

* * *

10. MariaDB 初始化要求

-----------------

`ops/db-init/01-create-wikis.sh` 负责：

* 创建 `labwiki_public`

* 创建 `labwiki_private`

* 创建各自独立数据库用户

* 分配最小所需权限

参考逻辑：
    #!/usr/bin/env bash
    set -euo pipefail

    ROOT_PASS="$(cat /run/secrets/db_root_password)"
    PUBLIC_PASS="$(cat /run/secrets/public_db_password)"
    PRIVATE_PASS="$(cat /run/secrets/private_db_password)"

    mariadb -uroot -p"${ROOT_PASS}" <<SQL
    CREATE DATABASE IF NOT EXISTS \`labwiki_public\`
      CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

    CREATE DATABASE IF NOT EXISTS \`labwiki_private\`
      CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

    CREATE USER IF NOT EXISTS 'labwiki_public_user'@'%' IDENTIFIED BY '${PUBLIC_PASS}';
    CREATE USER IF NOT EXISTS 'labwiki_private_user'@'%' IDENTIFIED BY '${PRIVATE_PASS}';

    GRANT ALL PRIVILEGES ON \`labwiki_public\`.* TO 'labwiki_public_user'@'%';
    GRANT ALL PRIVILEGES ON \`labwiki_private\`.* TO 'labwiki_private_user'@'%';

    FLUSH PRIVILEGES;
    SQL

实现时需要解决一个工程问题：  
`docker-entrypoint-initdb.d` 脚本默认只会拿到容器环境和挂载文件。Codex 需确保 secrets 在该脚本可读，或改为在 `backup/restore/bootstrap` 统一阶段完成 DB 初始化。只要**最终流程幂等、可复现**即可。

* * *

11. MediaWiki 实例启动与初始化要求

------------------------

11.1 统一入口脚本
-----------

`bootstrap-instance.sh` 必须成为两个 wiki 实例的统一入口脚本。

职责：

1. 检查 `/state/LocalSettings.php` 是否存在且非空

2. 若不存在：
   
   * 调用 `php maintenance/run.php install`
   
   * 使用 `--confpath=/state`
   
   * 使用 `--dbpassfile`
   
   * 使用 `--passfile`

3. 追加实例级基础配置

4. 软链接 `/state/LocalSettings.php` → `/var/www/html/LocalSettings.php`

5. 启动 `php-fpm`

官方 `install` 脚本支持 `--confpath`、`--dbpassfile`、`--passfile`；并且如果根目录已存在 `LocalSettings.php`，会影响生成逻辑，因此应先写到 `/state` 再回链。([MediaWiki](https://www.mediawiki.org/wiki/Manual%3AInstall.php "Manual:install.php - MediaWiki"))
11.2 脚本幂等要求
-----------

重复执行容器启动时：

* 不应重复安装数据库

* 不应覆盖已有 `LocalSettings.php`

* 不应重复追加同一段配置

* 不应因存在软链接而报错退出

11.3 参考入口脚本
-----------

    #!/usr/bin/env bash
    set -euo pipefail
    
    if [ ! -s /state/LocalSettings.php ]; then
      php maintenance/run.php install \
        --confpath=/state \
        --dbtype=mysql \
        --dbserver=mariadb \
        --dbname="${MW_DB_NAME}" \
        --dbuser="${MW_DB_USER}" \
        --dbpassfile="${MW_DB_PASS_FILE}" \
        --server="${MW_SERVER}" \
        --scriptpath=/ \
        --lang="${MW_LANG:-zh-cn}" \
        --passfile="${MW_ADMIN_PASS_FILE}" \
        "${MW_SITE_NAME}" "${MW_ADMIN_USER}"
    
      if ! grep -q "wfLoadExtension( 'VisualEditor' );" /state/LocalSettings.php; then
        cat >> /state/LocalSettings.php <<'PHP'
    
    wfLoadExtension( 'VisualEditor' );
    
    $wgMainCacheType = CACHE_ACCEL;
    $wgParserCacheType = CACHE_ACCEL;
    $wgSessionCacheType = CACHE_ACCEL;
    PHP
      fi
    
      if [ "${MW_PRIVATE_MODE:-false}" = "true" ]; then
        if ! grep -q "PRIVATE_WIKI_HARDENING" /state/LocalSettings.php; then
          cat >> /state/LocalSettings.php <<'PHP'
    
    # PRIVATE_WIKI_HARDENING
    $wgGroupPermissions['*']['read'] = false;
    $wgGroupPermissions['*']['edit'] = false;
    $wgGroupPermissions['*']['createaccount'] = false;
    PHP
        fi
      fi
    
      chmod 600 /state/LocalSettings.php
    fi
    
    ln -sf /state/LocalSettings.php /var/www/html/LocalSettings.php
    exec "$@"

* * *

12. LocalSettings 配置要求

----------------------

12.1 Public wiki
----------------

追加：

* `wfLoadExtension( 'VisualEditor' );`

* APCu/对象缓存基础配置

* 站点名、logo、基础语言配置预留位

12.2 Private wiki
-----------------

在 public 的基础上增加：
    $wgGroupPermissions['*']['read'] = false;
    $wgGroupPermissions['*']['edit'] = false;
    $wgGroupPermissions['*']['createaccount'] = false;

但必须在文档里明确注明：

> 这只限制 wiki 页面访问，不自动保护上传文件直链。

这个点必须写入 README 和 PLAN。  
官方在“Restrict access to uploaded files”一节中说得非常明确。([MediaWiki](https://www.mediawiki.org/wiki/Manual%3APreventing_access "Manual:Preventing access - MediaWiki"))
12.3 文件权限
---------

`LocalSettings.php` 必须：

* 宿主机权限尽量收紧

* 运行后 chmod 600

* 不能加入 Git

MediaWiki 文档明确把数据库凭据视作敏感信息，并建议进一步拆到独立文件中。([MediaWiki](https://www.mediawiki.org/wiki/Manual%3ALocalSettings.php "Manual:LocalSettings.php - MediaWiki"))

* * *

13. Caddy 配置要求

--------------

13.1 `Caddyfile.public`
-----------------------

最小要求：
    {$PUBLIC_HOST} {
        encode zstd gzip
        reverse_proxy mw_public:9000
    }

若采用 FPM 方式接入，Codex 需根据最终容器形态改成：

* `php_fastcgi`

* 或 HTTP 反代至独立 web 层

关键在于：  
**public 必须支持正常 HTTPS、压缩、清晰的 host 路由**。
13.2 `Caddyfile.private`
------------------------

最小要求：
    {$PRIVATE_HOST} {
        encode zstd gzip
        reverse_proxy mw_private:9000
    }

但对应服务只绑定到 `127.0.0.1`，不直接暴露公网。

* * *

14. README 必须包含的内容

------------------

README 至少要写清楚：

1. 项目简介

2. 架构图

3. 为什么使用双 Wiki

4. 前置依赖

5. 首次启动步骤

6. secrets 文件准备

7. 域名/DNS 要求

8. 备份方法

9. 恢复方法

10. 升级方法

11. private wiki 的安全说明

12. 常见故障排查

* * *

15. 启动流程

--------

15.1 首次启动步骤
-----------

用户执行流程应尽量接近：
    cp .env.example .env
    mkdir -p secrets state/public state/private uploads/public uploads/private backups
    # 编辑 secrets/* 文件
    docker compose build --pull
    docker compose up -d

然后：

* `mariadb` 启动

* `mw_public` / `mw_private` 等待 DB healthy

* 首次启动自动安装 MediaWiki

* 自动生成各自 `LocalSettings.php`

* Caddy 接管访问

15.2 启动后验证
----------

至少验证：

* `docker compose ps`

* `docker compose logs mariadb`

* `docker compose logs mw_public`

* `docker compose logs mw_private`

* `curl -I https://public-host`

* `curl -k -I https://127.0.0.1:8443`

* * *

16. 备份策略

--------

16.1 备份内容
---------

必须备份：

* `labwiki_public` 数据库

* `labwiki_private` 数据库

* `state/`

* `uploads/`

MediaWiki 升级/运维时，数据库和文件是最关键的两类资产。([MediaWiki](https://www.mediawiki.org/wiki/Manual%3ALocalSettings.php "Manual:LocalSettings.php - MediaWiki"))
16.2 `backup.sh` 要求
-------------------

脚本至少完成：

* SQL dump

* `state/` 打包

* `uploads/` 打包

* 生成时间戳目录或文件名前缀

参考：
    #!/usr/bin/env bash
    set -euo pipefail

    STAMP="$(date +%F_%H-%M-%S)"
    mkdir -p backups

    docker compose exec -T mariadb sh -lc \
      "mariadb-dump -uroot -p\"$$(cat /run/secrets/db_root_password)\" --databases labwiki_public labwiki_private" \
      > "backups/${STAMP}_db.sql"

    tar czf "backups/${STAMP}_state_uploads.tar.gz" state uploads

* * *

17. 恢复策略

--------

17.1 `restore.sh` 必须支持
----------------------

* 从 SQL 恢复数据库

* 恢复 `state/`

* 恢复 `uploads/`

* 恢复后重新拉起服务

* 提示用户恢复前先停服务或确认覆盖

17.2 恢复后验证
----------

* public/private 是否都能打开

* 历史图片是否存在

* 管理员是否能登录

* 关键页面是否存在

* * *

18. 升级策略

--------

18.1 升级原则
---------

升级 MediaWiki 时：

1. 先备份

2. 更新 Dockerfile 中的基础镜像 tag + digest

3. `docker compose build --pull`

4. `docker compose up -d`

5. 执行 `php maintenance/run.php update`

6. smoke test

MediaWiki 的 CLI 维护脚本用于安装和更新；升级后跑 update 是标准动作。([MediaWiki](https://www.mediawiki.org/wiki/Manual%3AInstall.php "Manual:install.php - MediaWiki"))
18.2 `upgrade.sh` 要求
--------------------

脚本至少做：

* 提醒确认备份

* 执行容器重建

* 对 public/private 依次跑 update

* 输出升级后检查建议

参考：
    docker compose exec -T mw_public php maintenance/run.php update
    docker compose exec -T mw_private php maintenance/run.php update

* * *

19. Smoke Test 要求

-----------------

`smoke-test.sh` 必须至少检查：

1. 容器是否存活

2. `LocalSettings.php` 是否存在

3. public 首页是否返回 200/302

4. private 首页是否返回登录页或受控状态

5. uploads 目录是否可写

6. DB 连接是否正常

7. public/private 各自的 wiki name 是否正确

* * *

20. 安全说明

--------

20.1 本方案不承诺“公网 private wiki 的附件天然安全”
------------------------------------

必须在文档中明确：

* `read=false` 只保护 wiki 页面

* 默认不保护上传文件直链

* 若必须公网暴露 private wiki，需后续增加：
  
  * `img_auth.php`
  
  * 服务器级路径限制
  
  * VPN / 内网 ACL
  
  * 零信任访问网关

这个结论来自 MediaWiki 官方访问控制文档。([MediaWiki](https://www.mediawiki.org/wiki/Manual%3APreventing_access "Manual:Preventing access - MediaWiki"))
20.2 secrets 管理
---------------

* `secrets/` 必须加入 `.gitignore`

* 不允许把密码写进 README 示例

* 不允许把密码回显到日志

20.3 `.gitignore` 最低要求
----------------------

    .env
    secrets/*
    !secrets/.gitkeep
    state/**/LocalSettings.php
    backups/*

* * *

21. V3 范围内做，V3 范围外暂不做

---------------------

21.1 本期纳入
---------

* 双 wiki

* Docker Compose

* 自定义 MediaWiki 镜像

* secrets

* healthcheck

* 自动初始化

* 备份/恢复/升级脚本

* public/private 分离部署

21.2 本期不纳入
----------

* Cargo

* Page Forms

* LDAP / CAS

* SSO

* 对象存储

* Kubernetes

* 多节点 HA

* CDN

* 搜索引擎增强

* 文件直链高级保护

这些放到 V3.1 / V4。

* * *

22. Codex 实施阶段拆分

----------------

Phase 1：仓库骨架
------------

目标：

* 创建目录树

* 创建占位文件

* 写 `.gitignore`

* 写 `.env.example`

验收：

* 目录结构完整

* Git 状态干净

* 无无效路径

Phase 2：Compose 栈
-----------------

目标：

* 写 `compose.yaml`

* 定义服务、volumes、secrets、healthchecks

* 明确 public/private 暴露边界

验收：

* `docker compose config` 通过

* 无语法错误

Phase 3：自定义镜像
-------------

目标：

* 写 Dockerfile

* 安装 APCu

* 加 PHP 配置

* 接入 bootstrap entrypoint

验收：

* `docker compose build` 成功

* 镜像可启动

Phase 4：数据库初始化
--------------

目标：

* 创建双数据库

* 创建双用户

* 支持幂等执行

验收：

* 重启不重复失败

* 两个 DB 都存在

Phase 5：MediaWiki 自动安装
----------------------

目标：

* public/private 自动安装

* 生成 LocalSettings

* 软链回根目录

验收：

* 首次启动自动完成

* 二次重启不重复安装

Phase 6：反向代理
------------

目标：

* 配置 Caddy public/private

* public 正常 HTTPS

* private 默认本机绑定

验收：

* public 可浏览

* private 可通过本机隧道/回环访问

Phase 7：运维脚本
------------

目标：

* `backup.sh`

* `restore.sh`

* `upgrade.sh`

* `smoke-test.sh`

验收：

* 脚本可执行

* 关键路径都能跑通

Phase 8：README 与最终整理
--------------------

目标：

* 完整说明文档

* 常见故障排查

* 启动与恢复步骤清晰

验收：

* 新机器可按 README 独立部署

* * *

23. 验收标准

--------

项目完成时，必须满足：

1. `docker compose config` 通过

2. `docker compose build --pull` 成功

3. `docker compose up -d` 后所有核心服务正常

4. public wiki 可访问

5. private wiki 可访问（至少本机回环）

6. public/private 都各自有独立 `LocalSettings.php`

7. public/private 图片上传后重启不丢

8. `backup.sh` 成功导出 SQL + 文件归档

9. `restore.sh` 能恢复

10. `upgrade.sh` 能跑 update

11. 文档明确写明 private 附件访问边界

12. 所有密码均不在 `.env` 明文中

* * *

24. 失败回滚策略

----------

若任一阶段失败：

### 构建失败

* 修正 Dockerfile / Compose

* 重新 `docker compose build --no-cache`

### 初始化失败

* 检查 secrets 文件权限与挂载

* 检查 DB 是否 healthy

* 检查 `/state/LocalSettings.php` 是否残留半成品

* 清理异常 state 后重试

### 升级失败

* 停止新容器

* 恢复旧镜像 digest

* 恢复最近一次备份

* 重新 `up -d`

### 数据恢复失败

* 保留原始备份

* 分离问题为“数据库”或“文件”

* 优先验证 SQL 可导入，再恢复文件层

* * *

25. Codex 实施约束

--------------

Codex 在实现过程中必须遵守：

1. 不要把敏感密码写进源码

2. 不要使用 `latest`

3. 不要让 private wiki 默认暴露公网

4. 不要把 MediaWiki-Docker 当生产方案

5. 不要让 `LocalSettings.php` 留在 Git 中

6. 不要实现“启动一次之后必须人工进容器补配置”的半自动方案

7. 所有脚本都要幂等或尽量接近幂等

8. 所有 shell 脚本使用 `set -euo pipefail`

9. 所有关键行为写入 README

* * *

26. 给 Codex 的最终执行提示词

--------------------

    你要为一个课题组生成一套可生产使用的 MediaWiki Docker Compose 仓库，目标是“公开官网 + 内部知识库”双 wiki 部署，而不是单 wiki 混合权限站点。
    
    硬性要求：
    1. 使用双实例：mw_public / mw_private。
    2. 使用单个 MariaDB 容器，但创建两个独立数据库和用户。
    3. 使用 Docker Hub 的 mediawiki 官方镜像作为基础，但必须写自定义 Dockerfile，并固定到 1.43.6-fpm + digest。
    4. 不使用 MediaWiki-Docker 开发环境。
    5. 使用 Docker Compose secrets，所有真实密码不允许放在 .env 中。
    6. 使用 healthcheck 和 depends_on.condition: service_healthy。
    7. mw_public 通过 caddy_public 暴露 80/443。
    8. mw_private 通过 caddy_private 仅绑定到 127.0.0.1:8443，默认不直接公网暴露。
    9. state/public/LocalSettings.php 与 state/private/LocalSettings.php 必须持久化到宿主机。
    10. uploads/public 和 uploads/private 必须持久化到宿主机。
    11. 使用 MediaWiki CLI 安装：php maintenance/run.php install，并使用 --confpath、--dbpassfile、--passfile。
    12. 容器入口脚本必须实现幂等初始化：若 /state/LocalSettings.php 已存在则不重复安装。
    13. public/private 都要自动追加 VisualEditor 和基础缓存配置。
    14. private 需要默认设置匿名不可读、不可编辑、不可注册。
    15. README 必须明确写出：关闭匿名 read 只限制 wiki 页面，不自动保护上传文件直链。
    16. 提供以下文件：
       - compose.yaml
       - compose.override.yaml
       - .env.example
       - .gitignore
       - README.md
       - images/mediawiki-app/Dockerfile
       - images/mediawiki-app/php/zz-mediawiki.ini
       - images/mediawiki-app/entrypoint/bootstrap-instance.sh
       - ops/caddy/Caddyfile.public
       - ops/caddy/Caddyfile.private
       - ops/db-init/01-create-wikis.sh
       - ops/scripts/backup.sh
       - ops/scripts/restore.sh
       - ops/scripts/upgrade.sh
       - ops/scripts/smoke-test.sh
    17. 所有 shell 脚本使用 bash + set -euo pipefail。
    18. 所有关键步骤必须能在全新 Ubuntu + Docker Compose 环境中完成。
    
    验收目标：
    - docker compose config 通过
    - docker compose build --pull 成功
    - docker compose up -d 后服务正常
    - public/private 两个 wiki 都能访问
    - LocalSettings.php 已持久化
    - 图片上传后重启不丢失
    - backup/restore/upgrade/smoke-test 脚本都可运行
    - 文档清晰，具备真实可维护性

* * *

27. 最终结论

--------

本方案是：

* **适合课题组单机生产**

* **适合 Codex 自动生成**

* **比传统裸机手工部署更现代**

* **比单 Wiki 强行权限隔离更稳**

* **为后续 Cargo / Page Forms / LDAP 留足扩展空间**

但仍需记住：

* 若 future 要求更高的附件访问控制，private wiki 还需要继续硬化。

* 若未来扩到多节点或高可用，再进入 Kubernetes / object storage / SSO 阶段。

* * *

如果你要，我下一条就继续把这份 `PLAN.md` 对应的 **完整仓库文件逐个写出来**。
