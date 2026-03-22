#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

CASES=""
SCORES=""
TEMPLATE_OUTPUT=""
JSON_OUTPUT=""
MARKDOWN_OUTPUT=""

normalize_path() {
  local input="$1"
  if [[ -z "${input}" ]]; then
    return 0
  fi
  if [[ "${input}" = /* ]]; then
    realpath -m "${input}"
  else
    realpath -m "${ROOT_DIR}/${input}"
  fi
}

usage() {
  cat <<'EOF'
Usage: bash ops/scripts/build-assistant-student-eval-report.sh [options]

Options:
  --cases <path>            Optional custom student evaluation case JSON
  --scores <path>           Filled CSV score sheet
  --template-output <path>  Write a blank CSV score template
  --json-output <path>      Write the aggregated JSON report
  --markdown-output <path>  Write the Markdown summary report
  --help                    Show this help text

Examples:
  bash ops/scripts/build-assistant-student-eval-report.sh \
    --template-output backups/validation/student-eval-template.csv

  bash ops/scripts/build-assistant-student-eval-report.sh \
    --scores backups/validation/student-eval-scores.csv \
    --json-output backups/validation/student-eval-report.json \
    --markdown-output backups/validation/student-eval-report.md
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cases)
      CASES="${2:-}"
      shift
      ;;
    --scores)
      SCORES="${2:-}"
      shift
      ;;
    --template-output)
      TEMPLATE_OUTPUT="${2:-}"
      shift
      ;;
    --json-output)
      JSON_OUTPUT="${2:-}"
      shift
      ;;
    --markdown-output)
      MARKDOWN_OUTPUT="${2:-}"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ -n "${CASES}" ]]; then
  CASES="$(normalize_path "${CASES}")"
fi
if [[ -n "${SCORES}" ]]; then
  SCORES="$(normalize_path "${SCORES}")"
fi
if [[ -n "${TEMPLATE_OUTPUT}" ]]; then
  TEMPLATE_OUTPUT="$(normalize_path "${TEMPLATE_OUTPUT}")"
fi
if [[ -n "${JSON_OUTPUT}" ]]; then
  JSON_OUTPUT="$(normalize_path "${JSON_OUTPUT}")"
fi
if [[ -n "${MARKDOWN_OUTPUT}" ]]; then
  MARKDOWN_OUTPUT="$(normalize_path "${MARKDOWN_OUTPUT}")"
fi

python_args=(-m app.services.student_eval_report)
if [[ -n "${CASES}" ]]; then
  python_args+=(--cases "${CASES}")
fi
if [[ -n "${SCORES}" ]]; then
  python_args+=(--scores "${SCORES}")
fi
if [[ -n "${TEMPLATE_OUTPUT}" ]]; then
  mkdir -p "$(dirname "${TEMPLATE_OUTPUT}")"
  python_args+=(--template-output "${TEMPLATE_OUTPUT}")
fi
if [[ -n "${JSON_OUTPUT}" ]]; then
  mkdir -p "$(dirname "${JSON_OUTPUT}")"
  python_args+=(--json-output "${JSON_OUTPUT}")
fi
if [[ -n "${MARKDOWN_OUTPUT}" ]]; then
  mkdir -p "$(dirname "${MARKDOWN_OUTPUT}")"
  python_args+=(--markdown-output "${MARKDOWN_OUTPUT}")
fi

(
  bash "${ROOT_DIR}/ops/scripts/assistant-python.sh" --cwd assistant_api "${python_args[@]}"
)
