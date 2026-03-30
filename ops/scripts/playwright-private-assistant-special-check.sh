#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

BASE_URL="${BASE_URL:-http://localhost:8443}"
LOOPBACK_URL="${LOOPBACK_URL:-http://localhost:8443}"
PRIVATE_USER="${PRIVATE_ADMIN_USER:-admin}"
PRIVATE_PASSWORD_FILE="${PRIVATE_PASSWORD_FILE:-${ROOT_DIR}/secrets/private_admin_password.txt}"
SESSION_NAME="${SESSION_NAME:-labwiki-private-assistant-special-check}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ARTIFACT_DIR="${ARTIFACT_DIR:-${ROOT_DIR}/backups/validation/playwright-private-assistant-special-${TIMESTAMP}}"
REPORT_FILE="${ARTIFACT_DIR}/report.md"

usage() {
  cat <<EOF
Usage: bash ops/scripts/playwright-private-assistant-special-check.sh [options]

Options:
  --base-url <url>         Canonical private entry (default: ${BASE_URL})
  --loopback-url <url>     Loopback entry used to verify behavior (default: ${LOOPBACK_URL})
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
ASSISTANT_URL="${LOOPBACK_URL}/index.php?title=Special:%E7%9F%A5%E8%AF%86%E5%8A%A9%E6%89%8B"

mkdir -p "${ARTIFACT_DIR}"

cleanup() {
  playwright-cli -s="${SESSION_NAME}" close >/dev/null 2>&1 || true
}
trap cleanup EXIT

assert_equals() {
  local value="$1"
  local expected="$2"
  local message="$3"
  if [[ "${value}" != "${expected}" ]]; then
    echo "${message}: got '${value}', expected '${expected}'" >&2
    exit 1
  fi
}

assert_true() {
  local value="$1"
  local message="$2"
  if [[ "${value}" != "True" ]]; then
    echo "${message}: got '${value}', expected 'True'" >&2
    exit 1
  fi
}

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
  until docker compose exec -T caddy_private sh -lc \
    "curl -fsS -H 'Host: ${CANONICAL_HOST}' -o /dev/null 'http://127.0.0.1${login_path}'"; do
    attempts=$((attempts + 1))
    if [[ ${attempts} -ge 20 ]]; then
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

LOGIN_URL="${LOOPBACK_URL}/index.php?title=%E7%89%B9%E6%AE%8A:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95"
playwright-cli -s="${SESSION_NAME}" goto "${LOGIN_URL}" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.getByRole('textbox', { name: '用户名' }).fill(${PRIVATE_USER_JSON});
  await page.getByRole('textbox', { name: '密码' }).fill(${PRIVATE_PASSWORD_JSON});
  await page.getByRole('button', { name: '登录' }).click();
  await page.waitForLoadState('domcontentloaded');
}" >/dev/null

playwright-cli -s="${SESSION_NAME}" goto "${ASSISTANT_URL}" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/01-special-desktop.yml" >/dev/null

DESKTOP_JSON="$(playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.waitForSelector('.labassistant-workspace.is-special');
  return await page.evaluate(() => {
    const shell = document.querySelector('.labassistant-workspace.is-special');
    const layout = document.querySelector('.labassistant-special-layout');
    const historyPanel = document.querySelector('.labassistant-history-panel');
    const mainColumn = document.querySelector('.labassistant-main-column');
    const aside = document.querySelector('.labassistant-special-aside');
    const activeSession = localStorage.getItem('labassistant-active-session-id');
    const historyItems = Array.from(document.querySelectorAll('.labassistant-history-open'));
    const firstHistory = historyItems[0];
    const shellRect = shell ? shell.getBoundingClientRect() : null;
    const historyRect = historyPanel ? historyPanel.getBoundingClientRect() : null;
    const mainRect = mainColumn ? mainColumn.getBoundingClientRect() : null;
    return {
      hasSpecialShell: !!shell,
      hasLayout: !!layout,
      hasHistoryPanel: !!historyPanel,
      hasLegacyAside: !!aside,
      historyCount: historyItems.length,
      activeSession: activeSession,
      historyWidth: historyRect ? Math.round(historyRect.width) : 0,
      mainWidth: mainRect ? Math.round(mainRect.width) : 0,
      shellWidth: shellRect ? Math.round(shellRect.width) : 0,
      historyButtonText: document.querySelector('.labassistant-history-header strong')?.textContent?.trim() || '',
      newChatVisible: !!Array.from(document.querySelectorAll('button')).find(btn => btn.textContent.trim() === '+ 新会话'),
      searchPlaceholder: document.querySelector('.labassistant-history-search')?.getAttribute('placeholder') || '',
      transcriptHeading: document.querySelector('.labassistant-panel-header h2')?.textContent?.trim() || '',
      transcriptContext: document.querySelector('.labassistant-panel-header .labassistant-context-chip')?.textContent?.trim() || '',
      firstHistoryLabel: firstHistory ? firstHistory.textContent.trim() : ''
    };
  });
}")"
DESKTOP_RAW="$(printf '%s\n' "${DESKTOP_JSON}" | sed -n '/^### Result/{n;p;}' | head -n 1)"
python - <<'PY' "${DESKTOP_RAW}" > "${ARTIFACT_DIR}/desktop-metrics.json"
import json, sys
print(json.dumps(json.loads(sys.argv[1]), ensure_ascii=False, indent=2))
PY

DESKTOP_HAS_SPECIAL="$(python - <<'PY' "${DESKTOP_RAW}"
import json, sys
print(json.loads(sys.argv[1])["hasSpecialShell"])
PY
)"
DESKTOP_HAS_HISTORY="$(python - <<'PY' "${DESKTOP_RAW}"
import json, sys
print(json.loads(sys.argv[1])["hasHistoryPanel"])
PY
)"
DESKTOP_HAS_ASIDE="$(python - <<'PY' "${DESKTOP_RAW}"
import json, sys
print(json.loads(sys.argv[1])["hasLegacyAside"])
PY
)"
DESKTOP_HISTORY_COUNT="$(python - <<'PY' "${DESKTOP_RAW}"
import json, sys
print(json.loads(sys.argv[1])["historyCount"])
PY
)"
DESKTOP_ACTIVE_SESSION="$(python - <<'PY' "${DESKTOP_RAW}"
import json, sys
value = json.loads(sys.argv[1])["activeSession"]
print("" if value is None else value)
PY
)"
DESKTOP_HISTORY_WIDTH="$(python - <<'PY' "${DESKTOP_RAW}"
import json, sys
print(json.loads(sys.argv[1])["historyWidth"])
PY
)"
DESKTOP_MAIN_WIDTH="$(python - <<'PY' "${DESKTOP_RAW}"
import json, sys
print(json.loads(sys.argv[1])["mainWidth"])
PY
)"

assert_equals "${DESKTOP_HAS_SPECIAL}" "True" "Assistant special shell did not render"
assert_equals "${DESKTOP_HAS_HISTORY}" "True" "Assistant special history rail did not render"
assert_equals "${DESKTOP_HAS_ASIDE}" "False" "Legacy special-page aside is still present"
if [[ "${DESKTOP_HISTORY_COUNT}" -lt 1 ]]; then
  echo "Assistant special page did not show any history sessions" >&2
  exit 1
fi
if [[ -n "${DESKTOP_ACTIVE_SESSION}" ]]; then
  echo "Assistant special page unexpectedly hydrated a stored session: ${DESKTOP_ACTIVE_SESSION}" >&2
  exit 1
fi
if [[ "${DESKTOP_HISTORY_WIDTH}" -lt 240 ]]; then
  echo "History rail width is too small on desktop: ${DESKTOP_HISTORY_WIDTH}" >&2
  exit 1
fi
if [[ "${DESKTOP_MAIN_WIDTH}" -le "${DESKTOP_HISTORY_WIDTH}" ]]; then
  echo "Main column width did not exceed history rail width on desktop" >&2
  exit 1
fi

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  const firstHistory = page.locator('.labassistant-history-open').first();
  await firstHistory.click();
  await page.waitForFunction(() => {
    const active = document.querySelector('.labassistant-history-open.is-active');
    const sessionId = localStorage.getItem('labassistant-active-session-id');
    const messages = document.querySelectorAll('.labassistant-message').length;
    return Boolean(active && sessionId && messages > 0);
  }, { timeout: 15000 });
}" >/dev/null
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/02-special-history-loaded.yml" >/dev/null

POST_HISTORY_JSON="$(playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  return await page.evaluate(() => ({
    activeHistoryCount: document.querySelectorAll('.labassistant-history-open.is-active').length,
    activeSession: localStorage.getItem('labassistant-active-session-id'),
    messageCount: document.querySelectorAll('.labassistant-message').length,
    heading: document.querySelector('.labassistant-session-badge')?.textContent?.trim() || ''
  }));
}")"
POST_HISTORY_RAW="$(printf '%s\n' "${POST_HISTORY_JSON}" | sed -n '/^### Result/{n;p;}' | head -n 1)"
python - <<'PY' "${POST_HISTORY_RAW}" > "${ARTIFACT_DIR}/history-loaded-metrics.json"
import json, sys
print(json.dumps(json.loads(sys.argv[1]), ensure_ascii=False, indent=2))
PY

POST_HISTORY_SESSION_ID="$(python - <<'PY' "${POST_HISTORY_RAW}"
import json, sys
print(json.loads(sys.argv[1])["activeSession"] or "")
PY
)"

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.getByRole('button', { name: '新会话' }).click();
  await page.waitForFunction(() => {
    const sessionId = localStorage.getItem('labassistant-active-session-id');
    const activeHistory = document.querySelector('.labassistant-history-open.is-active');
    const badge = document.querySelector('.labassistant-session-badge');
    return !sessionId && !activeHistory && badge && badge.textContent.includes('新会话');
  }, { timeout: 10000 });
}" >/dev/null
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/03-special-new-session.yml" >/dev/null

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  const firstHistory = page.locator('.labassistant-history-open').first();
  await firstHistory.click();
  await page.waitForFunction(() => {
    return Boolean(
      document.querySelector('.labassistant-history-open.is-active') &&
      localStorage.getItem('labassistant-active-session-id') &&
      document.querySelectorAll('.labassistant-message').length > 0
    );
  }, { timeout: 15000 });
  const input = page.getByRole('textbox', { name: '输入问题' });
  await input.fill('请只回复：收到。');
  await page.getByRole('button', { name: '发送' }).click();
  await page.waitForFunction(() => document.querySelector('.labassistant-send-button')?.disabled === true, { timeout: 5000 });
  await page.waitForFunction(async previousSessionId => {
    const sessionId = localStorage.getItem('labassistant-active-session-id');
    if (!sessionId || sessionId !== previousSessionId) {
      return false;
    }
    const response = await fetch('/tools/assistant/api/session/' + encodeURIComponent(sessionId) + '?user_name=Admin', {
      credentials: 'same-origin'
    });
    if (!response.ok) {
      return false;
    }
    const body = await response.json();
    return body && body.last_stage === 'completed' && Array.isArray(body.turns) && body.turns.length >= 2;
  }, ${POST_HISTORY_SESSION_ID@Q}, { timeout: 180000 });
}" >/dev/null
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/04-special-after-reply.yml" >/dev/null

SEND_JSON="$(playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  return await page.evaluate(async () => {
    const messages = Array.from(document.querySelectorAll('.labassistant-message')).slice(-4).map(node => node.textContent.trim());
    const sessionId = localStorage.getItem('labassistant-active-session-id');
    let turnCount = null;
    let lastStage = null;
    if (sessionId) {
      const response = await fetch('/tools/assistant/api/session/' + encodeURIComponent(sessionId) + '?user_name=Admin', {
        credentials: 'same-origin'
      });
      if (response.ok) {
        const body = await response.json();
        turnCount = Array.isArray(body.turns) ? body.turns.length : null;
        lastStage = body.last_stage || null;
      }
    }
    return {
      activeSession: sessionId,
      messageCount: document.querySelectorAll('.labassistant-message').length,
      sendDisabled: document.querySelector('.labassistant-send-button')?.disabled ?? null,
      turnCount: turnCount,
      lastStage: lastStage,
      recentMessages: messages
    };
  });
}")"
SEND_RAW="$(printf '%s\n' "${SEND_JSON}" | sed -n '/^### Result/{n;p;}' | head -n 1)"
python - <<'PY' "${SEND_RAW}" > "${ARTIFACT_DIR}/send-metrics.json"
import json, sys
print(json.dumps(json.loads(sys.argv[1]), ensure_ascii=False, indent=2))
PY

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.setViewportSize({ width: 430, height: 932 });
  await page.goto(${ASSISTANT_URL@Q});
}" >/dev/null
wait_for_page_ready
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/05-special-mobile-closed.yml" >/dev/null

MOBILE_CLOSED_JSON="$(playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  return await page.evaluate(() => {
    const shell = document.querySelector('.labassistant-special-layout');
    const historyPanel = document.querySelector('.labassistant-history-panel');
    const backdrop = document.querySelector('.labassistant-special-backdrop');
    const style = historyPanel ? window.getComputedStyle(historyPanel) : null;
    return {
      isHistoryOpen: shell ? shell.classList.contains('is-history-open') : null,
      historyTransform: style ? style.transform : null,
      backdropHidden: backdrop ? backdrop.hasAttribute('hidden') : null
    };
  });
}")"
MOBILE_CLOSED_RAW="$(printf '%s\n' "${MOBILE_CLOSED_JSON}" | sed -n '/^### Result/{n;p;}' | head -n 1)"
python - <<'PY' "${MOBILE_CLOSED_RAW}" > "${ARTIFACT_DIR}/mobile-closed-metrics.json"
import json, sys
print(json.dumps(json.loads(sys.argv[1]), ensure_ascii=False, indent=2))
PY

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  await page.getByRole('button', { name: '历史' }).click();
  await page.waitForFunction(() => {
    const shell = document.querySelector('.labassistant-special-layout');
    const backdrop = document.querySelector('.labassistant-special-backdrop');
    return Boolean(shell && shell.classList.contains('is-history-open') && backdrop && !backdrop.hasAttribute('hidden'));
  }, { timeout: 10000 });
}" >/dev/null
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/06-special-mobile-open.yml" >/dev/null

MOBILE_OPEN_JSON="$(playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  return await page.evaluate(() => {
    const shell = document.querySelector('.labassistant-special-layout');
    const historyPanel = document.querySelector('.labassistant-history-panel');
    const backdrop = document.querySelector('.labassistant-special-backdrop');
    const style = historyPanel ? window.getComputedStyle(historyPanel) : null;
    return {
      isHistoryOpen: shell ? shell.classList.contains('is-history-open') : null,
      historyTransform: style ? style.transform : null,
      backdropHidden: backdrop ? backdrop.hasAttribute('hidden') : null
    };
  });
}")"
MOBILE_OPEN_RAW="$(printf '%s\n' "${MOBILE_OPEN_JSON}" | sed -n '/^### Result/{n;p;}' | head -n 1)"
python - <<'PY' "${MOBILE_OPEN_RAW}" > "${ARTIFACT_DIR}/mobile-open-metrics.json"
import json, sys
print(json.dumps(json.loads(sys.argv[1]), ensure_ascii=False, indent=2))
PY

playwright-cli -s="${SESSION_NAME}" run-code "async page => {
  const backdrop = page.locator('.labassistant-special-backdrop');
  await backdrop.click({ position: { x: 10, y: 10 } });
  await page.waitForFunction(() => {
    const shell = document.querySelector('.labassistant-special-layout');
    const backdropNode = document.querySelector('.labassistant-special-backdrop');
    return Boolean(shell && !shell.classList.contains('is-history-open') && backdropNode && backdropNode.hasAttribute('hidden'));
  }, { timeout: 10000 });
}" >/dev/null
playwright-cli -s="${SESSION_NAME}" snapshot --filename="${ARTIFACT_DIR}/07-special-mobile-closed-again.yml" >/dev/null

cat > "${REPORT_FILE}" <<EOF
# Private Assistant Special Check

- Loopback URL: \`${LOOPBACK_URL}\`
- Assistant URL: \`${ASSISTANT_URL}\`
- Desktop history sessions present: \`${DESKTOP_HISTORY_COUNT}\`
- Desktop active session on first load: \`${DESKTOP_ACTIVE_SESSION:-<empty>}\`
- Desktop history width: \`${DESKTOP_HISTORY_WIDTH}\`
- Desktop main width: \`${DESKTOP_MAIN_WIDTH}\`
- Desktop special shell present: \`${DESKTOP_HAS_SPECIAL}\`
- Desktop history rail present: \`${DESKTOP_HAS_HISTORY}\`
- Legacy aside present: \`${DESKTOP_HAS_ASIDE}\`

## Artifacts

- \`01-special-desktop.yml\`
- \`02-special-history-loaded.yml\`
- \`03-special-new-session.yml\`
- \`04-special-after-reply.yml\`
- \`05-special-mobile-closed.yml\`
- \`06-special-mobile-open.yml\`
- \`07-special-mobile-closed-again.yml\`
- \`desktop-metrics.json\`
- \`history-loaded-metrics.json\`
- \`send-metrics.json\`
- \`mobile-closed-metrics.json\`
- \`mobile-open-metrics.json\`
EOF

printf 'Report written to %s\n' "${REPORT_FILE}"
