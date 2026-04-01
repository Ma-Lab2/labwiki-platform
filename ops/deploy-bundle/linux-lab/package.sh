#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT_DIR}"

INCLUDE_RUNTIME_DATA="false"
STAMP="$(date +%F_%H-%M-%S)"
OUTPUT_ROOT="${ROOT_DIR}/backups/deploy-bundles"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --include-runtime-data)
      INCLUDE_RUNTIME_DATA="true"
      shift
      ;;
    --output-root)
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--include-runtime-data] [--output-root <dir>]" >&2
      exit 1
      ;;
  esac
done

STAGING_DIR="${OUTPUT_ROOT}/labwiki-linux-lab-${STAMP}"
REPO_DIR="${STAGING_DIR}/labwiki-platform"
mkdir -p "${REPO_DIR}"

copy_entry() {
  local source="$1"
  local dest_dir="${REPO_DIR}/$(dirname "${source}")"
  mkdir -p "${dest_dir}"
  if [[ -d "${ROOT_DIR}/${source}" ]]; then
    if command -v rsync >/dev/null 2>&1; then
      rsync -a         --exclude 'node_modules'         --exclude 'dist'         --exclude '__pycache__'         --exclude '.pytest_cache'         --exclude '.venv'         --exclude '.venv312'         --exclude '.git'         "${ROOT_DIR}/${source}" "${dest_dir}/"
    else
      tar -C "${ROOT_DIR}"         --exclude='node_modules'         --exclude='dist'         --exclude='__pycache__'         --exclude='.pytest_cache'         --exclude='.venv'         --exclude='.venv312'         --exclude='.git'         -cf - "${source}" | tar -C "${REPO_DIR}" -xf -
    fi
  else
    cp -R "${ROOT_DIR}/${source}" "${dest_dir}/$(basename "${source}")"
  fi
}

copy_entry compose.yaml
copy_entry .env.example
copy_entry README.md
copy_entry CONTRIBUTING.md
copy_entry assistant_api
copy_entry images/mediawiki-app
copy_entry ops/caddy
copy_entry ops/db-init
copy_entry ops/scripts
copy_entry ops/deploy-bundle/linux-lab
# runtime-data export ultimately shells out to ops/scripts/backup.sh plus assistant_store dump
copy_entry tools/pytps-web
copy_entry tools/rcf-web
copy_entry tools-data/tps/images/.gitkeep
copy_entry tools-data/tps/output/.gitkeep
copy_entry uploads/public/.gitkeep
copy_entry uploads/private/.gitkeep
copy_entry state/tps/.gitkeep
copy_entry state/rcf/uploaded_materials/.gitkeep
copy_entry backups/.gitkeep

cp "${ROOT_DIR}/ops/deploy-bundle/linux-lab/.env.lab.example" "${REPO_DIR}/.env.lab.example"

if [[ "${INCLUDE_RUNTIME_DATA}" == "true" ]]; then
  mkdir -p "${STAGING_DIR}/runtime-data"
  bash "${ROOT_DIR}/ops/deploy-bundle/linux-lab/backup-runtime-data.sh" --output-dir "${STAGING_DIR}/runtime-data"
fi

tar czf "${STAGING_DIR}.tar.gz" -C "${OUTPUT_ROOT}" "$(basename "${STAGING_DIR}")"
printf 'deploy bundle ready:
- %s
- %s
' "${STAGING_DIR}" "${STAGING_DIR}.tar.gz"
