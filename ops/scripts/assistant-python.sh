#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_NAME="${ASSISTANT_CONDA_ENV_NAME:-labwiki-assistant-py312}"
ENV_FILE="${ROOT_DIR}/assistant_api/environment.conda.yml"
REQUIREMENTS_FILE="${ROOT_DIR}/assistant_api/requirements.txt"
WORKDIR="${ROOT_DIR}"
ENSURE_ENV="false"
PRINT_DOCTOR="false"
PYTHON_SPEC=""

usage() {
  cat <<'EOF'
Usage: bash ops/scripts/assistant-python.sh [options] [-- python-args...]

Runs assistant-related local Python commands in the dedicated conda Python 3.12 environment.

Options:
  --ensure           Create/update the conda environment and sync assistant requirements
  --cwd <path>       Repo-relative or absolute working directory for the Python command
  --doctor           Print the resolved Python environment details and exit
  --help             Show this help text

Examples:
  bash ops/scripts/assistant-python.sh --ensure
  bash ops/scripts/assistant-python.sh --cwd assistant_api -m unittest discover -s tests -v
  bash ops/scripts/assistant-python.sh -m compileall assistant_api/app
EOF
}

load_conda() {
  local conda_base

  if command -v conda >/dev/null 2>&1; then
    conda_base="$(conda info --base)"
  elif [[ -f "${HOME}/miniconda3/etc/profile.d/conda.sh" ]]; then
    conda_base="${HOME}/miniconda3"
  else
    echo "conda is required but was not found." >&2
    exit 1
  fi

  # shellcheck disable=SC1090
  source "${conda_base}/etc/profile.d/conda.sh"
}

normalize_path() {
  local input="$1"

  if [[ -z "${input}" ]]; then
    printf '%s\n' "${ROOT_DIR}"
    return 0
  fi

  if [[ "${input}" = /* ]]; then
    realpath -m "${input}"
  else
    realpath -m "${ROOT_DIR}/${input}"
  fi
}

env_exists() {
  conda env list | awk 'NR > 2 && $1 != "" { print $1 }' | grep -Fxq "${ENV_NAME}"
}

load_python_spec() {
  PYTHON_SPEC="$(awk -F'- ' '/python=/{print $2; exit}' "${ENV_FILE}")"
  if [[ -z "${PYTHON_SPEC}" ]]; then
    echo "Could not determine python spec from ${ENV_FILE}" >&2
    exit 1
  fi
}

ensure_env() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Environment file not found: ${ENV_FILE}" >&2
    exit 1
  fi
  if [[ ! -f "${REQUIREMENTS_FILE}" ]]; then
    echo "Requirements file not found: ${REQUIREMENTS_FILE}" >&2
    exit 1
  fi

  load_python_spec

  if env_exists; then
    conda install -y -n "${ENV_NAME}" "${PYTHON_SPEC}" pip
  else
    conda create -y -n "${ENV_NAME}" "${PYTHON_SPEC}" pip
  fi

  conda run --no-capture-output -n "${ENV_NAME}" env PYTHONNOUSERSITE=1 python -m pip install \
    --disable-pip-version-check \
    --ignore-installed \
    -r "${REQUIREMENTS_FILE}"
}

print_doctor() {
  conda run --no-capture-output -n "${ENV_NAME}" env PYTHONNOUSERSITE=1 python - <<'PY'
import platform
import sys

print(f"python_executable={sys.executable}")
print(f"python_version={platform.python_version()}")
print(f"usersite_enabled={sys.flags.no_user_site == 0}")
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ensure)
      ENSURE_ENV="true"
      ;;
    --cwd)
      WORKDIR="$(normalize_path "${2:-}")"
      shift
      ;;
    --doctor)
      PRINT_DOCTOR="true"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
  shift
done

load_conda

if [[ "${ENSURE_ENV}" == "true" ]]; then
  ensure_env
fi

if ! env_exists; then
  echo "Conda environment '${ENV_NAME}' is missing. Run: bash ops/scripts/assistant-python.sh --ensure" >&2
  exit 1
fi

if [[ "${PRINT_DOCTOR}" == "true" ]]; then
  print_doctor
  exit 0
fi

if [[ $# -eq 0 ]]; then
  usage
  exit 0
fi

cd "${WORKDIR}"
conda run --no-capture-output -n "${ENV_NAME}" env PYTHONNOUSERSITE=1 python "$@"
