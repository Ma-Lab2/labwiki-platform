#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT_DIR}"
mkdir -p secrets

rand_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 24
  else
    python - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
  fi
}

write_if_missing() {
  local path="$1"
  local value="$2"
  if [[ ! -f "${path}" ]]; then
    printf '%s\n' "${value}" > "${path}"
    chmod 600 "${path}"
    printf 'created %s\n' "${path}"
  else
    printf 'kept existing %s\n' "${path}"
  fi
}

prompt_if_empty() {
  local var_name="$1"
  local prompt_text="$2"
  local value="${!var_name:-}"
  if [[ -z "${value}" ]]; then
    read -r -s -p "${prompt_text}: " value
    printf '\n' >&2
  fi
  printf '%s' "${value}"
}

PUBLIC_ADMIN_PASSWORD="$(prompt_if_empty PUBLIC_ADMIN_PASSWORD 'Public wiki admin password')"
PRIVATE_ADMIN_PASSWORD="$(prompt_if_empty PRIVATE_ADMIN_PASSWORD 'Private wiki admin password')"

write_if_missing secrets/db_root_password.txt "${DB_ROOT_PASSWORD:-$(rand_secret)}"
write_if_missing secrets/public_db_password.txt "${PUBLIC_DB_PASSWORD:-$(rand_secret)}"
write_if_missing secrets/private_db_password.txt "${PRIVATE_DB_PASSWORD:-$(rand_secret)}"
write_if_missing secrets/assistant_db_password.txt "${ASSISTANT_DB_PASSWORD:-$(rand_secret)}"
write_if_missing secrets/public_admin_password.txt "${PUBLIC_ADMIN_PASSWORD}"
write_if_missing secrets/private_admin_password.txt "${PRIVATE_ADMIN_PASSWORD}"
