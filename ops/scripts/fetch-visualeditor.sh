#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

VISUALEDITOR_REF="${VISUALEDITOR_REF:-3de88ce69e0b43d1565b5fc21adbe506fa71f78f}"
TARGET_DIR="vendor/VisualEditor"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

mkdir -p vendor
rm -rf "${TMP_DIR}/VisualEditor"

git clone --filter=blob:none --no-checkout https://gerrit.wikimedia.org/r/mediawiki/extensions/VisualEditor.git "${TMP_DIR}/VisualEditor"
git -C "${TMP_DIR}/VisualEditor" checkout "${VISUALEDITOR_REF}"
git -C "${TMP_DIR}/VisualEditor" submodule update --init --recursive --depth 1

rm -rf "${TMP_DIR}/VisualEditor/.git"
find "${TMP_DIR}/VisualEditor" -name '.git' -type d -prune -exec rm -rf {} +

rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"
cp -a "${TMP_DIR}/VisualEditor/." "${TARGET_DIR}/"

printf 'Vendored VisualEditor at %s into %s\n' "${VISUALEDITOR_REF}" "${TARGET_DIR}"
