#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

compose_cmd=(docker compose -f compose.yaml)
if [[ "${LABWIKI_LOCAL_OVERRIDE:-false}" == "true" ]]; then
  compose_cmd+=(-f compose.override.yaml)
fi

target="${1:-wiki}"
case "${target}" in
  wiki)
    endpoint="/reindex/wiki"
    ;;
  zotero)
    endpoint="/reindex/zotero"
    ;;
  *)
    echo "usage: bash ops/scripts/reindex-assistant.sh [wiki|zotero]" >&2
    exit 1
    ;;
esac

"${compose_cmd[@]}" exec -T assistant_api python - "${endpoint}" <<'PY'
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
