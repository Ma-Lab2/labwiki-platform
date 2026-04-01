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

stamp="$(date +%F_%H-%M-%S)"
private_sql="${OUTPUT_DIR}/${stamp}_labwiki_private.sql"
private_uploads="${OUTPUT_DIR}/${stamp}_uploads_private.tar.gz"

# Only export the private wiki database. This contains student accounts,
# approval records, and private wiki page content.
docker compose -f compose.yaml exec -T mariadb sh -lc \
  'mariadb-dump -uroot -p"$(cat /run/secrets/db_root_password)" --single-transaction --routines --triggers --events --databases labwiki_private' \
  > "${private_sql}"

# Only export private uploads. Do not include assistant database or other runtime data.
tar czf "${private_uploads}" uploads/private

cat > "${OUTPUT_DIR}/MANIFEST.txt" <<MANIFEST
private-wiki-safe-data package

Included files:
- $(basename "${private_sql}") : labwiki_private database only
- $(basename "${private_uploads}") : uploads/private only

Not included:
- assistant database
- assistant attachment storage
- .env
- secrets/*.txt
MANIFEST

printf 'private wiki safe backup complete -> %s\n' "${OUTPUT_DIR}"
