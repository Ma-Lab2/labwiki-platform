#!/usr/bin/env bash
set -euo pipefail

DEFAULT_DATA_DIR="/app/default-data"
DATA_DIR="${PYTPS_DATA_DIR:-/app/backend/data}"
IMAGE_DIR="${PYTPS_IMAGE_DIR:-/data/images}"
OUTPUT_DIR="${PYTPS_OUTPUT_DIR:-/data/output}"
INIT_FILE="${DATA_DIR}/PyTPS_init.ini"
MCP_FILE="${DATA_DIR}/mcp-proton.txt"

mkdir -p "${DATA_DIR}" "${IMAGE_DIR}" "${OUTPUT_DIR}"

for name in PyTPS_init.ini TPS_Settings.ini mcp-proton.txt; do
  if [[ ! -f "${DATA_DIR}/${name}" && -f "${DEFAULT_DATA_DIR}/${name}" ]]; then
    cp "${DEFAULT_DATA_DIR}/${name}" "${DATA_DIR}/${name}"
  fi
done

if [[ -f "${INIT_FILE}" ]]; then
  export INIT_FILE IMAGE_DIR OUTPUT_DIR MCP_FILE
  python - <<'PY'
import os
from pathlib import Path

init_file = Path(os.environ["INIT_FILE"])
image_dir = os.environ["IMAGE_DIR"]
output_dir = os.environ["OUTPUT_DIR"]
mcp_file = os.environ["MCP_FILE"]

lines = init_file.read_text(encoding="utf-8").splitlines()
updated = []

for line in lines:
    if line.startswith("imagepath=\t"):
        updated.append(f"imagepath=\t{image_dir}")
    elif line.startswith("savepath=\t"):
        updated.append(f"savepath=\t{output_dir}")
    elif line.startswith("MCPpath=\t"):
        updated.append(f"MCPpath=\t{mcp_file}")
    else:
        updated.append(line)

init_file.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
fi

exec "$@"
