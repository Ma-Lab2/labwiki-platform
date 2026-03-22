#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

compose_cmd=(docker compose -f compose.yaml)
if [[ "${LABWIKI_LOCAL_OVERRIDE:-false}" == "true" ]]; then
  compose_cmd+=(-f compose.override.yaml)
fi

YES="false"
RUN_SMOKE="true"
ASSISTANT_VALIDATE_PROFILE="contract"
ASSISTANT_REPORT_FILE=""

usage() {
  cat <<'EOF'
Usage: bash ops/scripts/upgrade.sh [options]

Options:
  --yes                               Skip interactive confirmations
  --skip-smoke                        Do not run ops/scripts/smoke-test.sh
  --assistant-validate-profile <p>    Run assistant validation with profile: none|contract|chat|full
  --skip-assistant-validate           Alias for --assistant-validate-profile none
  --assistant-report-file <path>      Write assistant validation JSON to the given path
  --help                              Show this help text

Environment:
  LABWIKI_LOCAL_OVERRIDE=true
    Include compose.override.yaml in docker compose commands.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes)
      YES="true"
      ;;
    --skip-smoke)
      RUN_SMOKE="false"
      ;;
    --assistant-validate-profile)
      ASSISTANT_VALIDATE_PROFILE="${2:-}"
      shift
      ;;
    --skip-assistant-validate)
      ASSISTANT_VALIDATE_PROFILE="none"
      ;;
    --assistant-report-file)
      ASSISTANT_REPORT_FILE="${2:-}"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

case "${ASSISTANT_VALIDATE_PROFILE}" in
  none|contract|chat|full)
    ;;
  *)
    printf 'Unsupported assistant validation profile: %s\n' "${ASSISTANT_VALIDATE_PROFILE}" >&2
    usage >&2
    exit 1
    ;;
esac

if [[ "${YES}" != "true" ]]; then
  read -r -p "Confirm that a fresh backup exists before upgrade [y/N]: " reply
  if [[ ! "${reply}" =~ ^[Yy]$ ]]; then
    echo "Upgrade cancelled."
    exit 1
  fi
fi

"${compose_cmd[@]}" build --pull
"${compose_cmd[@]}" up -d
"${compose_cmd[@]}" exec -T mw_public php maintenance/run.php update
"${compose_cmd[@]}" exec -T mw_private php maintenance/run.php update

if [[ "${RUN_SMOKE}" == "true" ]]; then
  bash ops/scripts/smoke-test.sh
fi

if [[ "${ASSISTANT_VALIDATE_PROFILE}" != "none" ]]; then
  if [[ -z "${ASSISTANT_REPORT_FILE}" ]]; then
    timestamp="$(date +%Y-%m-%d_%H-%M-%S)"
    ASSISTANT_REPORT_FILE="backups/validation/upgrade-assistant-${timestamp}-${ASSISTANT_VALIDATE_PROFILE}.json"
  fi
  validate_cmd=(
    bash ops/scripts/validate-assistant.sh
    --profile "${ASSISTANT_VALIDATE_PROFILE}"
    --report-file "${ASSISTANT_REPORT_FILE}"
  )
  if [[ "${RUN_SMOKE}" == "true" ]]; then
    validate_cmd+=(--skip-smoke)
  fi
  "${validate_cmd[@]}"
  echo "[step] Assistant validation report: ${ASSISTANT_REPORT_FILE}"
fi

echo "Upgrade finished. Review service logs if anything looks unexpected."
