#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

bash "${ROOT_DIR}/ops/scripts/assistant-python.sh" --cwd assistant_api -m app.assistantctl "$@"
