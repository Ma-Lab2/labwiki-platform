#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

BASE_URL="${BASE_URL:-http://localhost:8443}"
PRIVATE_USER="${PRIVATE_ADMIN_USER:-admin}"
PRIVATE_PASSWORD_FILE="${PRIVATE_PASSWORD_FILE:-${ROOT_DIR}/secrets/private_admin_password.txt}"
SESSION_NAME="${SESSION_NAME:-labwiki-pdf-reader-check}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ARTIFACT_DIR="${ARTIFACT_DIR:-${ROOT_DIR}/backups/validation/playwright-private-pdf-reader-${TIMESTAMP}}"
SAMPLE_PDF_PATH="${SAMPLE_PDF_PATH:-${ROOT_DIR}/backups/validation/tmp/labassistant-sample.pdf}"
WIKI_PDF_FILE_TITLE="${WIKI_PDF_FILE_TITLE:-LabAssistant-Sample-Paper-${TIMESTAMP}.pdf}"
LITERATURE_PAGE_WITH_PDF="${LITERATURE_PAGE_WITH_PDF:-文献导读/PDF阅读测试}"
LITERATURE_PAGE_EMPTY="${LITERATURE_PAGE_EMPTY:-文献导读/PDF阅读空状态测试}"
EMBEDDED_QUOTE_TEXT="${EMBEDDED_QUOTE_TEXT:-This is an embedded PDF excerpt for assistant follow-up.}"
ATTACHMENT_QUOTE_TEXT="${ATTACHMENT_QUOTE_TEXT:-This is an attachment PDF excerpt for assistant follow-up.}"
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

usage() {
  cat <<EOF
Usage: bash ops/scripts/playwright-private-pdf-reader-check.sh [options]

Options:
  --base-url <url>                 Private wiki entry (default: ${BASE_URL})
  --session-name <name>            Playwright session name (default: ${SESSION_NAME})
  --artifact-dir <path>            Directory for snapshots and report
  --sample-pdf <path>              Local PDF fixture (default: ${SAMPLE_PDF_PATH})
  --wiki-file-title <title>        Wiki file title used for the formal PDF fixture
  --literature-page-with-pdf <t>   Literature page seeded with a PDF field
  --literature-page-empty <t>      Literature page seeded without a PDF field
  --help                           Show this help text
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
    --sample-pdf)
      SAMPLE_PDF_PATH="${2:?missing value for --sample-pdf}"
      shift 2
      ;;
    --wiki-file-title)
      WIKI_PDF_FILE_TITLE="${2:?missing value for --wiki-file-title}"
      shift 2
      ;;
    --literature-page-with-pdf)
      LITERATURE_PAGE_WITH_PDF="${2:?missing value for --literature-page-with-pdf}"
      shift 2
      ;;
    --literature-page-empty)
      LITERATURE_PAGE_EMPTY="${2:?missing value for --literature-page-empty}"
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
EMBEDDED_QUOTE_TEXT_JSON="$(python - <<'PY' "${EMBEDDED_QUOTE_TEXT}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
ATTACHMENT_QUOTE_TEXT_JSON="$(python - <<'PY' "${ATTACHMENT_QUOTE_TEXT}"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
)"
WITH_PDF_PAGE_URL_PATH="$(python - <<'PY' "${LITERATURE_PAGE_WITH_PDF}"
from urllib.parse import quote
import sys
print("/index.php?title=" + quote(sys.argv[1], safe=""))
PY
)"
EMPTY_PAGE_URL_PATH="$(python - <<'PY' "${LITERATURE_PAGE_EMPTY}"
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
    value="$(python - <<'PY' "$(playwright-cli -s="${SESSION_NAME}" run-code "async page => await page.evaluate(() => (${expression}))" | sed -n '/^### Result/{n;p;}' | head -n 1)"
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

seed_pdf_fixture() {
  local container_id
  container_id="$(docker compose ps -q mw_private)"
  if [[ -z "${container_id}" ]]; then
    echo "mw_private container is not running." >&2
    exit 1
  fi

  docker compose exec -T mw_private sh -lc 'rm -rf /tmp/labassistant-pdf-fixture && mkdir -p /tmp/labassistant-pdf-fixture' >/dev/null
  docker cp "${SAMPLE_PDF_PATH}" "${container_id}:/tmp/labassistant-pdf-fixture/${WIKI_PDF_FILE_TITLE}" >/dev/null
  docker compose exec -T mw_private php maintenance/run.php importImages.php \
    --overwrite \
    --summary "Import PDF reader regression fixture" \
    --user "${PRIVATE_USER}" \
    /tmp/labassistant-pdf-fixture >/dev/null
}

seed_literature_page() {
  local title="$1"
  local include_pdf="$2"
  local pdf_line=""
  if [[ "${include_pdf}" == "with_pdf" ]]; then
    pdf_line="|PDF文件=File:${WIKI_PDF_FILE_TITLE}"
  fi

  docker compose exec -T mw_private php maintenance/run.php edit \
    --summary "Seed PDF reader regression fixture" \
    --user "${PRIVATE_USER}" \
    "${title}" >/dev/null <<EOF
{{文献导读
|标题=PDF 阅读自动化测试
|作者=LabAssistant Regression
|年份=2026
|DOI=10.0000/labassistant.pdf-reader
${pdf_line}
|摘要=这是用于 PDF 阅读模块自动化验收的文献导读测试页。
|相关页面=Theory:激光等离子体加速总览
|来源=Theory:激光等离子体加速总览
}}
EOF
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
seed_pdf_fixture
seed_literature_page "${LITERATURE_PAGE_WITH_PDF}" "with_pdf"
seed_literature_page "${LITERATURE_PAGE_EMPTY}" "empty"

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

EMPTY_URL="${BASE_URL%/}${EMPTY_PAGE_URL_PATH}"
playwright-cli -s="${SESSION_NAME}" goto "${EMPTY_URL}" >/dev/null
wait_for_page_ready
EMPTY_STATE_PRESENT="$(pl_eval_json 'Boolean(document.querySelector(".labassistant-pdf-reader-empty"))')"
EMPTY_EDIT_ENTRY_PRESENT="$(pl_eval_json 'Boolean(document.querySelector(".labassistant-pdf-reader-empty .labassistant-pdf-reader-button.is-link"))')"
assert_equals "${EMPTY_STATE_PRESENT}" "True" "Literature guide page without PDF did not show the empty reader state"
assert_equals "${EMPTY_EDIT_ENTRY_PRESENT}" "True" "Literature guide empty state did not expose the edit entry for associating a formal PDF"
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/01-literature-empty.yml" >/dev/null

WITH_PDF_URL="${BASE_URL%/}${WITH_PDF_PAGE_URL_PATH}"
playwright-cli -s="${SESSION_NAME}" goto "${WITH_PDF_URL}" >/dev/null
wait_for_page_ready
ASSET_VERSION_READY="$(pl_eval_json 'window.LabAssistantAssetVersion || (window.mw && mw.labassistantAssetVersion) || null')"
assert_equals "${ASSET_VERSION_READY}" "${ASSET_VERSION_EXPECTED}" "Assistant asset-version bootstrap did not reach the literature page runtime"
wait_for_playwright_true 'Boolean(document.querySelector(".labassistant-pdf-reader-source .labassistant-pdf-reader-shell"))' 15 \
  "Embedded literature PDF reader did not mount on the literature guide page"
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  const pageInput = page.locator('.labassistant-pdf-reader-source .labassistant-pdf-reader-page').first();
  await pageInput.fill('3');
  await pageInput.dispatchEvent('change');
}" >/dev/null
EMBEDDED_READER_PRESENT="$(pl_eval_json 'Boolean(document.querySelector(".labassistant-pdf-reader-source .labassistant-pdf-reader-shell"))')"
EMBEDDED_NAVIGATION_PRESENT="$(pl_eval_json 'Boolean((function () { var labels = Array.prototype.map.call(document.querySelectorAll(".labassistant-pdf-reader-source .labassistant-pdf-reader-button"), function (node) { return node.textContent || ""; }).join(" "); return labels.indexOf("上一页") !== -1 && labels.indexOf("下一页") !== -1 && labels.indexOf("编辑条目") !== -1; }()))')"
EMBEDDED_READER_SRC="$(pl_eval_json 'document.querySelector(".labassistant-pdf-reader-source .labassistant-pdf-reader-frame") ? document.querySelector(".labassistant-pdf-reader-source .labassistant-pdf-reader-frame").getAttribute("src") : ""')"
assert_equals "${EMBEDDED_READER_PRESENT}" "True" "Embedded literature PDF reader disappeared after page navigation controls updated"
assert_equals "${EMBEDDED_NAVIGATION_PRESENT}" "True" "Embedded literature PDF reader did not expose page navigation and edit-entry controls"
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/02-literature-reader.yml" >/dev/null

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.locator('.labassistant-pdf-reader-source .labassistant-pdf-reader-quote-input').first().fill(${EMBEDDED_QUOTE_TEXT_JSON});
  await page.locator('.labassistant-pdf-reader-source .labassistant-pdf-reader-button.is-primary').first().click();
  await page.waitForSelector('#labassistant-drawer-root:not([hidden])');
}" >/dev/null
EMBEDDED_QUOTE_SEEDED="$(pl_eval_json 'Boolean(document.querySelector("#labassistant-drawer-root .labassistant-question-input") && document.querySelector("#labassistant-drawer-root .labassistant-question-input").value.includes("PDF 文件：") && document.querySelector("#labassistant-drawer-root .labassistant-question-input").value.includes("引用选区：") && document.querySelector("#labassistant-drawer-root .labassistant-question-input").value.includes("embedded PDF excerpt"))')"
assert_equals "${EMBEDDED_QUOTE_SEEDED}" "True" "Embedded literature PDF quote was not seeded into the assistant composer"
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/03-embedded-quote-sent.yml" >/dev/null

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.locator('#labassistant-drawer-root input[type=file][accept*=\"application/pdf\"]').setInputFiles(${SAMPLE_PDF_PATH_JSON});
}" >/dev/null
wait_for_playwright_true 'Boolean(document.querySelector("#labassistant-drawer-root .labassistant-attachment-open"))' 15 \
  "Assistant PDF attachment chip did not render the reader action"
ATTACHMENT_CHIP_PRESENT="$(pl_eval_json 'Boolean(document.querySelector("#labassistant-drawer-root .labassistant-attachment-open"))')"
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.locator('#labassistant-drawer-root .labassistant-attachment-open', {
    hasText: '阅读'
  }).first().click();
  await page.waitForSelector('.labassistant-pdf-reader-floating-root:not([hidden]) .labassistant-pdf-reader-shell.is-floating');
}" >/dev/null
FLOATING_READER_PRESENT="$(pl_eval_json 'Boolean(document.querySelector(".labassistant-pdf-reader-floating-root:not([hidden]) .labassistant-pdf-reader-shell.is-floating"))')"
FLOATING_READER_SRC="$(pl_eval_json 'document.querySelector(".labassistant-pdf-reader-floating-root .labassistant-pdf-reader-frame") ? document.querySelector(".labassistant-pdf-reader-floating-root .labassistant-pdf-reader-frame").getAttribute("src") : ""')"
assert_equals "${FLOATING_READER_PRESENT}" "True" "Floating reader did not open from the assistant PDF attachment chip"
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.locator('.labassistant-pdf-reader-floating-root .labassistant-pdf-reader-quote-input').first().fill(${ATTACHMENT_QUOTE_TEXT_JSON});
  await page.locator('.labassistant-pdf-reader-floating-root .labassistant-pdf-reader-button.is-primary').first().click();
  await page.waitForTimeout(500);
}" >/dev/null
ATTACHMENT_QUOTE_SEEDED="$(pl_eval_json 'Boolean(document.querySelector("#labassistant-drawer-root .labassistant-question-input") && document.querySelector("#labassistant-drawer-root .labassistant-question-input").value.includes("attachment PDF excerpt") && document.querySelector("#labassistant-drawer-root .labassistant-question-input").value.includes("PDF 文件：labassistant-sample.pdf"))')"
assert_equals "${ATTACHMENT_QUOTE_SEEDED}" "True" "Attachment PDF quote was not seeded into the assistant composer"
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/04-attachment-reader.yml" >/dev/null

capture_log_artifact console "05-console.log"
capture_log_artifact network "06-network.log"

python - <<'PY' "${SUMMARY_FILE}" "${BASE_URL}" "${LITERATURE_PAGE_WITH_PDF}" "${LITERATURE_PAGE_EMPTY}" "${EMPTY_STATE_PRESENT}" "${EMBEDDED_READER_PRESENT}" "${EMBEDDED_NAVIGATION_PRESENT}" "${EMPTY_EDIT_ENTRY_PRESENT}" "${EMBEDDED_READER_SRC}" "${EMBEDDED_QUOTE_SEEDED}" "${ATTACHMENT_CHIP_PRESENT}" "${FLOATING_READER_PRESENT}" "${FLOATING_READER_SRC}" "${ATTACHMENT_QUOTE_SEEDED}"
import json
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
summary = {
    "base_url": sys.argv[2],
    "literature_page_with_pdf": sys.argv[3],
    "literature_page_empty": sys.argv[4],
    "empty_state_present": sys.argv[5] == "True",
    "embedded_reader_present": sys.argv[6] == "True",
    "embedded_navigation_present": sys.argv[7] == "True",
    "literature_edit_entry_present": sys.argv[8] == "True",
    "embedded_reader_src": sys.argv[9],
    "assistant_seeded_from_embedded_quote": sys.argv[10] == "True",
    "attachment_chip_present": sys.argv[11] == "True",
    "floating_reader_present": sys.argv[12] == "True",
    "floating_reader_src": sys.argv[13],
    "assistant_seeded_from_attachment_quote": sys.argv[14] == "True",
    "artifacts": [
        "01-literature-empty.yml",
        "02-literature-reader.yml",
        "03-embedded-quote-sent.yml",
        "04-attachment-reader.yml",
        "05-console.log",
        "06-network.log",
    ],
}
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
PY

python ops/scripts/render_pdf_reader_report.py --summary-file "${SUMMARY_FILE}" --output "${REPORT_FILE}"
printf 'PDF reader check complete. Report: %s\n' "${REPORT_FILE}"
