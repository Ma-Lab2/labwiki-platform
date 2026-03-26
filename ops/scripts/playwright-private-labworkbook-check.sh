#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

BASE_URL="${BASE_URL:-http://localhost:8443}"
PRIVATE_USER="${PRIVATE_ADMIN_USER:-admin}"
PRIVATE_PASSWORD_FILE="${PRIVATE_PASSWORD_FILE:-${ROOT_DIR}/secrets/private_admin_password.txt}"
SESSION_NAME="${SESSION_NAME:-labwiki-labworkbook-check}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ARTIFACT_DIR="${ARTIFACT_DIR:-${ROOT_DIR}/backups/validation/playwright-private-labworkbook-${TIMESTAMP}}"
WORKBOOK_PAGE="Special:实验工作簿"
SHOT_PAGE="Shot:2025-09-26-Run96-Shot001"

usage() {
  cat <<EOF
Usage: bash ops/scripts/playwright-private-labworkbook-check.sh [options]

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

cleanup() {
  playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_for_page_ready() {
  playwright-cli -s="${SESSION_NAME}" run-code "async page => {
    await page.waitForLoadState('domcontentloaded');
    try {
      await page.waitForLoadState('networkidle', { timeout: 5000 });
    } catch (error) {}
  }" >/dev/null
}

playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
playwright-cli -s="${SESSION_NAME}" delete-data >/dev/null 2>&1 || true
playwright-cli -s="${SESSION_NAME}" open about:blank >/dev/null
playwright-cli -s="${SESSION_NAME}" goto "${BASE_URL}/index.php?title=Special:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95" >/dev/null
wait_for_page_ready

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.getByLabel('用户名').fill(${PRIVATE_USER_JSON});
  await page.getByLabel('密码').fill(${PRIVATE_PASSWORD_JSON});
  await page.getByRole('button', { name: '登录' }).click();
  await page.waitForLoadState('networkidle');
}" >/dev/null
wait_for_page_ready

playwright-cli -s="${SESSION_NAME}" goto "${BASE_URL}/index.php?title=Special:%E5%AE%9E%E9%AA%8C%E5%B7%A5%E4%BD%9C%E7%B0%BF" >/dev/null
wait_for_page_ready

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.waitForSelector('#labworkbook-root .labworkbook-input');
  await page.waitForFunction(() => document.body.textContent.includes('shotlist20250926.xls') && document.body.textContent.includes('shotlist20251111.xls'));
  await page.getByPlaceholder('例如 Run96').fill('Run96');
  await page.getByRole('button', { name: '保存 Run 标签' }).click();
  await page.waitForFunction(() => document.body.textContent.includes('已保存工作簿 Run 标签。'));
  await page.getByPlaceholder('筛选 No / 靶类型 / 靶位 / 备注 / 时间').fill('Cu100');
  await page.waitForFunction(() => document.body.textContent.includes('Shot:2025-09-26-Run96-Shot096'));
  await page.getByPlaceholder('筛选 No / 靶类型 / 靶位 / 备注 / 时间').fill('');
  await page.getByRole('button', { name: '生成 / 更新 Shot 页面' }).first().click();
  await page.waitForFunction(() => document.body.textContent.includes('已同步到 Shot:2025-09-26-Run96-Shot001'));
}" >/dev/null

playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/labworkbook-special.yml" >/dev/null

docker compose exec -T mw_private php maintenance/run.php purgePage "${SHOT_PAGE}" >/dev/null

PARSED_OUTPUT="$(docker compose exec -T mw_private bash -lc "php maintenance/run.php getText '${SHOT_PAGE}' | php maintenance/run.php parse --title '${SHOT_PAGE}'")"

grep -q '主台账事实层' <<<"${PARSED_OUTPUT}"
grep -q '主台账 No：1' <<<"${PARSED_OUTPUT}"
grep -q '压缩后：20mJ' <<<"${PARSED_OUTPUT}"
grep -q '靶位：0' <<<"${PARSED_OUTPUT}"

printf '%s\n' "${PARSED_OUTPUT}" > "${ARTIFACT_DIR}/shot-parsed.html"

cat > "${ARTIFACT_DIR}/report.md" <<EOF
# LabWorkbook 回归报告

- Base URL: ${BASE_URL}
- Workbook page: ${WORKBOOK_PAGE}
- Shot page: ${SHOT_PAGE}
- Workbook source files detected: yes
- Run label save confirmed: yes
- Main log filter confirmed: yes
- Shot sync confirmed: yes
- Parsed shot facts block confirmed: yes
EOF

printf 'Artifacts written to %s\n' "${ARTIFACT_DIR}"
