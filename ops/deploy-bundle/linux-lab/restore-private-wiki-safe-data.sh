#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT_DIR}"

RUNTIME_DIR=""
FORCE="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --runtime-dir)
      RUNTIME_DIR="$2"
      shift 2
      ;;
    --force)
      FORCE="true"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 --runtime-dir <dir> [--force]" >&2
      exit 1
      ;;
  esac
done

[[ -n "${RUNTIME_DIR}" ]] || { echo "--runtime-dir is required" >&2; exit 1; }
[[ -d "${RUNTIME_DIR}" ]] || { echo "Runtime dir not found: ${RUNTIME_DIR}" >&2; exit 1; }
[[ "${FORCE}" == "true" ]] || { echo "Restore is destructive. Re-run with --force." >&2; exit 1; }

sql_file="$(find "${RUNTIME_DIR}" -maxdepth 1 -type f -name '*_labwiki_private.sql' | sort | tail -n 1)"
uploads_archive="$(find "${RUNTIME_DIR}" -maxdepth 1 -type f -name '*_uploads_private.tar.gz' | sort | tail -n 1)"
[[ -n "${sql_file}" && -n "${uploads_archive}" ]] || { echo "private wiki safe bundle is incomplete" >&2; exit 1; }

docker compose -f compose.yaml stop caddy_private mw_private >/dev/null 2>&1 || true
docker compose -f compose.yaml up -d mariadb
until docker compose -f compose.yaml exec -T mariadb sh -lc 'mariadb-admin ping -uroot -p"$(cat /run/secrets/db_root_password)" --silent' >/dev/null 2>&1; do
  sleep 2
done

rm -rf uploads/private
mkdir -p uploads/private

docker compose -f compose.yaml exec -T mariadb sh -lc \
  'mariadb -uroot -p"$(cat /run/secrets/db_root_password)" <<SQL
DROP DATABASE IF EXISTS `labwiki_private`;
CREATE DATABASE `labwiki_private` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
SQL' >/dev/null

docker compose -f compose.yaml exec -T mariadb sh -lc \
  'mariadb -uroot -p"$(cat /run/secrets/db_root_password)"' \
  < "${sql_file}"

tar xzf "${uploads_archive}" -C "${ROOT_DIR}"

docker compose -f compose.yaml up -d mw_private caddy_private
printf 'private wiki safe restore complete\n'
