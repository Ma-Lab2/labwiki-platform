#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

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

docker compose build --pull
docker compose up -d
docker compose exec -T mw_public php maintenance/run.php update
docker compose exec -T mw_private php maintenance/run.php update
bash ops/scripts/smoke-test.sh

echo "Upgrade finished. Review service logs if anything looks unexpected."
