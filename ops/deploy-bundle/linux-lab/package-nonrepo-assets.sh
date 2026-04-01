#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT_DIR}"

OUTPUT_ROOT="${ROOT_DIR}/backups/runtime-transfer"
INCLUDE_RUNTIME_DATA="true"
STAMP="$(date +%F_%H-%M-%S)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-root)
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    --without-runtime-data)
      INCLUDE_RUNTIME_DATA="false"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--output-root <dir>] [--without-runtime-data]" >&2
      exit 1
      ;;
  esac
done

[[ -f .env ]] || { echo ".env not found" >&2; exit 1; }
[[ -d secrets ]] || { echo "secrets/ not found" >&2; exit 1; }
[[ -f secrets/private_admin_password.txt ]] || { echo "secrets/private_admin_password.txt not found" >&2; exit 1; }
[[ -f secrets/assistant_db_password.txt ]] || { echo "secrets/assistant_db_password.txt not found" >&2; exit 1; }

STAGING_DIR="${OUTPUT_ROOT}/labwiki-nonrepo-assets-${STAMP}"
mkdir -p "${STAGING_DIR}"

cp .env "${STAGING_DIR}/.env"
mkdir -p "${STAGING_DIR}/secrets"
cp secrets/*.txt "${STAGING_DIR}/secrets/"

cat > "${STAGING_DIR}/README.txt" <<README
This package is for servers that have already pulled the Git repository.

Included:
- .env
- secrets/*.txt
README

if [[ "${INCLUDE_RUNTIME_DATA}" == "true" ]]; then
  mkdir -p "${STAGING_DIR}/runtime-data"
  bash "${ROOT_DIR}/ops/deploy-bundle/linux-lab/backup-runtime-data.sh" --output-dir "${STAGING_DIR}/runtime-data"
  cat >> "${STAGING_DIR}/README.txt" <<README
- runtime-data/ produced by backup-runtime-data.sh

Restore on the server after copying this package into the pulled repo root:
- cp .env <repo>/.env
- cp secrets/*.txt <repo>/secrets/
- bash ops/deploy-bundle/linux-lab/restore-runtime-data.sh --runtime-dir <path-to-runtime-data> --force
README
else
  cat >> "${STAGING_DIR}/README.txt" <<README

This package was generated without runtime-data.
README
fi

tar czf "${STAGING_DIR}.tar.gz" -C "${OUTPUT_ROOT}" "$(basename "${STAGING_DIR}")"
printf 'non-repo asset bundle ready:\n- %s\n- %s\n' "${STAGING_DIR}" "${STAGING_DIR}.tar.gz"
