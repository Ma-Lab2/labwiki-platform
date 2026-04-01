#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT_DIR}"

OUTPUT_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 --output-dir <dir>" >&2
      exit 1
      ;;
  esac
done

[[ -n "${OUTPUT_DIR}" ]] || { echo "--output-dir is required" >&2; exit 1; }
mkdir -p "${OUTPUT_DIR}"

before_list="$(mktemp)"
after_list="$(mktemp)"
trap 'rm -f "${before_list}" "${after_list}"' EXIT
find backups -maxdepth 1 -type f | sort > "${before_list}" || true

bash ops/scripts/backup.sh >/dev/null

find backups -maxdepth 1 -type f | sort > "${after_list}" || true
new_files="$(comm -13 "${before_list}" "${after_list}")"

sql_file="$(printf '%s\n' "${new_files}" | grep '_db\.sql$' | tail -n 1 || true)"
archive_file="$(printf '%s\n' "${new_files}" | grep '_state_uploads\.tar\.gz$' | tail -n 1 || true)"
[[ -n "${sql_file}" && -n "${archive_file}" ]] || { echo "Could not locate new backup artifacts from ops/scripts/backup.sh" >&2; exit 1; }

stamp="$(date +%F_%H-%M-%S)"
assistant_dump="${OUTPUT_DIR}/${stamp}_assistant_store.sql"

docker compose -f compose.yaml exec -T assistant_store sh -lc \
  'PGPASSWORD="$(cat /run/secrets/assistant_db_password)" pg_dump -U "${ASSISTANT_DB_USER:-labassistant}" -d "${ASSISTANT_DB_NAME:-labassistant}"' \
  > "${assistant_dump}"

cp "${sql_file}" "${OUTPUT_DIR}/"
cp "${archive_file}" "${OUTPUT_DIR}/"

cat > "${OUTPUT_DIR}/MANIFEST.txt" <<MANIFEST
runtime-data package

Included files:
- $(basename "${sql_file}") : MariaDB dump for labwiki_public + labwiki_private
- $(basename "${archive_file}") : state/ and uploads/
- $(basename "${assistant_dump}") : assistant_store PostgreSQL dump

Student accounts, registration approvals, and wiki page content are stored in the MariaDB dump above.
MANIFEST

printf 'runtime backup complete -> %s\n' "${OUTPUT_DIR}"
