#!/usr/bin/env bash
set -euo pipefail

DEFAULT_DATA_DIR="/app/default-data"
DATA_DIR="${PYTPS_DATA_DIR:-/app/backend/data}"
IMAGE_DIR="${PYTPS_IMAGE_DIR:-/data/images}"
OUTPUT_DIR="${PYTPS_OUTPUT_DIR:-/data/output}"

mkdir -p "${DATA_DIR}" "${IMAGE_DIR}" "${OUTPUT_DIR}"

for name in PyTPS_init.ini TPS_Settings.ini mcp-proton.txt; do
  if [[ ! -f "${DATA_DIR}/${name}" && -f "${DEFAULT_DATA_DIR}/${name}" ]]; then
    cp "${DEFAULT_DATA_DIR}/${name}" "${DATA_DIR}/${name}"
  fi
done

exec "$@"
