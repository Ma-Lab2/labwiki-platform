#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

BASE_URL="${BASE_URL:-http://192.168.1.2:8443}"
LOOPBACK_URL="${LOOPBACK_URL:-http://127.0.0.1:8443}"
PRIVATE_USER="${PRIVATE_ADMIN_USER:-admin}"
PRIVATE_PASSWORD_FILE="${PRIVATE_PASSWORD_FILE:-${ROOT_DIR}/secrets/private_admin_password.txt}"
SESSION_NAME="${SESSION_NAME:-labwiki-private-check}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ARTIFACT_DIR="${ARTIFACT_DIR:-${ROOT_DIR}/backups/validation/playwright-private-session-${TIMESTAMP}}"

usage() {
  cat <<EOF
Usage: bash ops/scripts/playwright-private-session-check.sh [options]

Options:
  --base-url <url>         Canonical private entry (default: ${BASE_URL})
  --loopback-url <url>     Loopback entry used to verify redirect behavior (default: ${LOOPBACK_URL})
  --session-name <name>    Playwright session name (default: ${SESSION_NAME})
  --artifact-dir <path>    Directory for snapshots and report
  --help                   Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="${2:?missing value for --base-url}"
      shift 2
      ;;
    --loopback-url)
      LOOPBACK_URL="${2:?missing value for --loopback-url}"
      shift 2
      ;;
    --session-name)
      SESSION_NAME="${2:?missing value for --session-name}"
      shift 2
      ;;
    --artifact-dir)
      ARTIFACT_DIR="${2:?missing value for --artifact-dir}"
      shift 2
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
done

if [[ ! -f "${PRIVATE_PASSWORD_FILE}" ]]; then
  echo "Private admin password file not found: ${PRIVATE_PASSWORD_FILE}" >&2
  exit 1
fi

PRIVATE_PASSWORD="$(<"${PRIVATE_PASSWORD_FILE}")"
PRIVATE_USER_JSON="$(python - <<'PY' "${PRIVATE_USER}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
PRIVATE_PASSWORD_JSON="$(python - <<'PY' "${PRIVATE_PASSWORD}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
CANONICAL_HOST="$(python - <<'PY' "${BASE_URL}"
from urllib.parse import urlparse
import sys
print(urlparse(sys.argv[1]).hostname or "")
PY
)"
mkdir -p "${ARTIFACT_DIR}"
REPORT_FILE="${ARTIFACT_DIR}/report.md"

cleanup() {
  playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
}
trap cleanup EXIT

pl_eval_json() {
  local expr="$1"
  local raw
  raw="$(playwright-cli -s="${SESSION_NAME}" eval "${expr}" | sed -n '/^### Result/{n;p;}' | head -n 1)"
  python - <<'PY' "${raw}"
import json
import sys
value = sys.argv[1]
print(json.loads(value))
PY
}

capture_log_artifact() {
  local command_name="$1"
  local target_name="$2"
  local output
  local source_path
  output="$(playwright-cli -s="${SESSION_NAME}" "${command_name}")"
  printf '%s\n' "${output}" > "${ARTIFACT_DIR}/${target_name}.command.txt"
  source_path="$(printf '%s\n' "${output}" | sed -n 's|.*(\(.*\)).*|\1|p' | head -n 1)"
  if [[ -n "${source_path}" && -f "${ROOT_DIR}/${source_path}" ]]; then
    cp "${ROOT_DIR}/${source_path}" "${ARTIFACT_DIR}/${target_name}"
  fi
}

assert_prefix() {
  local value="$1"
  local prefix="$2"
  local message="$3"
  if [[ "${value}" != "${prefix}"* ]]; then
    echo "${message}: got '${value}', expected prefix '${prefix}'" >&2
    exit 1
  fi
}

wait_for_private_entry() {
  local attempts=0
  local login_path="/index.php?title=%E7%89%B9%E6%AE%8A:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95"
  until docker compose exec -T caddy_private sh -lc \
    "curl -fsS -H 'Host: ${CANONICAL_HOST}' -o /dev/null 'http://127.0.0.1${login_path}'"; do
    attempts=$((attempts + 1))
    if [[ ${attempts} -ge 15 ]]; then
      echo "Private wiki did not become ready for canonical host ${CANONICAL_HOST}" >&2
      exit 1
    fi
    sleep 2
  done
}

wait_for_private_entry
playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
playwright-cli -s="${SESSION_NAME}" delete-data >/dev/null 2>&1 || true
playwright-cli -s="${SESSION_NAME}" open about:blank >/dev/null
playwright-cli -s="${SESSION_NAME}" cookie-clear >/dev/null
playwright-cli -s="${SESSION_NAME}" localstorage-clear >/dev/null
playwright-cli -s="${SESSION_NAME}" sessionstorage-clear >/dev/null
playwright-cli -s="${SESSION_NAME}" goto "${LOOPBACK_URL}" >/dev/null

LOOPBACK_HREF="$(pl_eval_json 'window.location.href')"
LOOPBACK_TITLE="$(pl_eval_json 'document.title')"
assert_prefix "${LOOPBACK_HREF}" "${LOOPBACK_URL}" "Loopback entry left the loopback host"
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/01-loopback-home.yml" >/dev/null

LOGIN_URL="${LOOPBACK_URL}/index.php?title=%E7%89%B9%E6%AE%8A:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95"
playwright-cli -s="${SESSION_NAME}" goto "${LOGIN_URL}" >/dev/null
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.getByRole('textbox', { name: '用户名' }).fill(${PRIVATE_USER_JSON});
  await page.getByRole('textbox', { name: '密码' }).fill(${PRIVATE_PASSWORD_JSON});
  await page.getByRole('button', { name: '登录' }).click();
  await page.waitForLoadState('networkidle');
}" >/dev/null

POST_LOGIN_HREF="$(pl_eval_json 'window.location.href')"
POST_LOGIN_TITLE="$(pl_eval_json 'document.title')"
assert_prefix "${POST_LOGIN_HREF}" "${LOOPBACK_URL}" "Login landed on unexpected host"
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/02-post-login.yml" >/dev/null

playwright-cli -s="${SESSION_NAME}" reload >/dev/null
RELOAD_HREF="$(pl_eval_json 'window.location.href')"
RELOAD_TITLE="$(pl_eval_json 'document.title')"
assert_prefix "${RELOAD_HREF}" "${LOOPBACK_URL}" "Reload left loopback host"
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/03-after-reload.yml" >/dev/null

ASSISTANT_URL="${LOOPBACK_URL}/index.php?title=Special:%E7%9F%A5%E8%AF%86%E5%8A%A9%E6%89%8B"
playwright-cli -s="${SESSION_NAME}" goto "${ASSISTANT_URL}" >/dev/null
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/04-assistant.yml" >/dev/null
ASSISTANT_HREF="$(pl_eval_json 'window.location.href')"
ASSISTANT_TITLE="$(pl_eval_json 'document.title')"
HOST_STORAGE_VALUE="$(playwright-cli -s="${SESSION_NAME}" localstorage-get labassistant-active-host | sed -n '/^### Result/{n;p;}' | head -n 1 || true)"
SESSION_STORAGE_VALUE="$(playwright-cli -s="${SESSION_NAME}" localstorage-get labassistant-active-session-id | sed -n '/^### Result/{n;p;}' | head -n 1 || true)"

capture_log_artifact console "05-console.log"
capture_log_artifact network "06-network.log"

cat > "${REPORT_FILE}" <<EOF
# Private Session Check

- Canonical base URL: \`${BASE_URL}\`
- Loopback URL: \`${LOOPBACK_URL}\`
- Loopback landing URL: \`${LOOPBACK_HREF}\`
- Loopback page title: \`${LOOPBACK_TITLE}\`
- Post-login URL: \`${POST_LOGIN_HREF}\`
- Post-login title: \`${POST_LOGIN_TITLE}\`
- After reload URL: \`${RELOAD_HREF}\`
- After reload title: \`${RELOAD_TITLE}\`
- Assistant URL: \`${ASSISTANT_HREF}\`
- Assistant title: \`${ASSISTANT_TITLE}\`
- Assistant localStorage host key: \`${HOST_STORAGE_VALUE}\`
- Assistant session key: \`${SESSION_STORAGE_VALUE}\`

## Artifacts

- \`01-loopback-home.yml\`
- \`02-post-login.yml\`
- \`03-after-reload.yml\`
- \`04-assistant.yml\`
- \`05-console.log\`
- \`06-network.log\`
EOF

printf 'Report written to %s\n' "${REPORT_FILE}"
