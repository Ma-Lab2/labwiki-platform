#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

BASE_URL="${BASE_URL:-http://localhost:8443}"
PRIVATE_USER="${PRIVATE_ADMIN_USER:-admin}"
PRIVATE_PASSWORD_FILE="${PRIVATE_PASSWORD_FILE:-${ROOT_DIR}/secrets/private_admin_password.txt}"
SESSION_NAME="${SESSION_NAME:-labwiki-private-assistant-operation-check}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ARTIFACT_DIR="${ARTIFACT_DIR:-${ROOT_DIR}/backups/validation/playwright-private-assistant-operation-${TIMESTAMP}}"
REPORT_FILE="${ARTIFACT_DIR}/report.md"

SHOT_PAGE_TITLE="Shot:Shot日志入口"
SHOT_PAGE_URL="${BASE_URL}/index.php?title=Shot:Shot日志入口"
NORMALIZED_RULE="必须备注原实验记录excel的实际电脑ID及文件夹位置"
BAD_RULE_PREFIX="加入一条规则：必须备注原实验记录excel的实际电脑ID及文件夹位置"
FORMAL_RULE="每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径"
REPLACE_OLD_RULE="打靶后立刻创建或补全页面"
REPLACE_NEW_RULE="打靶后应立刻创建或补全页面"

json_string() {
  python - <<'PY' "$1"
import json
import sys
print(json.dumps(sys.argv[1], ensure_ascii=False))
PY
}

run_code_result() {
  local code="$1"
  local output raw
  output="$(playwright-cli -s="${SESSION_NAME}" run-code "${code}")"
  raw="$(printf '%s\n' "${output}" | sed -n '/^### Result/{n;p;}' | head -n 1)"
  if [[ -z "${raw}" ]]; then
    printf 'Failed to parse playwright run-code output\n' >&2
    printf '%s\n' "${output}" >&2
    exit 1
  fi
  printf '%s\n' "${raw}"
}

if [[ ! -f "${PRIVATE_PASSWORD_FILE}" ]]; then
  echo "Private admin password file not found: ${PRIVATE_PASSWORD_FILE}" >&2
  exit 1
fi

if ! command -v playwright-cli >/dev/null 2>&1; then
  echo "playwright-cli is required but not found in PATH" >&2
  exit 1
fi

mkdir -p "${ARTIFACT_DIR}"

cleanup() {
  playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
}
trap cleanup EXIT

playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
playwright-cli -s="${SESSION_NAME}" delete-data >/dev/null 2>&1 || true
playwright-cli -s="${SESSION_NAME}" open about:blank >/dev/null
playwright-cli -s="${SESSION_NAME}" cookie-clear >/dev/null
playwright-cli -s="${SESSION_NAME}" localstorage-clear >/dev/null
playwright-cli -s="${SESSION_NAME}" sessionstorage-clear >/dev/null

LOGIN_URL="${BASE_URL}/index.php?title=%E7%89%B9%E6%AE%8A:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95"
USER_JSON="$(json_string "${PRIVATE_USER}")"
PASSWORD_JSON="$(json_string "$(<"${PRIVATE_PASSWORD_FILE}")")"
LOGIN_URL_JSON="$(json_string "${LOGIN_URL}")"
SHOT_PAGE_URL_JSON="$(json_string "${SHOT_PAGE_URL}")"
SHOT_PAGE_TITLE_JSON="$(json_string "${SHOT_PAGE_TITLE}")"
NORMALIZED_RULE_JSON="$(json_string "${NORMALIZED_RULE}")"
BAD_RULE_PREFIX_JSON="$(json_string "${BAD_RULE_PREFIX}")"
FORMAL_RULE_JSON="$(json_string "${FORMAL_RULE}")"
REPLACE_OLD_RULE_JSON="$(json_string "${REPLACE_OLD_RULE}")"
REPLACE_NEW_RULE_JSON="$(json_string "${REPLACE_NEW_RULE}")"

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.goto(${LOGIN_URL_JSON}, { waitUntil: 'domcontentloaded' });
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.getByRole('textbox', { name: '用户名' }).fill(${USER_JSON});
  await page.getByRole('textbox', { name: '密码' }).fill(${PASSWORD_JSON});
  await page.getByRole('button', { name: '登录' }).click();
  await page.waitForLoadState('domcontentloaded');
  try {
    await page.waitForLoadState('networkidle', { timeout: 8000 });
  } catch (error) {}
}" >/dev/null

ORIGINAL_RAW_JSON="$(run_code_result "async page => {
  const response = await page.evaluate(async url => {
    const rawUrl = url + '&action=raw';
    const rawResponse = await fetch(rawUrl, { credentials: 'same-origin' });
    return {
      ok: rawResponse.ok,
      text: await rawResponse.text()
    };
  }, ${SHOT_PAGE_URL_JSON});
  if (!response.ok) {
    throw new Error('failed to load raw page');
  }
  return response.text;
}")"

python - <<'PY' "${ORIGINAL_RAW_JSON}" > "${ARTIFACT_DIR}/shot-original.wiki"
import json
import sys
print(json.loads(sys.argv[1]))
PY

HAS_RULE="$(python - <<'PY' "${ORIGINAL_RAW_JSON}" "${NORMALIZED_RULE}"
import json
import sys
text = json.loads(sys.argv[1])
line = sys.argv[2]
print('true' if line in text else 'false')
PY
)"

run_prompt() {
  local label="$1"
  local prompt="$2"
  local expected="$3"
  local unexpected="$4"
  local click_action="${5:-none}"
  local prompt_json expected_json unexpected_json page_url_json response_json response_json_encoded
  prompt_json="$(json_string "${prompt}")"
  expected_json="$(json_string "${expected}")"
  unexpected_json="$(json_string "${unexpected}")"
  page_url_json="${SHOT_PAGE_URL_JSON}"

  playwright-cli -s="${SESSION_NAME}" run-code "async page => {
    await page.goto(${page_url_json}, { waitUntil: 'domcontentloaded' });
    try {
      await page.waitForLoadState('networkidle', { timeout: 8000 });
    } catch (error) {}
  }" >/dev/null

  response_json="$(run_code_result "async page => {
    const config = await page.evaluate(() => (window.mw && mw.config && mw.config.get('wgLabAssistant')) || null);
    if (!config || !config.apiBase) {
      throw new Error('wgLabAssistant.apiBase is missing');
    }
    const response = await page.evaluate(async ({ apiBase, question, targetPage, userName }) => {
      const res = await fetch(apiBase + '/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          question,
          mode: 'qa',
          detail_level: 'intro',
          context_pages: [targetPage],
          user_name: userName
        })
      });
      return {
        ok: res.ok,
        body: await res.json()
      };
    }, {
      apiBase: config.apiBase,
      question: ${prompt_json},
      targetPage: ${SHOT_PAGE_TITLE_JSON},
      userName: config.userName || null
    });
    if (!response.ok) {
      throw new Error(response.body.detail || 'chat request failed');
    }
    return response.body;
  }")"

  response_json_encoded="$(json_string "${response_json}")"

  python - <<'PY' "${response_json}" "${expected}" "${unexpected}" > "${ARTIFACT_DIR}/${label}-operation.json"
import json
import sys
body = json.loads(sys.argv[1])
expected = sys.argv[2]
unexpected = sys.argv[3]
preview = body.get("operation_preview") or {}
content = preview.get("content") or ""
print(json.dumps(body, ensure_ascii=False, indent=2))
if not preview:
    raise SystemExit("operation_preview missing")
if expected not in content:
    raise SystemExit(f"expected line missing: {expected}")
if unexpected and unexpected in content:
    raise SystemExit(f"unexpected text present: {unexpected}")
PY

  if [[ "${click_action}" == "edit" ]]; then
    playwright-cli -s="${SESSION_NAME}" run-code "async page => {
      const body = JSON.parse(${response_json_encoded});
      const targetUrl = await page.evaluate(chatBody => {
        const preview = chatBody.operation_preview;
        const editorUtils = window.LabAssistantEditorUtils || (window.mw && mw.labassistantEditorUtils);
        if (!preview || !editorUtils || !editorUtils.buildDraftHandoffStorageKey) {
          throw new Error('operation preview handoff unavailable');
        }
        const key = editorUtils.buildDraftHandoffStorageKey(preview.target_page, window.location.host);
        sessionStorage.setItem(key, JSON.stringify({
          title: preview.target_page,
          source_mode: 'default',
          content_type: 'write_preview',
          content: preview.content,
          target_section: preview.target_section || '',
          structured_payload: preview.structured_payload || null,
          created_at: new Date().toISOString()
        }));
        const nextUrl = new URL(mw.util.getUrl(preview.target_page), window.location.origin);
        nextUrl.searchParams.set('action', 'edit');
        return nextUrl.toString();
      }, body);
      await page.goto(targetUrl.toString(), { waitUntil: 'domcontentloaded' });
      await page.locator('#wpTextbox1').waitFor({ state: 'visible', timeout: 15000 });
    }" >/dev/null
    playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/${label}-edit.yml" >/dev/null
    local editor_json
    editor_json="$(run_code_result "async page => page.locator('#wpTextbox1').inputValue()")"
    python - <<'PY' "${editor_json}" "${expected}" "${unexpected}" > "${ARTIFACT_DIR}/${label}-editor.txt"
import json
import sys
text = json.loads(sys.argv[1])
expected = sys.argv[2]
unexpected = sys.argv[3]
print(text)
if expected not in text:
    raise SystemExit(f"editor missing expected line: {expected}")
if unexpected and unexpected in text:
    raise SystemExit(f"editor contained unexpected text: {unexpected}")
PY
  elif [[ "${click_action}" == "confirm" ]]; then
    local commit_json
    commit_json="$(run_code_result "async page => {
      const body = JSON.parse(${response_json_encoded});
      const config = await page.evaluate(() => (window.mw && mw.config && mw.config.get('wgLabAssistant')) || null);
      const previewId = body.operation_preview && body.operation_preview.preview_id;
      if (!previewId) {
        throw new Error('preview_id missing for commit');
      }
      const response = await page.evaluate(async ({ apiBase, previewId }) => {
        const res = await fetch(apiBase + '/write/commit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ preview_id: previewId })
        });
        return {
          ok: res.ok,
          body: await res.json()
        };
      }, {
        apiBase: config.apiBase,
        previewId
      });
      if (!response.ok) {
        throw new Error(response.body.detail || 'write commit failed');
      }
      return response.body;
    }")"
    printf '%s\n' "${commit_json}" > "${ARTIFACT_DIR}/${label}-commit.json"
  fi
}

run_prompt \
  "shot-edit-phrasing" \
  "编辑一下使用规则区域：加入一条规则：必须备注原实验记录excel的实际电脑ID及文件夹位置" \
  "${NORMALIZED_RULE}" \
  "${BAD_RULE_PREFIX}" \
  "edit"

run_prompt \
  "shot-formal-append-preview" \
  "给使用规则加一条：每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径。" \
  "${FORMAL_RULE}" \
  "加入一条规则："

run_prompt \
  "shot-replace-preview" \
  "把使用规则里“打靶后立刻创建或补全页面”这条规则改成更正式的写法：打靶后应立刻创建或补全页面。" \
  "${REPLACE_NEW_RULE}" \
  "${REPLACE_OLD_RULE}" \
  "edit"

if [[ "${HAS_RULE}" == "false" ]]; then
  run_prompt \
    "shot-formal-append-commit" \
    "给使用规则加一条：每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径。" \
    "${FORMAL_RULE}" \
    "加入一条规则：" \
    "confirm"

  run_prompt \
    "shot-delete-preview" \
    "把刚加的这条使用规则删掉：每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径。" \
    "打靶后立刻创建或补全页面" \
    "${FORMAL_RULE}" \
    "confirm"

  RESTORED_RAW_JSON="$(run_code_result "async page => {
    const response = await page.evaluate(async url => {
      const rawResponse = await fetch(url + '&action=raw', { credentials: 'same-origin' });
      return await rawResponse.text();
    }, ${SHOT_PAGE_URL_JSON});
    return response;
  }")"

  python - <<'PY' "${RESTORED_RAW_JSON}" "${FORMAL_RULE}" > "${ARTIFACT_DIR}/shot-restored-check.txt"
import json
import sys
text = json.loads(sys.argv[1])
line = sys.argv[2]
print(text)
if line in text:
    raise SystemExit("formal rule still present after delete restore")
PY
fi

cat > "${REPORT_FILE}" <<REPORT
# Assistant Operation Check

- Base URL: ${BASE_URL}
- Session: ${SESSION_NAME}
- Verified prompts:
  - 编辑一下使用规则区域：加入一条规则：必须备注原实验记录excel的实际电脑ID及文件夹位置
  - 给使用规则加一条：每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径。
  - 把使用规则里“打靶后立刻创建或补全页面”这条规则改成更正式的写法：打靶后应立刻创建或补全页面。
- Verified UI action:
  - 代我编辑这个模块
- Verified normalization:
  - 操作话术不会写入预览或编辑框
  - replace 只替换目标规则，不保留旧措辞
REPORT

echo "Assistant operation browser check passed. Report: ${REPORT_FILE}"
