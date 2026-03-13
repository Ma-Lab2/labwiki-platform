#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

STAMP="$(date +%F_%H-%M-%S)"
SQL_FILE="backups/${STAMP}_db.sql"
ARCHIVE_FILE="backups/${STAMP}_state_uploads.tar.gz"

mkdir -p backups

docker compose exec -T mariadb sh -lc \
  'mariadb-dump -uroot -p"$(cat /run/secrets/db_root_password)" --single-transaction --routines --triggers --events --databases labwiki_public labwiki_private' \
  > "${SQL_FILE}"

tar czf "${ARCHIVE_FILE}" state uploads

printf 'Backup complete:\n- %s\n- %s\n' "${SQL_FILE}" "${ARCHIVE_FILE}"
