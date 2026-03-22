#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

compose_cmd=(docker compose -f compose.yaml)
if [[ "${LABWIKI_LOCAL_OVERRIDE:-false}" == "true" ]]; then
  compose_cmd+=(-f compose.override.yaml)
fi

OUTPUT=""
LIMIT="5"
CASES=""
TOKENIZER_ARGS=()
NORMALIZATION_ARGS=()
STRATEGY_ARGS=()
VECTOR_BACKEND_ARGS=()
CONTAINER_CASES_PATH=""

usage() {
  cat <<'EOF'
Usage: bash ops/scripts/benchmark-assistant-retrieval.sh [options]

Options:
  --output <path>          Write the JSON report to a repo-relative path
  --cases <path>           Use a custom benchmark case JSON file
  --limit <k>              Top-k per retrieval run (default: 5)
  --tokenizer-mode <mode>  Repeatable; defaults to mixed/ascii/cjk
  --normalization-mode <m> Repeatable; defaults to basic/lab
  --strategy <name>        Repeatable; defaults to keyword/vector/hybrid
  --vector-backend <name>  Repeatable; defaults to pgvector/qdrant_local
  --help                   Show this help text
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
    --limit)
      LIMIT="${2:-5}"
      shift
      ;;
    --tokenizer-mode)
      TOKENIZER_ARGS+=("--tokenizer-mode" "${2:-}")
      shift
      ;;
    --normalization-mode)
      NORMALIZATION_ARGS+=("--normalization-mode" "${2:-}")
      shift
      ;;
    --strategy)
      STRATEGY_ARGS+=("--strategy" "${2:-}")
      shift
      ;;
    --vector-backend)
      VECTOR_BACKEND_ARGS+=("--vector-backend" "${2:-}")
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

ASSISTANT_CONTAINER_ID="$("${compose_cmd[@]}" ps -q assistant_api)"
if [[ -z "${ASSISTANT_CONTAINER_ID}" ]]; then
  echo "assistant_api container is not running." >&2
  exit 1
fi

python_args=(python -m app.services.retrieval_benchmark --limit "${LIMIT}")
python_args+=("${TOKENIZER_ARGS[@]}")
python_args+=("${NORMALIZATION_ARGS[@]}")
python_args+=("${STRATEGY_ARGS[@]}")
python_args+=("${VECTOR_BACKEND_ARGS[@]}")
if [[ -n "${CASES}" ]]; then
  CONTAINER_CASES_PATH="/tmp/assistant-retrieval-cases.json"
  docker cp "${CASES}" "${ASSISTANT_CONTAINER_ID}:${CONTAINER_CASES_PATH}"
  python_args+=(--cases "${CONTAINER_CASES_PATH}")
fi

if [[ -n "${OUTPUT}" ]]; then
  mkdir -p "$(dirname "${OUTPUT}")"
  "${compose_cmd[@]}" exec -T assistant_api "${python_args[@]}" | tee "${OUTPUT}"
else
  "${compose_cmd[@]}" exec -T assistant_api "${python_args[@]}"
fi
