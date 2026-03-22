#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

compose_cmd=(docker compose -f compose.yaml)
if [[ "${LABWIKI_LOCAL_OVERRIDE:-false}" == "true" ]]; then
  compose_cmd+=(-f compose.override.yaml)
fi

WAIT_FOR_JOB="false"
TIMEOUT_SECONDS=900
POLL_INTERVAL=5

usage() {
  cat <<'EOF'
Usage: bash ops/scripts/reindex-assistant.sh [wiki|zotero] [options]

Options:
  --wait                Poll /admin/jobs/<job_id> until the job completes
  --timeout <seconds>   Maximum wait time when --wait is enabled (default: 900)
  --poll-interval <n>   Poll interval in seconds when --wait is enabled (default: 5)

Environment:
  LABWIKI_LOCAL_OVERRIDE=true
    Include compose.override.yaml in docker compose commands.
EOF
}

target="wiki"
if [[ $# -gt 0 && "${1}" != --* ]]; then
  target="$1"
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --wait)
      WAIT_FOR_JOB="true"
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:-}"
      shift
      ;;
    --poll-interval)
      POLL_INTERVAL="${2:-}"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

case "${target}" in
  wiki)
    endpoint="/reindex/wiki"
    ;;
  zotero)
    endpoint="/reindex/zotero"
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not in PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose plugin is not available." >&2
  exit 1
fi

response="$("${compose_cmd[@]}" exec -T assistant_api python - "${endpoint}" <<'PY'
import json
import sys
import urllib.request

endpoint = sys.argv[1]
req = urllib.request.Request(
    "http://127.0.0.1:8000" + endpoint,
    data=b"{}",
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=20) as response:
    payload = json.loads(response.read().decode("utf-8"))
print(json.dumps(payload, ensure_ascii=False))
PY
)"

printf '%s\n' "${response}"

if [[ "${WAIT_FOR_JOB}" != "true" ]]; then
  exit 0
fi

job_id="$(REINDEX_RESPONSE="${response}" python - <<'PY'
import json
import os

payload = json.loads(os.environ["REINDEX_RESPONSE"])
print(payload.get("job_id", ""))
PY
)"

status="$(REINDEX_RESPONSE="${response}" python - <<'PY'
import json
import os

payload = json.loads(os.environ["REINDEX_RESPONSE"])
print(payload.get("status", ""))
PY
)"

if [[ -z "${job_id}" || "${status}" == "disabled" ]]; then
  exit 0
fi

deadline=$((SECONDS + TIMEOUT_SECONDS))
while (( SECONDS < deadline )); do
  job_payload="$("${compose_cmd[@]}" exec -T assistant_api python - "${job_id}" <<'PY'
import json
import sys
import urllib.request

job_id = sys.argv[1]
with urllib.request.urlopen(f"http://127.0.0.1:8000/admin/jobs/{job_id}", timeout=20) as response:
    payload = json.loads(response.read().decode("utf-8"))
print(json.dumps(payload, ensure_ascii=False))
PY
)"
  printf '%s\n' "${job_payload}"
  job_status="$(JOB_PAYLOAD="${job_payload}" python - <<'PY'
import json
import os

payload = json.loads(os.environ["JOB_PAYLOAD"])
print(payload.get("status", ""))
PY
)"
  case "${job_status}" in
    completed)
      exit 0
      ;;
    failed)
      echo "Assistant reindex job failed." >&2
      exit 1
      ;;
  esac
  sleep "${POLL_INTERVAL}"
done

echo "Timed out waiting for assistant reindex job ${job_id}." >&2
exit 1
