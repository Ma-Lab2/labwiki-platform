#!/usr/bin/env bash
set -euo pipefail

ROOT_PASS="$(tr -d '\r\n' < /run/secrets/db_root_password)"
PUBLIC_PASS="$(tr -d '\r\n' < /run/secrets/public_db_password)"
PRIVATE_PASS="$(tr -d '\r\n' < /run/secrets/private_db_password)"

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
