#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT_DIR}"

require_file() {
  local path="$1"
  [[ -f "${path}" ]] || { echo "Missing file: ${path}" >&2; exit 1; }
}

command -v docker >/dev/null 2>&1 || { echo "docker not found" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "docker compose plugin not available" >&2; exit 1; }

require_file .env
require_file compose.yaml
require_file secrets/db_root_password.txt
require_file secrets/public_db_password.txt
require_file secrets/private_db_password.txt
require_file secrets/public_admin_password.txt
require_file secrets/private_admin_password.txt
require_file secrets/assistant_db_password.txt

mkdir -p state/public state/private state/assistant_uploads uploads/public uploads/private backups tools-data/tps/images tools-data/tps/output

docker compose -f compose.yaml config >/dev/null
printf 'preflight ok\n'
