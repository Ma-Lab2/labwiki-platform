#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

OUTPUT=""
CASES=""
GENERATION_MODEL="gpt-5.4-mini"
TIMEOUT="180"
RETRIES="1"
RETRY_DELAY="2.0"
CASE_IDS=()

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
Usage: bash ops/scripts/run-assistant-student-eval.sh [options]

Options:
  --output <path>            Repo-relative JSON output path
  --cases <path>             Optional custom case JSON
  --case-id <id>             Repeatable filter for one or more case ids
  --generation-model <id>    Generation model (default: gpt-5.4-mini)
  --timeout <seconds>        Per-case timeout (default: 180)
  --retries <n>              Retries on failure (default: 1)
  --retry-delay <seconds>    Delay between retries (default: 2.0)
  --help                     Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      OUTPUT="${2:-}"
      shift
      ;;
    --cases)
      CASES="${2:-}"
      shift
      ;;
    --case-id)
      CASE_IDS+=("${2:-}")
      shift
      ;;
    --generation-model)
      GENERATION_MODEL="${2:-}"
      shift
      ;;
    --timeout)
      TIMEOUT="${2:-180}"
      shift
      ;;
    --retries)
      RETRIES="${2:-1}"
      shift
      ;;
    --retry-delay)
      RETRY_DELAY="${2:-2.0}"
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

if [[ -n "${OUTPUT}" ]]; then
  OUTPUT="$(normalize_path "${OUTPUT}")"
  mkdir -p "$(dirname "${OUTPUT}")"
fi
if [[ -n "${CASES}" ]]; then
  CASES="$(normalize_path "${CASES}")"
fi

python_args=(-m app.services.student_eval_runner --generation-model "${GENERATION_MODEL}" --timeout "${TIMEOUT}" --retries "${RETRIES}" --retry-delay "${RETRY_DELAY}")
if [[ -n "${CASES}" ]]; then
  python_args+=(--cases "${CASES}")
fi
for case_id in "${CASE_IDS[@]}"; do
  python_args+=(--case-id "${case_id}")
done

if [[ -n "${OUTPUT}" ]]; then
  CONTAINER_OUTPUT="/tmp/student-eval-runner-output.json"
  python_args+=(--output "${CONTAINER_OUTPUT}")
  docker compose exec -T assistant_api python "${python_args[@]}"
  ASSISTANT_CONTAINER_ID="$(docker compose ps -q assistant_api)"
  docker cp "${ASSISTANT_CONTAINER_ID}:${CONTAINER_OUTPUT}" "${OUTPUT}"
else
  docker compose exec -T assistant_api python "${python_args[@]}"
fi
