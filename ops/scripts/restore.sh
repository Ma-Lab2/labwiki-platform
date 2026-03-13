#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

SQL_FILE=""
ARCHIVE_FILE=""
FORCE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sql)
      SQL_FILE="$2"
      shift 2
      ;;
    --archive)
      ARCHIVE_FILE="$2"
      shift 2
      ;;
    --force)
      FORCE="true"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 --sql <dump.sql> --archive <state_uploads.tar.gz> [--force]" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${SQL_FILE}" || -z "${ARCHIVE_FILE}" ]]; then
  echo "Both --sql and --archive are required" >&2
  exit 1
fi

if [[ ! -f "${SQL_FILE}" ]]; then
  echo "SQL file not found: ${SQL_FILE}" >&2
  exit 1
fi

if [[ ! -f "${ARCHIVE_FILE}" ]]; then
  echo "Archive file not found: ${ARCHIVE_FILE}" >&2
  exit 1
fi

if [[ "${FORCE}" != "true" ]]; then
  echo "Restore is destructive. Re-run with --force to continue." >&2
  exit 1
fi

mkdir -p state/public state/private uploads/public uploads/private

docker compose stop caddy_public caddy_private mw_public mw_private >/dev/null 2>&1 || true
docker compose up -d mariadb

until docker compose exec -T mariadb sh -lc 'mariadb-admin ping -uroot -p"$(cat /run/secrets/db_root_password)" --silent'; do
  sleep 2
done

rm -rf state uploads
mkdir -p state/public state/private uploads/public uploads/private
tar xzf "${ARCHIVE_FILE}" -C "${ROOT_DIR}"

docker compose exec -T mariadb sh -lc \
  'mariadb -uroot -p"$(cat /run/secrets/db_root_password)"' \
  < "${SQL_FILE}"

docker compose up -d

printf 'Restore complete. Verify with:\n- docker compose ps\n- bash ops/scripts/smoke-test.sh\n'
