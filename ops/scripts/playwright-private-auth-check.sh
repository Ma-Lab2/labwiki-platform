#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

BASE_URL="${BASE_URL:-http://localhost:8443}"
PRIVATE_USER="${PRIVATE_ADMIN_USER:-admin}"
PRIVATE_PASSWORD_FILE="${PRIVATE_PASSWORD_FILE:-${ROOT_DIR}/secrets/private_admin_password.txt}"
SESSION_NAME="${SESSION_NAME:-labwiki-auth-check}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ARTIFACT_DIR="${ARTIFACT_DIR:-${ROOT_DIR}/backups/validation/playwright-private-auth-${TIMESTAMP}}"

usage() {
  cat <<EOF
Usage: bash ops/scripts/playwright-private-auth-check.sh [options]

Options:
  --base-url <url>         Private wiki entry (default: ${BASE_URL})
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

mkdir -p "${ARTIFACT_DIR}"

PRIVATE_PASSWORD="$(<"${PRIVATE_PASSWORD_FILE}")"
RUN_ID="$(date +%s)"
STUDENT_USERNAME="student_${RUN_ID}"
STUDENT_CANONICAL_USERNAME="Student ${RUN_ID}"
STUDENT_NAME="测试学生${RUN_ID}"
STUDENT_ID="S${RUN_ID}"
STUDENT_EMAIL="student_${RUN_ID}@lab.example.com"
STUDENT_PASSWORD="StudentPass!${RUN_ID}"

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
STUDENT_USERNAME_JSON="$(python - <<'PY' "${STUDENT_USERNAME}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
STUDENT_NAME_JSON="$(python - <<'PY' "${STUDENT_NAME}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
STUDENT_CANONICAL_USERNAME_JSON="$(python - <<'PY' "${STUDENT_CANONICAL_USERNAME}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
STUDENT_ID_JSON="$(python - <<'PY' "${STUDENT_ID}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
STUDENT_EMAIL_JSON="$(python - <<'PY' "${STUDENT_EMAIL}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
STUDENT_PASSWORD_JSON="$(python - <<'PY' "${STUDENT_PASSWORD}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"

cleanup() {
  playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
}
trap cleanup EXIT

reset_browser_session() {
  playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
  playwright-cli -s="${SESSION_NAME}" delete-data >/dev/null 2>&1 || true
  playwright-cli -s="${SESSION_NAME}" open about:blank >/dev/null
}

wait_for_page_ready() {
  playwright-cli -s="${SESSION_NAME}" run-code "async page => {
    await page.waitForLoadState('domcontentloaded');
    try {
      await page.waitForLoadState('networkidle', { timeout: 5000 });
    } catch (error) {}
  }" >/dev/null
}

wait_for_http_ok() {
  local url="$1"
  local code=''
  local attempt=0

  while (( attempt < 30 )); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "${url}" || true)"
    if [[ "${code}" =~ ^2[0-9][0-9]$ || "${code}" =~ ^3[0-9][0-9]$ ]]; then
      return 0
    fi
    attempt=$(( attempt + 1 ))
    sleep 1
  done

  echo "Timed out waiting for ${url} to become ready; last status=${code:-unreachable}" >&2
  exit 1
}

pl_eval_json() {
  local expr="$1"
  local output
  local raw
  output="$(playwright-cli -s="${SESSION_NAME}" eval "${expr}")"
  raw="$(printf '%s\n' "${output}" | sed -n '/^### Result/{n;p;}' | head -n 1)"
  if [[ -z "${raw}" ]]; then
    printf 'Failed to parse playwright eval output for expression: %s\n' "${expr}" >&2
    printf '%s\n' "${output}" >&2
    exit 1
  fi
  python - <<'PY' "${raw}"
import json
import sys
print(json.loads(sys.argv[1]))
PY
}

assert_equals() {
  local value="$1"
  local expected="$2"
  local message="$3"
  if [[ "${value}" != "${expected}" ]]; then
    echo "${message}: got '${value}', expected '${expected}'" >&2
    exit 1
  fi
}

wait_for_http_ok "${BASE_URL}/index.php?title=Special:%E5%AD%A6%E7%94%9F%E6%B3%A8%E5%86%8C"

playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
playwright-cli -s="${SESSION_NAME}" delete-data >/dev/null 2>&1 || true
playwright-cli -s="${SESSION_NAME}" open about:blank >/dev/null
playwright-cli -s="${SESSION_NAME}" goto "${BASE_URL}/index.php?title=Special:%E5%AD%A6%E7%94%9F%E6%B3%A8%E5%86%8C" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.getByLabel('姓名').fill(${STUDENT_NAME_JSON});
  await page.getByLabel('学号').fill(${STUDENT_ID_JSON});
  await page.getByLabel('邮箱').fill(${STUDENT_EMAIL_JSON});
  await page.getByLabel('用户名').fill(${STUDENT_USERNAME_JSON});
  await page.getByLabel('密码').fill(${STUDENT_PASSWORD_JSON});
  await page.getByRole('button', { name: '提交注册申请' }).click();
  await page.waitForLoadState('networkidle');
}" >/dev/null
wait_for_page_ready

SIGNUP_SUCCESS="$(pl_eval_json 'document.body.textContent.includes("注册申请已提交")')"
assert_equals "${SIGNUP_SUCCESS}" "True" "Student registration request did not submit successfully"

playwright-cli -s="${SESSION_NAME}" goto "${BASE_URL}/index.php?title=Special:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95" >/dev/null
wait_for_page_ready
NATIVE_LOGIN_FORM="$(pl_eval_json "Boolean(document.querySelector('form[name=userlogin], #userloginForm'))")"
assert_equals "${NATIVE_LOGIN_FORM}" "True" "Native MediaWiki login form is not available"
CUSTOM_LOGIN_PRESENT="$(pl_eval_json "Boolean(document.querySelector('.labauth-login-shell'))")"
assert_equals "${CUSTOM_LOGIN_PRESENT}" "False" "Native login route is still intercepted by the custom login shell"
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.getByLabel('用户名').fill(${PRIVATE_USER_JSON});
  await page.getByLabel('密码').fill(${PRIVATE_PASSWORD_JSON});
  await page.getByRole('button', { name: '登录' }).click();
  await page.waitForLoadState('networkidle');
}" >/dev/null
wait_for_page_ready

playwright-cli -s="${SESSION_NAME}" goto "${BASE_URL}/index.php?title=Special:%E8%B4%A6%E6%88%B7%E7%AE%A1%E7%90%86%E5%90%8E%E5%8F%B0" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.evaluate(() => {
    window.confirm = () => true;
  });
  const card = page.locator('.labauth-request-card', { hasText: ${STUDENT_USERNAME_JSON} }).first();
  await card.getByRole('button', { name: '审批通过' }).click();
  await page.waitForLoadState('networkidle');
}" >/dev/null
wait_for_page_ready

APPROVED_USER_VISIBLE="$(pl_eval_json "document.body.textContent.includes(${STUDENT_CANONICAL_USERNAME_JSON})")"
assert_equals "${APPROVED_USER_VISIBLE}" "True" "Approved student account is not visible in the admin console"

reset_browser_session

playwright-cli -s="${SESSION_NAME}" goto "${BASE_URL}/index.php?title=Special:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.getByLabel('用户名').fill(${STUDENT_USERNAME_JSON});
  await page.getByLabel('密码').fill(${STUDENT_PASSWORD_JSON});
  await page.getByRole('button', { name: '登录' }).click();
  await page.waitForLoadState('networkidle');
}" >/dev/null
wait_for_page_ready

POST_STUDENT_LOGIN_USER="$(pl_eval_json "window.mw && mw.config.get('wgUserName') === ${STUDENT_CANONICAL_USERNAME_JSON}")"
assert_equals "${POST_STUDENT_LOGIN_USER}" "True" "Approved student could not log in through the native MediaWiki login page"

reset_browser_session

playwright-cli -s="${SESSION_NAME}" goto "${BASE_URL}/index.php?title=Special:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.getByLabel('用户名').fill(${PRIVATE_USER_JSON});
  await page.getByLabel('密码').fill(${PRIVATE_PASSWORD_JSON});
  await page.getByRole('button', { name: '登录' }).click();
  await page.waitForLoadState('networkidle');
}" >/dev/null
wait_for_page_ready

playwright-cli -s="${SESSION_NAME}" goto "${BASE_URL}/index.php?title=Special:%E8%B4%A6%E6%88%B7%E7%AE%A1%E7%90%86%E5%90%8E%E5%8F%B0" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.evaluate(() => {
    window.confirm = () => true;
  });
  const userRow = page.locator('.labauth-user-row', { hasText: ${STUDENT_CANONICAL_USERNAME_JSON} }).first();
  await userRow.getByRole('button', { name: '停用' }).click();
  await page.waitForLoadState('networkidle');
}" >/dev/null
wait_for_page_ready

STUDENT_DISABLED_VISIBLE="$(pl_eval_json "document.body.textContent.includes(${STUDENT_CANONICAL_USERNAME_JSON}) && document.body.textContent.includes('disabled')")"
assert_equals "${STUDENT_DISABLED_VISIBLE}" "True" "Student account was not disabled in the admin console"

reset_browser_session

playwright-cli -s="${SESSION_NAME}" goto "${BASE_URL}/index.php?title=Special:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.getByLabel('用户名').fill(${STUDENT_USERNAME_JSON});
  await page.getByLabel('密码').fill(${STUDENT_PASSWORD_JSON});
  await page.getByRole('button', { name: '登录' }).click();
  await page.waitForLoadState('networkidle');
}" >/dev/null
wait_for_page_ready

DISABLED_LOGIN_REJECTED="$(pl_eval_json "document.body.textContent.includes('该账户已被管理员停用')")"
assert_equals "${DISABLED_LOGIN_REJECTED}" "True" "Disabled student account was still able to log in"

reset_browser_session

playwright-cli -s="${SESSION_NAME}" goto "${BASE_URL}/index.php?title=Special:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.getByLabel('用户名').fill(${PRIVATE_USER_JSON});
  await page.getByLabel('密码').fill(${PRIVATE_PASSWORD_JSON});
  await page.getByRole('button', { name: '登录' }).click();
  await page.waitForLoadState('networkidle');
}" >/dev/null
wait_for_page_ready

playwright-cli -s="${SESSION_NAME}" goto "${BASE_URL}/index.php?title=Special:%E8%B4%A6%E6%88%B7%E7%AE%A1%E7%90%86%E5%90%8E%E5%8F%B0" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.evaluate(() => {
    window.confirm = () => true;
  });
  const userRow = page.locator('.labauth-user-row', { hasText: ${STUDENT_CANONICAL_USERNAME_JSON} }).first();
  await userRow.getByRole('button', { name: '恢复' }).click();
  await page.waitForLoadState('networkidle');
}" >/dev/null
wait_for_page_ready

STUDENT_ACTIVE_VISIBLE="$(pl_eval_json "document.body.textContent.includes(${STUDENT_CANONICAL_USERNAME_JSON}) && document.body.textContent.includes('active')")"
assert_equals "${STUDENT_ACTIVE_VISIBLE}" "True" "Student account was not restored in the admin console"
