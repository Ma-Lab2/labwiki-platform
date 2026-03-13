#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

compose_cmd=(docker compose -f compose.yaml)
if [[ "${LABWIKI_LOCAL_OVERRIDE:-false}" == "true" ]]; then
  compose_cmd+=(-f compose.override.yaml)
fi

YES="false"

if [[ "${1:-}" == "--yes" ]]; then
  YES="true"
fi

if [[ "${YES}" != "true" ]]; then
  read -r -p "Confirm that a fresh backup exists before upgrade [y/N]: " reply
  if [[ ! "${reply}" =~ ^[Yy]$ ]]; then
    echo "Upgrade cancelled."
    exit 1
  fi
fi

"${compose_cmd[@]}" build --pull
"${compose_cmd[@]}" up -d
"${compose_cmd[@]}" exec -T mw_public php maintenance/run.php update
"${compose_cmd[@]}" exec -T mw_private php maintenance/run.php update
bash ops/scripts/smoke-test.sh

echo "Upgrade finished. Review service logs if anything looks unexpected."
