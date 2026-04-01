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

sql_file="$(find "${RUNTIME_DIR}" -maxdepth 1 -type f -name '*_db.sql' | sort | tail -n 1)"
archive_file="$(find "${RUNTIME_DIR}" -maxdepth 1 -type f -name '*_state_uploads.tar.gz' | sort | tail -n 1)"
assistant_dump="$(find "${RUNTIME_DIR}" -maxdepth 1 -type f -name '*_assistant_store.sql' | sort | tail -n 1)"

[[ -n "${sql_file}" && -n "${archive_file}" && -n "${assistant_dump}" ]] || { echo "runtime-data bundle is incomplete" >&2; exit 1; }

bash ops/scripts/restore.sh --sql "${sql_file}" --archive "${archive_file}" --force

docker compose -f compose.yaml up -d assistant_store
until docker compose -f compose.yaml exec -T assistant_store sh -lc 'pg_isready -U "${ASSISTANT_DB_USER:-labassistant}" -d "${ASSISTANT_DB_NAME:-labassistant}"' >/dev/null 2>&1; do
  sleep 2
done

docker compose -f compose.yaml exec -T assistant_store sh -lc \
  'PGPASSWORD="$(cat /run/secrets/assistant_db_password)" psql -U "${ASSISTANT_DB_USER:-labassistant}" -d "${ASSISTANT_DB_NAME:-labassistant}" <<SQL
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO "${ASSISTANT_DB_USER:-labassistant}";
GRANT ALL ON SCHEMA public TO public;
SQL'

docker compose -f compose.yaml exec -T assistant_store sh -lc \
  'PGPASSWORD="$(cat /run/secrets/assistant_db_password)" psql -U "${ASSISTANT_DB_USER:-labassistant}" -d "${ASSISTANT_DB_NAME:-labassistant}"' \
  < "${assistant_dump}"

printf 'runtime restore complete\n'
