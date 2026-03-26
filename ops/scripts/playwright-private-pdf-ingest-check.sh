#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

BASE_URL="${BASE_URL:-http://localhost:8443}"
PRIVATE_USER="${PRIVATE_ADMIN_USER:-admin}"
PRIVATE_PASSWORD_FILE="${PRIVATE_PASSWORD_FILE:-${ROOT_DIR}/secrets/private_admin_password.txt}"
SESSION_NAME="${SESSION_NAME:-labwiki-pdf-ingest-check}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ARTIFACT_DIR="${ARTIFACT_DIR:-${ROOT_DIR}/backups/validation/playwright-private-pdf-ingest-${TIMESTAMP}}"
TARGET_PAGE_TITLE="${TARGET_PAGE_TITLE:-首页}"
SAMPLE_PDF_PATH="${SAMPLE_PDF_PATH:-${ROOT_DIR}/怀柔真空管道电机控制.pdf}"
ASSET_VERSION_EXPECTED="${ASSET_VERSION_EXPECTED:-$(python - <<'PY'
from pathlib import Path
import re

path = Path("images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.asset-version.js")
match = re.search(r"ASSET_VERSION = '([^']+)'", path.read_text(encoding="utf-8"))
if not match:
    raise SystemExit("Unable to resolve LabAssistant asset version from ext.labassistant.asset-version.js")
print(match.group(1))
PY
)}"
MODEL_PREF_VERSION_EXPECTED="${MODEL_PREF_VERSION_EXPECTED:-$(python - <<'PY'
from pathlib import Path
import re

path = Path("images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js")
match = re.search(r"MODEL_PREF_VERSION = '([^']+)'", path.read_text(encoding="utf-8"))
if not match:
    raise SystemExit("Unable to resolve LabAssistant model preference version from ext.labassistant.ui.js")
print(match.group(1))
PY
)}"
FORCED_MODEL_ID="${FORCED_MODEL_ID:-gpt-5.4-mini}"
FORCED_MODEL_FAMILY="${FORCED_MODEL_FAMILY:-gpt}"

usage() {
  cat <<EOF
Usage: bash ops/scripts/playwright-private-pdf-ingest-check.sh [options]

Options:
  --base-url <url>           Private wiki entry (default: ${BASE_URL})
  --session-name <name>      Playwright session name (default: ${SESSION_NAME})
  --artifact-dir <path>      Directory for snapshots and report
  --target-page <title>      Page used to open the assistant (default: ${TARGET_PAGE_TITLE})
  --sample-pdf <path>        Local PDF fixture (default: ${SAMPLE_PDF_PATH})
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
    --target-page)
      TARGET_PAGE_TITLE="${2:?missing value for --target-page}"
      shift 2
      ;;
    --sample-pdf)
      SAMPLE_PDF_PATH="${2:?missing value for --sample-pdf}"
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

if [[ ! -f "${SAMPLE_PDF_PATH}" ]]; then
  echo "Sample PDF not found: ${SAMPLE_PDF_PATH}" >&2
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
SAMPLE_PDF_PATH_JSON="$(python - <<'PY' "${SAMPLE_PDF_PATH}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
TARGET_PAGE_URL_PATH="$(python - <<'PY' "${TARGET_PAGE_TITLE}"
from urllib.parse import quote
import sys
print("/index.php?title=" + quote(sys.argv[1], safe=""))
PY
)"

mkdir -p "${ARTIFACT_DIR}"
SUMMARY_FILE="${ARTIFACT_DIR}/summary.json"
REPORT_FILE="${ARTIFACT_DIR}/report.md"
RAW_DRAFT_FILE="${ARTIFACT_DIR}/07-draft-raw.txt"
RAW_FORMAL_FILE="${ARTIFACT_DIR}/08-formal-raw.txt"
RAW_OVERVIEW_FILE="${ARTIFACT_DIR}/09-overview-raw.txt"

cleanup() {
  playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
}
trap cleanup EXIT

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

wait_for_authenticated_page_contains() {
  local page_title="$1"
  local needle="$2"
  local timeout_seconds="$3"
  local description="$4"
  local attempt=0
  local max_attempts=$(( timeout_seconds * 2 ))
  local page_url
  local page_url_json
  local needle_json
  local result_json
  local contains

  page_url="$(python - <<'PY' "${page_title}"
from urllib.parse import quote
import sys
print("/index.php?title=" + quote(sys.argv[1], safe="") + "&action=raw")
PY
)"
  page_url_json="$(python - <<'PY' "${BASE_URL%/}${page_url}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
  needle_json="$(python - <<'PY' "${needle}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"

  while (( attempt < max_attempts )); do
    result_json="$(pl_run_json "async page => {
      return await page.evaluate(async (payload) => {
        try {
          const response = await fetch(payload.url, { credentials: 'include' });
          const text = await response.text();
          return {
            status: response.status,
            contains: text.includes(payload.needle),
            text: text
          };
        } catch (error) {
          return {
            status: 0,
            contains: false,
            text: '',
            error: String(error)
          };
        }
      }, {
        url: ${page_url_json},
        needle: ${needle_json}
      });
    }")"
    contains="$(python - <<'PY' "${result_json}"
import json
import sys
print(json.loads(sys.argv[1])["contains"])
PY
)"
    if [[ "${contains}" == "True" ]]; then
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 0.5
  done

  echo "${description}" >&2
  return 1
}

fetch_authenticated_page_text() {
  local page_title="$1"
  local page_url
  local page_url_json

  page_url="$(python - <<'PY' "${page_title}"
from urllib.parse import quote
import sys
print("/index.php?title=" + quote(sys.argv[1], safe="") + "&action=raw")
PY
)"
  page_url_json="$(python - <<'PY' "${BASE_URL%/}${page_url}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"

  pl_run_json "async page => {
    return await page.evaluate(async (url) => {
      const response = await fetch(url, { credentials: 'include' });
      return await response.text();
    }, ${page_url_json});
  }"
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

python ops/scripts/check_mediawiki_resource_sync.py --service mw_private --json > "${ARTIFACT_DIR}/00-resource-sync.json"
RESOURCE_SYNC_STATUS="$(python - <<'PY' "${ARTIFACT_DIR}/00-resource-sync.json"
import json
import sys
from pathlib import Path

print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["status"])
PY
)"
if [[ "${RESOURCE_SYNC_STATUS}" != "ok" ]]; then
  echo "environment unavailable: mw_private runtime resources are out of sync." >&2
  exit 1
fi

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

TARGET_URL="${BASE_URL%/}${TARGET_PAGE_URL_PATH}"
playwright-cli -s="${SESSION_NAME}" goto "${TARGET_URL}" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.evaluate((payload) => {
    window.localStorage.setItem('labassistant-selected-model', payload.modelId);
    window.localStorage.setItem('labassistant-selected-model-family', payload.family);
    window.localStorage.setItem('labassistant-model-pref-version', payload.version);
  }, {
    modelId: ${FORCED_MODEL_ID@Q},
    family: ${FORCED_MODEL_FAMILY@Q},
    version: ${MODEL_PREF_VERSION_EXPECTED@Q}
  });
}" >/dev/null
playwright-cli -s="${SESSION_NAME}" goto "${TARGET_URL}" >/dev/null
wait_for_page_ready

ASSET_VERSION_READY="$(pl_eval_json 'window.LabAssistantAssetVersion || (window.mw && mw.labassistantAssetVersion) || null')"
assert_equals "${ASSET_VERSION_READY}" "${ASSET_VERSION_EXPECTED}" "Assistant asset-version bootstrap did not reach the runtime"

LAUNCHER_PRESENT="$(pl_eval_json 'Boolean(document.querySelector(".labassistant-launcher-button"))')"
assert_equals "${LAUNCHER_PRESENT}" "True" "Knowledge assistant launcher did not render on the target page"

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.locator('.labassistant-launcher-button').first().click();
  await page.waitForSelector('#labassistant-drawer-root:not([hidden])');
  await page.locator('#labassistant-drawer-root input[type=file][accept*=\".pdf\"]').first().setInputFiles(${SAMPLE_PDF_PATH_JSON});
}" >/dev/null

wait_for_playwright_true \
  "Boolean(Array.from(document.querySelectorAll('#labassistant-drawer-root .labassistant-attachment-chip .labassistant-attachment-open')).find(node => (node.textContent || '').includes('分析写入')))" \
  30 \
  "PDF attachment chip did not expose the ingest action."

ATTACHMENT_READY="$(python - <<'PY' "$(pl_run_json "async page => {
  return await page.evaluate(() => Boolean(
    Array.from(document.querySelectorAll('#labassistant-drawer-root .labassistant-attachment-chip .labassistant-attachment-open'))
      .find(node => (node.textContent || '').includes('分析写入'))
  ));
}")"
import json
import sys
print(json.loads(sys.argv[1]))
PY
)"
assert_equals "${ATTACHMENT_READY}" "True" "PDF attachment was not ready for ingest analysis"
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/01-page.yml" >/dev/null

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  const button = page.locator('#labassistant-drawer-root .labassistant-attachment-chip .labassistant-attachment-open', {
    hasText: '分析写入'
  }).first();
  await button.click({ force: true });
}" >/dev/null

wait_for_playwright_true \
  "Boolean(Array.from(document.querySelectorAll('#labassistant-drawer-root .labassistant-inline-card')).find(card => { const text = card.textContent || ''; return text.includes('建议归档区域') && text.includes('生成草稿预览'); }))" \
  180 \
  "PDF ingest review card did not render within timeout."

playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/02-review.yml" >/dev/null

REVIEW_SUMMARY_JSON="$(pl_run_json "async page => {
  return await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll('#labassistant-drawer-root .labassistant-inline-card'));
    const reviewCard = cards.find(card => {
      const text = card.textContent || '';
      return text.includes('建议归档区域') && text.includes('生成草稿预览');
    });
    const cardText = reviewCard ? reviewCard.textContent || '' : '';
    const targetNodes = reviewCard ? Array.from(reviewCard.querySelectorAll('.labassistant-form-missing .labassistant-form-fill-item strong')).map(node => node.textContent.trim()) : [];
    const modelSelect = document.querySelector('#labassistant-drawer-root .labassistant-compact-model-select');
    const activeModelId = modelSelect ? String(modelSelect.value || '').trim() : '';
    return {
      reviewCardPresent: Boolean(reviewCard),
      reviewMentionsControlManual: cardText.includes('SMC Basic Studio') && cardText.includes('IP') && cardText.includes('轴'),
      primaryTargetControl: targetNodes.length ? targetNodes[0].indexOf('Control:') === 0 : false,
      activeModelId: activeModelId,
      modelPromotedFromMini: Boolean(activeModelId) && activeModelId !== ${FORCED_MODEL_ID@Q}
    };
  });
}")"

REVIEW_CARD_PRESENT="$(python - <<'PY' "${REVIEW_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["reviewCardPresent"])
PY
)"
REVIEW_MENTIONS_CONTROL_MANUAL="$(python - <<'PY' "${REVIEW_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["reviewMentionsControlManual"])
PY
)"
PRIMARY_TARGET_CONTROL="$(python - <<'PY' "${REVIEW_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["primaryTargetControl"])
PY
)"
ACTIVE_MODEL_AFTER_REVIEW="$(python - <<'PY' "${REVIEW_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["activeModelId"])
PY
)"
MODEL_PROMOTED_FROM_MINI="$(python - <<'PY' "${REVIEW_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["modelPromotedFromMini"])
PY
)"
assert_equals "${REVIEW_CARD_PRESENT}" "True" "PDF ingest review card was not found"
assert_equals "${PRIMARY_TARGET_CONTROL}" "True" "PDF ingest review did not rank Control: as the first target"
assert_equals "${REVIEW_MENTIONS_CONTROL_MANUAL}" "True" "PDF ingest review did not mention the expected control-manual details"
assert_equals "${MODEL_PROMOTED_FROM_MINI}" "True" "PDF ingest workflow did not promote the forced mini model to a stronger model"

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  const button = page.locator('#labassistant-drawer-root .labassistant-inline-card button', {
    hasText: '生成草稿预览'
  }).first();
  await button.click({ force: true });
}" >/dev/null

wait_for_playwright_true \
  "Boolean(Array.from(document.querySelectorAll('#labassistant-drawer-root .labassistant-callout')).find(node => (node.textContent || '').includes('草稿预览已生成：')))" \
  120 \
  "PDF draft preview callout did not appear."

DRAFT_PREVIEW_SUMMARY_JSON="$(pl_run_json "async page => {
  return await page.evaluate(() => {
    const callout = Array.from(document.querySelectorAll('#labassistant-drawer-root .labassistant-callout'))
      .find(node => (node.textContent || '').includes('草稿预览已生成：'));
    const text = callout ? (callout.textContent || '').trim() : '';
    const pageTitle = text.includes('：') ? text.split('：').slice(1).join('：').trim() : '';
    return {
      draftPreviewPresent: Boolean(callout),
      draftPageTitle: pageTitle
    };
  });
}")"
DRAFT_PREVIEW_PRESENT="$(python - <<'PY' "${DRAFT_PREVIEW_SUMMARY_JSON}"
import json
import sys
print(json.loads(sys.argv[1])["draftPreviewPresent"])
PY
)"
DRAFT_PAGE_TITLE="$(python - <<'PY' "${DRAFT_PREVIEW_SUMMARY_JSON}"
import json
import sys
print(json.loads(sys.argv[1])["draftPageTitle"])
PY
)"
assert_equals "${DRAFT_PREVIEW_PRESENT}" "True" "PDF draft preview did not render"
if [[ -z "${DRAFT_PAGE_TITLE}" ]]; then
  echo "PDF draft preview did not expose a target draft page title." >&2
  exit 1
fi
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/03-preview.yml" >/dev/null

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  const button = page.locator('#labassistant-drawer-root .labassistant-inline-card button', {
    hasText: '确认写入草稿页'
  }).first();
  await button.click({ force: true });
}" >/dev/null
wait_for_playwright_true \
  "Boolean(Array.from(document.querySelectorAll('#labassistant-drawer-root .labassistant-callout')).find(node => (node.textContent || '').includes('已写入草稿页：')))" \
  120 \
  "PDF draft commit did not update the assistant card within timeout."
wait_for_authenticated_page_contains \
  "${DRAFT_PAGE_TITLE}" \
  "建议正式归档区域：Control:" \
  180 \
  "PDF draft commit did not finish within timeout."

playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/04-commit.yml" >/dev/null
DRAFT_COMMIT_SUCCESS="True"
DRAFT_RAW_TEXT_JSON="$(fetch_authenticated_page_text "${DRAFT_PAGE_TITLE}")"
python - <<'PY' "${DRAFT_RAW_TEXT_JSON}" "${RAW_DRAFT_FILE}"
import json
import sys
from pathlib import Path

Path(sys.argv[2]).write_text(json.loads(sys.argv[1]), encoding="utf-8")
PY

DRAFT_PAGE_CONTAINS_CONTROL_TARGET="$(python - <<'PY' "${RAW_DRAFT_FILE}"
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding='utf-8')
print('True' if '建议正式归档区域：Control:' in text else 'False')
PY
)"
DRAFT_PAGE_CONTAINS_PAGE_GALLERY="$(python - <<'PY' "${RAW_DRAFT_FILE}"
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding='utf-8')
print('True' if '== 全部页图 ==' in text else 'False')
PY
)"
DRAFT_PAGE_CONTAINS_UPLOADED_FILES="$(python - <<'PY' "${RAW_DRAFT_FILE}"
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding='utf-8')
print('True' if '[[File:PDF提取-怀柔真空管道电机控制-p01-' in text else 'False')
PY
)"
assert_equals "${DRAFT_PAGE_CONTAINS_CONTROL_TARGET}" "True" "Draft page raw content did not include the suggested Control target"
assert_equals "${DRAFT_PAGE_CONTAINS_PAGE_GALLERY}" "True" "Draft page raw content did not include the page gallery section"
assert_equals "${DRAFT_PAGE_CONTAINS_UPLOADED_FILES}" "True" "Draft page raw content did not include uploaded PDF page images"

wait_for_playwright_true \
  "Boolean(Array.from(document.querySelectorAll('#labassistant-drawer-root .labassistant-inline-card button')).find(node => (node.textContent || '').includes('生成 Control 正式写入预览')))" \
  120 \
  "Control formal preview trigger did not appear after draft commit."

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  const button = page.locator('#labassistant-drawer-root .labassistant-inline-card button', {
    hasText: '生成 Control 正式写入预览'
  }).first();
  await button.click({ force: true });
}" >/dev/null

wait_for_playwright_true \
  "Boolean(Array.from(document.querySelectorAll('#labassistant-drawer-root .labassistant-inline-card')).find(card => { const text = card.textContent || ''; return text.includes('总览挂载页：') && text.includes('确认写入 Control 正式页'); }))" \
  120 \
  "Control formal preview card did not appear within timeout."

playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/05-formal-preview.yml" >/dev/null

FORMAL_PREVIEW_SUMMARY_JSON="$(pl_run_json "async page => {
  return await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll('#labassistant-drawer-root .labassistant-inline-card'));
    const formalCard = cards.find(card => {
      const text = card.textContent || '';
      return text.includes('总览挂载页：') && text.includes('确认写入 Control 正式页');
    });
    const text = formalCard ? formalCard.textContent || '' : '';
    const titleNode = formalCard ? formalCard.querySelector('h4') : null;
    const blockedItems = formalCard ? formalCard.querySelectorAll('.labassistant-form-missing .labassistant-form-fill-item').length : 0;
    const overviewNode = formalCard
      ? Array.from(formalCard.querySelectorAll('*')).find(node => {
          const value = node.textContent || '';
          return value.startsWith('总览挂载页：');
        })
      : null;
    const overviewValue = overviewNode
      ? (overviewNode.textContent || '').replace(/^总览挂载页：/, '').trim()
      : '';
    return {
      formalPreviewPresent: Boolean(formalCard),
      formalPreviewTargetsControl: Boolean(titleNode && (titleNode.textContent || '').trim().indexOf('Control:') === 0),
      formalPreviewBlockedItems: blockedItems,
      formalPageTitle: titleNode ? (titleNode.textContent || '').trim() : '',
      overviewPageTitle: overviewValue
    };
  });
}")"
FORMAL_PREVIEW_PRESENT="$(python - <<'PY' "${FORMAL_PREVIEW_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["formalPreviewPresent"])
PY
)"
FORMAL_PREVIEW_TARGETS_CONTROL="$(python - <<'PY' "${FORMAL_PREVIEW_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["formalPreviewTargetsControl"])
PY
)"
FORMAL_PREVIEW_BLOCKED_ITEMS="$(python - <<'PY' "${FORMAL_PREVIEW_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["formalPreviewBlockedItems"])
PY
)"
FORMAL_PAGE_TITLE="$(python - <<'PY' "${FORMAL_PREVIEW_SUMMARY_JSON}"
import json, sys
print(json.loads(sys.argv[1])["formalPageTitle"])
PY
)"
OVERVIEW_PAGE_TITLE="$(python - <<'PY' "${FORMAL_PREVIEW_SUMMARY_JSON}"
import json, sys
value = json.loads(sys.argv[1])["overviewPageTitle"]
print(value if value else "Control:控制与运行总览")
PY
)"
assert_equals "${FORMAL_PREVIEW_PRESENT}" "True" "Control formal preview card was not found"
assert_equals "${FORMAL_PREVIEW_TARGETS_CONTROL}" "True" "Control formal preview did not target a Control: page"
if [[ -z "${FORMAL_PAGE_TITLE}" ]]; then
  echo "Control formal preview did not expose a target page title." >&2
  exit 1
fi

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  const button = page.locator('#labassistant-drawer-root .labassistant-inline-card button', {
    hasText: '确认写入 Control 正式页'
  }).first();
  await button.click({ force: true });
}" >/dev/null

wait_for_authenticated_page_contains \
  "${FORMAL_PAGE_TITLE}" \
  "LABASSISTANT_CONTROL_START" \
  180 \
  "Control formal commit did not finish within timeout."

playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/06-formal-commit.yml" >/dev/null
FORMAL_COMMIT_SUCCESS="True"

FORMAL_RAW_TEXT_JSON="$(fetch_authenticated_page_text "${FORMAL_PAGE_TITLE}")"
python - <<'PY' "${FORMAL_RAW_TEXT_JSON}" "${RAW_FORMAL_FILE}"
import json
import sys
from pathlib import Path

Path(sys.argv[2]).write_text(json.loads(sys.argv[1]), encoding="utf-8")
PY

OVERVIEW_RAW_TEXT_JSON="$(fetch_authenticated_page_text "${OVERVIEW_PAGE_TITLE}")"
python - <<'PY' "${OVERVIEW_RAW_TEXT_JSON}" "${RAW_OVERVIEW_FILE}"
import json
import sys
from pathlib import Path

Path(sys.argv[2]).write_text(json.loads(sys.argv[1]), encoding="utf-8")
PY

FORMAL_PAGE_CONTAINS_MANAGED_BLOCK="$(python - <<'PY' "${RAW_FORMAL_FILE}"
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding='utf-8')
print('True' if 'LABASSISTANT_CONTROL_START' in text and '== 页面定位 ==' in text else 'False')
PY
)"
OVERVIEW_PAGE_CONTAINS_TOPIC_LINK="$(python - <<'PY' "${RAW_OVERVIEW_FILE}" "${FORMAL_PAGE_TITLE}"
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding='utf-8')
needle = f"[[{sys.argv[2]}]]"
print('True' if needle in text else 'False')
PY
)"
assert_equals "${FORMAL_PAGE_CONTAINS_MANAGED_BLOCK}" "True" "Formal Control page raw content did not include the managed block"
assert_equals "${OVERVIEW_PAGE_CONTAINS_TOPIC_LINK}" "True" "Control overview raw content did not include the generated topic link"

capture_log_artifact console "10-console.log"
capture_log_artifact network "11-network.log"

python - <<'PY' \
  "${SUMMARY_FILE}" \
  "${BASE_URL}" \
  "${TARGET_PAGE_TITLE}" \
  "${SAMPLE_PDF_PATH}" \
  "${FORCED_MODEL_ID}" \
  "${ACTIVE_MODEL_AFTER_REVIEW}" \
  "${MODEL_PROMOTED_FROM_MINI}" \
  "${LAUNCHER_PRESENT}" \
  "${ATTACHMENT_READY}" \
  "${REVIEW_CARD_PRESENT}" \
  "${REVIEW_MENTIONS_CONTROL_MANUAL}" \
  "${PRIMARY_TARGET_CONTROL}" \
  "${DRAFT_PREVIEW_PRESENT}" \
  "${DRAFT_COMMIT_SUCCESS}" \
  "${DRAFT_PAGE_TITLE}" \
  "${DRAFT_PAGE_CONTAINS_CONTROL_TARGET}" \
  "${DRAFT_PAGE_CONTAINS_PAGE_GALLERY}" \
  "${DRAFT_PAGE_CONTAINS_UPLOADED_FILES}" \
  "${FORMAL_PREVIEW_PRESENT}" \
  "${FORMAL_PREVIEW_TARGETS_CONTROL}" \
  "${FORMAL_PREVIEW_BLOCKED_ITEMS}" \
  "${FORMAL_COMMIT_SUCCESS}" \
  "${FORMAL_PAGE_TITLE}" \
  "${OVERVIEW_PAGE_TITLE}" \
  "${FORMAL_PAGE_CONTAINS_MANAGED_BLOCK}" \
  "${OVERVIEW_PAGE_CONTAINS_TOPIC_LINK}" \
  "00-resource-sync.json" \
  "01-page.yml" \
  "02-review.yml" \
  "03-preview.yml" \
  "04-commit.yml" \
  "05-formal-preview.yml" \
  "06-formal-commit.yml" \
  "07-draft-raw.txt" \
  "08-formal-raw.txt" \
  "09-overview-raw.txt" \
  "10-console.log" \
  "11-network.log"
from __future__ import annotations

import json
import pathlib
import sys

summary_path = pathlib.Path(sys.argv[1])
artifacts = list(sys.argv[27:])
summary = {
    "base_url": sys.argv[2],
    "target_page": sys.argv[3],
    "sample_pdf": sys.argv[4],
    "forced_model_before": sys.argv[5],
    "active_model_after_review": sys.argv[6],
    "model_promoted_from_mini": sys.argv[7] == "True",
    "launcher_present": sys.argv[8] == "True",
    "attachment_ready": sys.argv[9] == "True",
    "review_card_present": sys.argv[10] == "True",
    "review_mentions_control_manual": sys.argv[11] == "True",
    "primary_target_control": sys.argv[12] == "True",
    "draft_preview_present": sys.argv[13] == "True",
    "draft_commit_success": sys.argv[14] == "True",
    "draft_page_title": sys.argv[15],
    "draft_page_contains_control_target": sys.argv[16] == "True",
    "draft_page_contains_page_gallery": sys.argv[17] == "True",
    "draft_page_contains_uploaded_files": sys.argv[18] == "True",
    "formal_preview_present": sys.argv[19] == "True",
    "formal_preview_targets_control": sys.argv[20] == "True",
    "formal_preview_blocked_items": int(sys.argv[21]),
    "formal_commit_success": sys.argv[22] == "True",
    "formal_page_title": sys.argv[23],
    "overview_page_title": sys.argv[24],
    "formal_page_contains_managed_block": sys.argv[25] == "True",
    "overview_page_contains_topic_link": sys.argv[26] == "True",
    "artifacts": artifacts,
}
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
PY

python ops/scripts/render_pdf_ingest_report.py --summary-file "${SUMMARY_FILE}" --output "${REPORT_FILE}"
printf 'PDF ingest check complete. Report: %s\n' "${REPORT_FILE}"
