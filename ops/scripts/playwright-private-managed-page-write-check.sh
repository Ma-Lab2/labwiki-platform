#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

BASE_URL="${BASE_URL:-http://localhost:8443}"
LOOPBACK_URL="${LOOPBACK_URL:-http://localhost:8443}"
PRIVATE_USER="${PRIVATE_ADMIN_USER:-admin}"
PRIVATE_PASSWORD_FILE="${PRIVATE_PASSWORD_FILE:-${ROOT_DIR}/secrets/private_admin_password.txt}"
SESSION_NAME="${SESSION_NAME:-labwiki-private-managed-page-write-check}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ARTIFACT_DIR="${ARTIFACT_DIR:-${ROOT_DIR}/backups/validation/playwright-private-managed-page-write-${TIMESTAMP}}"
REPORT_FILE="${ARTIFACT_DIR}/report.md"

usage() {
  cat <<USAGE
Usage: bash ops/scripts/playwright-private-managed-page-write-check.sh [options]

Options:
  --base-url <url>         Canonical private entry (default: ${BASE_URL})
  --loopback-url <url>     Loopback entry used to verify behavior (default: ${LOOPBACK_URL})
  --session-name <name>    Playwright session name (default: ${SESSION_NAME})
  --artifact-dir <path>    Directory for snapshots and report
  --help                   Show this help text
USAGE
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

if ! command -v playwright-cli >/dev/null 2>&1; then
  echo "playwright-cli is required but not found in PATH" >&2
  exit 1
fi

json_string() {
  python - <<'PY' "$1"
import json
import sys
print(json.dumps(sys.argv[1], ensure_ascii=False))
PY
}

assert_true() {
  local value="$1"
  local message="$2"
  if [[ "${value}" != "True" ]]; then
    echo "${message}: got '${value}', expected 'True'" >&2
    exit 1
  fi
}

run_code_result() {
  local code="$1"
  local output
  local raw
  output="$(playwright-cli -s="${SESSION_NAME}" run-code "${code}")"
  raw="$(printf '%s\n' "${output}" | sed -n '/^### Result/{n;p;}' | head -n 1)"
  if [[ -z "${raw}" ]]; then
    printf 'Failed to parse playwright run-code output\n' >&2
    printf '%s\n' "${output}" >&2
    exit 1
  fi
  python - <<'PY' "${raw}"
import json
import sys
value = json.loads(sys.argv[1])
if isinstance(value, bool):
    print('True' if value else 'False')
elif value is None:
    print('')
else:
    print(json.dumps(value, ensure_ascii=False))
PY
}

wait_for_page_ready() {
  playwright-cli -s="${SESSION_NAME}" run-code "async page => {
    await page.waitForLoadState('domcontentloaded');
    try {
      await page.waitForLoadState('networkidle', { timeout: 8000 });
    } catch (error) {
    }
  }" >/dev/null
}

wait_for_private_entry() {
  local attempts=0
  local login_path="/index.php?title=%E7%89%B9%E6%AE%8A:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95"
  local canonical_host
  canonical_host="$(python - <<'PY' "${BASE_URL}"
from urllib.parse import urlparse
import sys
print(urlparse(sys.argv[1]).hostname or '')
PY
)"
  until docker compose exec -T caddy_private sh -lc \
    "curl -fsS -H 'Host: ${canonical_host}' -o /dev/null 'http://127.0.0.1${login_path}'"; do
    attempts=$((attempts + 1))
    if [[ ${attempts} -ge 20 ]]; then
      echo "Private wiki did not become ready for canonical host ${canonical_host}" >&2
      exit 1
    fi
    sleep 2
  done
}

login_private_wiki() {
  local login_url user_json password_json
  login_url="${LOOPBACK_URL}/index.php?title=%E7%89%B9%E6%AE%8A:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95"
  user_json="$(json_string "${PRIVATE_USER}")"
  password_json="$(json_string "$(<"${PRIVATE_PASSWORD_FILE}")")"
  playwright-cli -s="${SESSION_NAME}" goto "${login_url}" >/dev/null
  wait_for_page_ready
  playwright-cli -s="${SESSION_NAME}" run-code "async page => {
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.getByRole('textbox', { name: '用户名' }).fill(${user_json});
    await page.getByRole('textbox', { name: '密码' }).fill(${password_json});
    await page.getByRole('button', { name: '登录' }).click();
    await page.waitForLoadState('domcontentloaded');
    try {
      await page.waitForLoadState('networkidle', { timeout: 8000 });
    } catch (error) {
    }
  }" >/dev/null
}

run_case() {
  local label="$1"
  local encoded_title="$2"
  local target_page="$3"
  local target_section="$4"
  local prompt="$5"
  local stable_line="$6"
  local page_url raw_url page_url_json target_page_json target_section_json prompt_json stable_line_json
  local raw_contains raw_result api_result

  page_url="${LOOPBACK_URL}/index.php?title=${encoded_title}"
  raw_url="${page_url}&action=raw"
  page_url_json="$(json_string "${page_url}")"
  target_page_json="$(json_string "${target_page}")"
  target_section_json="$(json_string "${target_section}")"
  prompt_json="$(json_string "${prompt}")"
  stable_line_json="$(json_string "${stable_line}")"

  playwright-cli -s="${SESSION_NAME}" run-code "async page => {
    await page.goto(${page_url_json}, { waitUntil: 'domcontentloaded' });
    try {
      await page.waitForLoadState('networkidle', { timeout: 8000 });
    } catch (error) {
    }
  }" >/dev/null

  playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/${label}-preview.yml" >/dev/null

  api_result="$(run_code_result "async page => {
    return await page.evaluate(async ({ question, targetPage, targetSection, stableLine }) => {
      const config = window.mw && mw.config && mw.config.get('wgLabAssistant');
      if (!config || !config.apiBase) {
        throw new Error('wgLabAssistant.apiBase is missing');
      }
      const previewResponse = await fetch(config.apiBase + '/write/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          question,
          answer: '* ' + stableLine,
          context_pages: [targetPage],
          source_titles: [targetPage]
        })
      });
      const preview = await previewResponse.json();
      if (!previewResponse.ok) {
        throw new Error(preview.detail || 'write preview failed');
      }
      if (preview.target_page !== targetPage) {
        throw new Error('preview target mismatch: ' + preview.target_page);
      }
      if (preview.target_section !== targetSection) {
        throw new Error('preview section mismatch: ' + preview.target_section);
      }
      if (!String(preview.preview_text || '').includes(stableLine)) {
        throw new Error('preview text missing stable line');
      }
      const commitResponse = await fetch(config.apiBase + '/write/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ preview_id: preview.preview_id })
      });
      const commit = await commitResponse.json();
      if (!commitResponse.ok) {
        throw new Error(commit.detail || 'write commit failed');
      }
      return { preview, commit };
    }, {
      question: ${prompt_json},
      targetPage: ${target_page_json},
      targetSection: ${target_section_json},
      stableLine: ${stable_line_json}
    });
  }")"
  python - <<'PY' "${api_result}" > "${ARTIFACT_DIR}/${label}-api.json"
import json
import sys
print(json.dumps(json.loads(sys.argv[1]), ensure_ascii=False, indent=2))
PY

  playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/${label}-commit.yml" >/dev/null

  playwright-cli -s="${SESSION_NAME}" goto "${raw_url}" >/dev/null
  wait_for_page_ready
  raw_result="$(playwright-cli -s="${SESSION_NAME}" eval "document.body.innerText.includes(${stable_line_json})" | sed -n '/^### Result/{n;p;}' | head -n 1)"
  raw_contains="$(python - <<'PY' "${raw_result}"
import json
import sys
print('True' if json.loads(sys.argv[1]) else 'False')
PY
)"
  assert_true "${raw_contains}" "Raw page ${target_page} did not contain the stable line after commit"
}

mkdir -p "${ARTIFACT_DIR}"

cleanup() {
  playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_for_private_entry
playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
playwright-cli -s="${SESSION_NAME}" delete-data >/dev/null 2>&1 || true
playwright-cli -s="${SESSION_NAME}" open about:blank >/dev/null
playwright-cli -s="${SESSION_NAME}" cookie-clear >/dev/null
playwright-cli -s="${SESSION_NAME}" localstorage-clear >/dev/null
playwright-cli -s="${SESSION_NAME}" sessionstorage-clear >/dev/null

login_private_wiki

run_case \
  "meeting-index" \
  "Meeting:%E4%BC%9A%E8%AE%AE%E5%85%A5%E5%8F%A3" \
  "Meeting:会议入口" \
  "当前入口" \
  "给当前入口加一条：[[Meeting:实验复盘模板]]。" \
  "[[Meeting:实验复盘模板]]"

run_case \
  "faq-index" \
  "FAQ:%E5%B8%B8%E8%A7%81%E9%97%AE%E9%A2%98%E5%85%A5%E5%8F%A3" \
  "FAQ:常见问题入口" \
  "使用规则" \
  "给使用规则加一条：每个 FAQ 条目都要链接到对应 SOP、设备页或 shot 复盘页。" \
  "每个 FAQ 条目都要链接到对应 SOP、设备页或 shot 复盘页"

run_case \
  "project-index" \
  "Project:%E9%A1%B9%E7%9B%AE%E6%80%BB%E8%A7%88" \
  "Project:项目总览" \
  "当前入口" \
  "给当前入口加一条：[[Project:激光质子加速]]。" \
  "[[Project:激光质子加速]]"

cat > "${REPORT_FILE}" <<REPORT
# Managed Page Write Check

- Session: ${SESSION_NAME}
- Base URL: ${BASE_URL}
- Loopback URL: ${LOOPBACK_URL}
- Verified pages:
  - Meeting:会议入口 / 当前入口
  - FAQ:常见问题入口 / 使用规则
  - Project:项目总览 / 当前入口
- Commit path: /write/commit
- UI action: 确认提交
REPORT

echo "Managed page browser write check passed. Report: ${REPORT_FILE}"
