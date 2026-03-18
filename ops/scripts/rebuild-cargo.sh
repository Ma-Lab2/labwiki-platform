#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

compose_cmd=(docker compose -f compose.yaml)
if [[ "${LABWIKI_LOCAL_OVERRIDE:-false}" == "true" ]]; then
  compose_cmd+=(-f compose.override.yaml)
fi

seed_manifest="${ROOT_DIR}/images/mediawiki-app/seed/private-cargo-manifest.tsv"
seed_root="${ROOT_DIR}/images/mediawiki-app/seed"

seed_missing_cargo_pages() {
  local title=""
  local relative_path=""
  local existing_text=""
  local seed_file=""

  [[ -f "${seed_manifest}" ]] || return 0

  while IFS=$'\t' read -r title relative_path; do
    [[ -z "${title}" || -z "${relative_path}" ]] && continue
    seed_file="${seed_root}/${relative_path}"
    [[ -f "${seed_file}" ]] || continue

    existing_text="$("${compose_cmd[@]}" exec -T mw_private php maintenance/run.php getText.php "${title}" 2>/dev/null || true)"
    if [[ "${existing_text}" != Page\ *does\ not\ exist. ]]; then
      continue
    fi

    "${compose_cmd[@]}" exec -T mw_private php maintenance/run.php edit \
      --summary="Seed cargo entity page" \
      --user="${PRIVATE_ADMIN_USER:-admin}" \
      "${title}" < "${seed_file}"
  done < "${seed_manifest}"
}

seed_missing_cargo_pages

for table_name in \
  lab_terms \
  lab_devices \
  lab_mechanisms \
  lab_diagnostics \
  lab_literature_guides; do
  "${compose_cmd[@]}" exec -T mw_private php extensions/Cargo/maintenance/cargoRecreateData.php --quiet --table="${table_name}"
done
bash ops/scripts/reindex-assistant.sh wiki

printf '[ok] cargo tables recreated and assistant wiki index refreshed\n'
