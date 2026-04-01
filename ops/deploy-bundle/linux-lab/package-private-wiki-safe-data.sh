#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT_DIR}"

OUTPUT_ROOT="${ROOT_DIR}/backups/private-wiki-safe-transfer"
STAMP="$(date +%F_%H-%M-%S)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-root)
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--output-root <dir>]" >&2
      exit 1
      ;;
  esac
done

STAGING_DIR="${OUTPUT_ROOT}/private-wiki-safe-data-${STAMP}"
mkdir -p "${STAGING_DIR}/runtime-data"

bash "${ROOT_DIR}/ops/deploy-bundle/linux-lab/backup-private-wiki-safe-data.sh" --output-dir "${STAGING_DIR}/runtime-data"

cat > "${STAGING_DIR}/README.txt" <<README
This package is for servers that have already pulled the Git repository.

Included:
- runtime-data/ from backup-private-wiki-safe-data.sh

Restore on the server in the pulled repo root:
- bash ops/deploy-bundle/linux-lab/restore-private-wiki-safe-data.sh --runtime-dir <path-to-runtime-data> --force
README

tar czf "${STAGING_DIR}.tar.gz" -C "${OUTPUT_ROOT}" "$(basename "${STAGING_DIR}")"
printf 'private wiki safe transfer bundle ready:\n- %s\n- %s\n' "${STAGING_DIR}" "${STAGING_DIR}.tar.gz"
