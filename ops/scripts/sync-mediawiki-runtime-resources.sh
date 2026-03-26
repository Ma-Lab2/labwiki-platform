#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

SERVICE="mw_private"
RESTART_SERVICE="true"

usage() {
  cat <<EOF
Usage: bash ops/scripts/sync-mediawiki-runtime-resources.sh [options]

Options:
  --service <name>       Compose service to sync into (default: ${SERVICE})
  --no-restart           Do not restart the service after syncing drifted files
  --help                 Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      SERVICE="${2:?missing value for --service}"
      shift 2
      ;;
    --no-restart)
      RESTART_SERVICE="false"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SYNC_PAYLOAD="$(python ops/scripts/check_mediawiki_resource_sync.py --service "${SERVICE}" --json || true)"
export SYNC_PAYLOAD

mapfile -t DRIFTED_PAIRS < <(python - <<'PY'
import json
import os

payload = json.loads(os.environ["SYNC_PAYLOAD"])
for record in payload.get("records", []):
    if record.get("status") != "ok":
        print(record["host_path"])
        print(record["container_path"])
PY
)

if [[ "${#DRIFTED_PAIRS[@]}" -eq 0 ]]; then
  echo "[ok] ${SERVICE} runtime resources already match repo"
  exit 0
fi

CONTAINER_ID="$(docker compose ps -q "${SERVICE}")"
if [[ -z "${CONTAINER_ID}" ]]; then
  echo "Service ${SERVICE} is not running." >&2
  exit 1
fi

for (( i=0; i<${#DRIFTED_PAIRS[@]}; i+=2 )); do
  host_path="${DRIFTED_PAIRS[$i]}"
  container_path="${DRIFTED_PAIRS[$((i + 1))]}"
  container_dir="$(dirname "${container_path}")"
  docker compose exec -T "${SERVICE}" mkdir -p "${container_dir}" >/dev/null
  echo "[sync] ${host_path} -> ${SERVICE}:${container_path}"
  docker cp "${host_path}" "${CONTAINER_ID}:${container_path}"
done

if [[ "${RESTART_SERVICE}" == "true" ]]; then
  echo "[step] Restart ${SERVICE}"
  docker compose restart "${SERVICE}" >/dev/null
fi

python ops/scripts/check_mediawiki_resource_sync.py --service "${SERVICE}"
