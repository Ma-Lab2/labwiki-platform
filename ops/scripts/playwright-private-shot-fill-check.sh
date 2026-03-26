#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

BASE_URL="${BASE_URL:-http://localhost:8443}"
PRIVATE_USER="${PRIVATE_ADMIN_USER:-admin}"
PRIVATE_PASSWORD_FILE="${PRIVATE_PASSWORD_FILE:-${ROOT_DIR}/secrets/private_admin_password.txt}"
SESSION_NAME="${SESSION_NAME:-labwiki-shot-fill-check}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ARTIFACT_DIR="${ARTIFACT_DIR:-${ROOT_DIR}/backups/validation/playwright-private-shot-fill-${TIMESTAMP}}"
SHOT_PAGE_TITLE="${SHOT_PAGE_TITLE:-Special:编辑表格/Shot记录/Shot:2026-03-23-Run96-Shot001}"
ATTACHMENT_PATH="${ATTACHMENT_PATH:-${ROOT_DIR}/backups/validation/tmp/labassistant-shot-check.png}"
PROMPT_TEXT="${PROMPT_TEXT:-请根据当前 Shot 页面和这张结果图，生成一版 Shot 结果回填建议。}"

usage() {
  cat <<EOF
Usage: bash ops/scripts/playwright-private-shot-fill-check.sh [options]

Options:
  --base-url <url>           Private wiki entry (default: ${BASE_URL})
  --session-name <name>      Playwright session name (default: ${SESSION_NAME})
  --artifact-dir <path>      Directory for snapshots and report
  --shot-page <title>        Shot PageForms title (default: ${SHOT_PAGE_TITLE})
  --attachment <path>        Attachment used for Shot result fill
  --prompt <text>            Prompt sent to the assistant
  --help                     Show this help text
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
    --shot-page)
      SHOT_PAGE_TITLE="${2:?missing value for --shot-page}"
      shift 2
      ;;
    --attachment)
      ATTACHMENT_PATH="${2:?missing value for --attachment}"
      shift 2
      ;;
    --prompt)
      PROMPT_TEXT="${2:?missing value for --prompt}"
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

if [[ ! -f "${ATTACHMENT_PATH}" ]]; then
  echo "Shot fill attachment not found: ${ATTACHMENT_PATH}" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not in PATH." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "environment unavailable: docker engine is not reachable." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose plugin is not available." >&2
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
ATTACHMENT_PATH_JSON="$(python - <<'PY' "${ATTACHMENT_PATH}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
PROMPT_TEXT_JSON="$(python - <<'PY' "${PROMPT_TEXT}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
SHOT_PAGE_URL_PATH="$(python - <<'PY' "${SHOT_PAGE_TITLE}"
from urllib.parse import quote
import sys
print("/index.php?title=" + quote(sys.argv[1], safe=""))
PY
)"

mkdir -p "${ARTIFACT_DIR}"
SUMMARY_FILE="${ARTIFACT_DIR}/summary.json"
REPORT_FILE="${ARTIFACT_DIR}/report.md"

cleanup() {
  playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
}
trap cleanup EXIT

pl_eval_json() {
  local expr="$1"
  local raw
  local output
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

pl_run_json() {
  local code="$1"
  local raw
  local output
  output="$(playwright-cli -s="${SESSION_NAME}" run-code "${code}")"
  raw="$(printf '%s\n' "${output}" | sed -n '/^### Result/{n;p;}' | head -n 1)"
  if [[ -z "${raw}" ]]; then
    printf 'Failed to parse playwright run-code output.\n' >&2
    printf '%s\n' "${output}" >&2
    exit 1
  fi
  printf '%s\n' "${raw}"
}

wait_for_page_ready() {
  playwright-cli -s="${SESSION_NAME}" run-code "async page => {
    await page.waitForLoadState('domcontentloaded');
    try {
      await page.waitForLoadState('networkidle', { timeout: 5000 });
    } catch (error) {}
  }" >/dev/null
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

assert_equals() {
  local value="$1"
  local expected="$2"
  local message="$3"
  if [[ "${value}" != "${expected}" ]]; then
    echo "${message}: got '${value}', expected '${expected}'" >&2
    exit 1
  fi
}

wait_for_playwright_true() {
  local expression="$1"
  local timeout_seconds="$2"
  local description="$3"
  local attempt=0
  local max_attempts=$(( timeout_seconds * 2 ))
  local value

  while (( attempt < max_attempts )); do
    value="$(python - <<'PY' "$(pl_run_json "async page => { return await page.evaluate(() => (${expression})); }")"
import json
import sys
print(json.loads(sys.argv[1]))
PY
)"
    if [[ "${value}" == "True" ]]; then
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 0.5
  done

  echo "${description}" >&2
  return 1
}

wait_for_private_entry() {
  local attempts=0
  local login_url="${BASE_URL%/}/index.php?title=%E7%89%B9%E6%AE%8A:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95"
  until curl --noproxy '*' -fsS -o /dev/null "${login_url}"; do
    attempts=$((attempts + 1))
    if [[ ${attempts} -ge 15 ]]; then
      echo "Private wiki did not become ready at ${BASE_URL}" >&2
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

LOGIN_URL="${BASE_URL%/}/index.php?title=%E7%89%B9%E6%AE%8A:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95"
playwright-cli -s="${SESSION_NAME}" goto "${LOGIN_URL}" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.locator('#wpName1').fill(${PRIVATE_USER_JSON});
  await page.locator('#wpPassword1').fill(${PRIVATE_PASSWORD_JSON});
  await page.locator('#wpLoginAttempt').click();
  await page.waitForLoadState('networkidle');
}" >/dev/null

SHOT_URL="${BASE_URL%/}${SHOT_PAGE_URL_PATH}"
playwright-cli -s="${SESSION_NAME}" goto "${SHOT_URL}" >/dev/null
wait_for_page_ready
SHOT_FORM_PRESENT="$(pl_eval_json 'Boolean(document.querySelector("#pfForm"))')"
assert_equals "${SHOT_FORM_PRESENT}" "True" "Shot PageForms form did not render"
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/01-shot-form.yml" >/dev/null

LAUNCHER_PRESENT="$(pl_eval_json 'Boolean(document.querySelector(".labassistant-launcher-button"))')"
assert_equals "${LAUNCHER_PRESENT}" "True" "Knowledge assistant launcher did not render on the Shot form page"

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.locator('.labassistant-launcher-button').first().click();
  await page.waitForSelector('#labassistant-drawer-root:not([hidden])');
  await page.locator('.labassistant-composer input[type=file]').nth(0).setInputFiles(${ATTACHMENT_PATH_JSON});
  await page.waitForTimeout(500);
  const presetButton = page.locator('.labassistant-followup-button', {
    hasText: '请根据我上传的结果截图和说明'
  }).first();
  if (await presetButton.count()) {
    await presetButton.click();
  } else {
    await page.locator('.labassistant-composer textarea').fill(${PROMPT_TEXT_JSON});
    await page.locator('.labassistant-composer textarea').dispatchEvent('input');
  }
  await page.waitForTimeout(500);
}" >/dev/null

wait_for_playwright_true \
  "Boolean(document.querySelector('.labassistant-attachment-chip')) && !document.body.textContent.includes('上传中')" \
  30 \
  "Attachment chip did not become ready."

wait_for_playwright_true \
  "Boolean(document.querySelector('.labassistant-composer textarea')) && document.querySelector('.labassistant-composer textarea').value.trim().length > 0 && Boolean(document.querySelector('.labassistant-send-button')) && !document.querySelector('.labassistant-send-button').disabled" \
  15 \
  "Composer was not ready to send the Shot result-fill request."

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.locator('.labassistant-send-button').click({ force: true });
}" >/dev/null

wait_for_playwright_true \
  "Array.from(document.querySelectorAll('.labassistant-inline-card h4')).map(node => node.textContent.trim()).includes('Shot 结果回填建议')" \
  180 \
  "Shot result fill card did not render within timeout."

wait_for_playwright_true \
  "Array.from(document.querySelectorAll('.labassistant-inline-card h4')).map(node => node.textContent.trim()).includes('表单字段建议')" \
  30 \
  "PageForms fill card did not render within timeout."

wait_for_playwright_true \
  "Array.from(document.querySelectorAll('.labassistant-submit-checklist .labassistant-form-missing-head strong')).map(node => node.textContent.trim()).includes('待确认字段') && Array.from(document.querySelectorAll('.labassistant-submit-checklist .labassistant-form-missing-head strong')).map(node => node.textContent.trim()).includes('待补充字段')" \
  30 \
  "Submission guidance did not split pending vs missing sections."

playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/02-shot-result-fill.yml" >/dev/null

BEFORE_SUMMARY_JSON="$(pl_run_json "async page => {
  return await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll('.labassistant-inline-card h4')).map(node => node.textContent.trim());
    const checklistLabels = Array.from(document.querySelectorAll('.labassistant-submit-checklist .labassistant-form-missing-head strong')).map(node => node.textContent.trim());
    const sections = Array.from(document.querySelectorAll('.labassistant-form-fill-card .labassistant-form-missing'));
    const pendingSection = sections.find(section => {
      const head = section.querySelector('.labassistant-form-missing-head strong');
      return head && head.textContent.trim() === '待确认字段';
    });
    const missingSection = sections.find(section => {
      const head = section.querySelector('.labassistant-form-missing-head strong');
      return head && head.textContent.trim() === '缺失字段';
    });
    const pendingItems = pendingSection ? Array.from(pendingSection.querySelectorAll('.labassistant-form-fill-item')) : [];
    const preferredPending = pendingItems.find(node => {
      const label = node.querySelector('strong');
      return label && label.textContent.trim() === '原始数据主目录';
    });
    const targetPending = preferredPending || pendingItems[0] || null;
    const targetLabel = targetPending && targetPending.querySelector('strong');
    return {
      resultFillCardPresent: cards.includes('Shot 结果回填建议'),
      formFillCardPresent: cards.includes('表单字段建议'),
      submissionGuidanceSplitPresent: checklistLabels.includes('待确认字段') && checklistLabels.includes('待补充字段'),
      pendingFieldsCountBeforeConfirm: pendingItems.length,
      missingFieldsCountBeforeConfirm: missingSection ? missingSection.querySelectorAll('.labassistant-form-fill-item, .labassistant-form-missing-chip').length : 0,
      confirmedFieldLabel: targetLabel ? targetLabel.textContent.trim() : ''
    };
  });
}")"

RESULT_FILL_CARD_PRESENT="$(python - <<'PY' "${BEFORE_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["resultFillCardPresent"])
PY
)"
FORM_FILL_CARD_PRESENT="$(python - <<'PY' "${BEFORE_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["formFillCardPresent"])
PY
)"
SUBMISSION_GUIDANCE_SPLIT_PRESENT="$(python - <<'PY' "${BEFORE_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["submissionGuidanceSplitPresent"])
PY
)"
PENDING_FIELDS_COUNT_BEFORE_CONFIRM="$(python - <<'PY' "${BEFORE_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["pendingFieldsCountBeforeConfirm"])
PY
)"
MISSING_FIELDS_COUNT_BEFORE_CONFIRM="$(python - <<'PY' "${BEFORE_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["missingFieldsCountBeforeConfirm"])
PY
)"
CONFIRMED_FIELD_LABEL="$(python - <<'PY' "${BEFORE_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["confirmedFieldLabel"])
PY
)"
assert_equals "${RESULT_FILL_CARD_PRESENT}" "True" "Shot result fill card did not render"
assert_equals "${FORM_FILL_CARD_PRESENT}" "True" "PageForms fill card did not render"
assert_equals "${SUBMISSION_GUIDANCE_SPLIT_PRESENT}" "True" "Submission guidance did not split pending vs missing sections"

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  const fallbackButton = page.locator('.labassistant-form-fill-card .labassistant-form-missing button', {
    hasText: '确认并填入此字段'
  }).first();
  if (!await fallbackButton.count()) {
    throw new Error('Pending field confirmation button is missing.');
  }
  await fallbackButton.click({ force: true });
}" >/dev/null

wait_for_playwright_true \
  "Boolean(document.querySelector('[name=\"Shot记录[原始数据主目录]\"]')) && document.querySelector('[name=\"Shot记录[原始数据主目录]\"]').value === '/data/shot/2026-03-23/Run96'" \
  30 \
  "Confirmed pending field was not written into the PageForms field."

wait_for_playwright_true \
  "Boolean(document.querySelector('.labassistant-submit-checklist')) && document.querySelector('.labassistant-submit-checklist').textContent.includes('已填入 1 个表单字段：原始数据主目录；表单尚未提交。')" \
  30 \
  "Submission guidance notice did not update after confirming the pending field."

playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/03-shot-after-confirm.yml" >/dev/null

AFTER_CONFIRM_SUMMARY_JSON="$(pl_run_json "async page => {
  return await page.evaluate(() => {
    const sections = Array.from(document.querySelectorAll('.labassistant-form-fill-card .labassistant-form-missing'));
    const pendingSection = sections.find(section => {
      const head = section.querySelector('.labassistant-form-missing-head strong');
      return head && head.textContent.trim() === '待确认字段';
    });
    const field = document.querySelector('[name=\"Shot记录[原始数据主目录]\"]');
    const hasForm = Boolean(
      document.querySelector('#pfForm, form[action*=\"Special:FormEdit\"], form[action*=\"action=formedit\"]')
    );
    return {
      confirmedFieldValue: field ? field.value : '',
      pendingFieldsCountAfterConfirm: pendingSection ? pendingSection.querySelectorAll('.labassistant-form-fill-item').length : 0,
      pageAutoSubmitted: !hasForm
    };
  });
}")"

CONFIRMED_FIELD_VALUE="$(python - <<'PY' "${AFTER_CONFIRM_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["confirmedFieldValue"])
PY
)"
PENDING_FIELDS_COUNT_AFTER_CONFIRM="$(python - <<'PY' "${AFTER_CONFIRM_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["pendingFieldsCountAfterConfirm"])
PY
)"
PAGE_AUTO_SUBMITTED="$(python - <<'PY' "${AFTER_CONFIRM_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["pageAutoSubmitted"])
PY
)"

RELOAD_LOG_FILE="$(mktemp)"
(
  playwright-cli -s="${SESSION_NAME}" reload >"${RELOAD_LOG_FILE}" 2>&1 || true
) &
RELOAD_PID=$!
sleep 1
playwright-cli -s="${SESSION_NAME}" dialog-accept >/dev/null 2>&1 || true
wait "${RELOAD_PID}" || true
rm -f "${RELOAD_LOG_FILE}"
wait_for_page_ready
wait_for_playwright_true \
  "Boolean(document.querySelector('.labassistant-submit-checklist')) && Array.from(document.querySelectorAll('.labassistant-submit-checklist .labassistant-form-missing-head strong')).map(node => node.textContent.trim()).includes('待确认字段') && Array.from(document.querySelectorAll('.labassistant-submit-checklist .labassistant-form-missing-head strong')).map(node => node.textContent.trim()).includes('待补充字段') && document.querySelector('.labassistant-submit-checklist').textContent.includes('已填入 1 个表单字段：原始数据主目录；表单尚未提交。')" \
  30 \
  "Submission guidance did not restore after refresh."
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/04-shot-after-refresh.yml" >/dev/null

AFTER_REFRESH_SUMMARY_JSON="$(pl_run_json "async page => {
  return await page.evaluate(() => {
    const checklist = document.querySelector('.labassistant-submit-checklist');
    const heads = checklist ? Array.from(checklist.querySelectorAll('.labassistant-form-missing-head strong')).map(node => node.textContent.trim()) : [];
    return {
      restoredSubmissionGuidance: Boolean(
        checklist &&
        heads.includes('待确认字段') &&
        heads.includes('待补充字段') &&
        checklist.textContent.includes('已填入 1 个表单字段：原始数据主目录；表单尚未提交。')
      )
    };
  });
}")"

RESTORED_SUBMISSION_GUIDANCE="$(python - <<'PY' "${AFTER_REFRESH_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["restoredSubmissionGuidance"])
PY
)"

capture_log_artifact console "05-console.log"
capture_log_artifact network "06-network.log"

python - <<'PY' \
  "${SUMMARY_FILE}" \
  "${BASE_URL}" \
  "${SHOT_PAGE_TITLE}" \
  "${RESULT_FILL_CARD_PRESENT}" \
  "${FORM_FILL_CARD_PRESENT}" \
  "${PENDING_FIELDS_COUNT_BEFORE_CONFIRM}" \
  "${MISSING_FIELDS_COUNT_BEFORE_CONFIRM}" \
  "${SUBMISSION_GUIDANCE_SPLIT_PRESENT}" \
  "${CONFIRMED_FIELD_LABEL}" \
  "${CONFIRMED_FIELD_VALUE}" \
  "${PENDING_FIELDS_COUNT_AFTER_CONFIRM}" \
  "${PAGE_AUTO_SUBMITTED}" \
  "${RESTORED_SUBMISSION_GUIDANCE}" \
  "01-shot-form.yml" \
  "02-shot-result-fill.yml" \
  "03-shot-after-confirm.yml" \
  "04-shot-after-refresh.yml" \
  "05-console.log" \
  "06-network.log"
from __future__ import annotations

import json
import pathlib
import sys

summary_path = pathlib.Path(sys.argv[1])
artifacts = list(sys.argv[14:])
summary = {
    "base_url": sys.argv[2],
    "shot_page": sys.argv[3],
    "result_fill_card_present": sys.argv[4] == "True",
    "form_fill_card_present": sys.argv[5] == "True",
    "pending_fields_count_before_confirm": int(sys.argv[6]),
    "missing_fields_count_before_confirm": int(sys.argv[7]),
    "submission_guidance_split_present": sys.argv[8] == "True",
    "confirmed_field_label": sys.argv[9],
    "confirmed_field_value": sys.argv[10],
    "pending_fields_count_after_confirm": int(sys.argv[11]),
    "page_auto_submitted": sys.argv[12] == "True",
    "restored_submission_guidance": sys.argv[13] == "True",
    "artifacts": artifacts,
}
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
PY

python ops/scripts/render_shot_student_report.py \
  --summary-file "${SUMMARY_FILE}" \
  --output "${REPORT_FILE}"

printf 'Artifacts written to %s\n' "${ARTIFACT_DIR}"
