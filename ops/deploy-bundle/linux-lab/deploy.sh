#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT_DIR}"

bash ops/deploy-bundle/linux-lab/preflight-check.sh

docker compose -f compose.yaml build --pull
docker compose -f compose.yaml up -d
bash ops/scripts/smoke-test.sh
