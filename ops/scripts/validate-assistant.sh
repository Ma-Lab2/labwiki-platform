#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

compose_cmd=(docker compose -f compose.yaml)
if [[ "${LABWIKI_LOCAL_OVERRIDE:-false}" == "true" ]]; then
  compose_cmd+=(-f compose.override.yaml)
fi

PROFILE="contract"
RUN_SMOKE="true"
COMMIT_DRAFT="false"
REINDEX_TIMEOUT=1200
POLL_INTERVAL=5
REPORT_FILE=""
OUTPUT_CAPTURE_FILE=""

usage() {
  cat <<'EOF'
Usage: bash ops/scripts/validate-assistant.sh [options]

Options:
  --profile <contract|chat|full>  Validation depth (default: contract)
  --skip-smoke                    Do not run ops/scripts/smoke-test.sh first
  --commit-draft                  Commit the generated draft preview during validation
  --reindex-timeout <seconds>     Timeout for full-profile wiki reindex wait (default: 1200)
  --poll-interval <seconds>       Poll interval for long-running checks (default: 5)
  --report-file <path>            Write a JSON validation report to the given path
  --help                          Show this help text

Profiles:
  contract  Health, plan, tool health, draft preview, stats, zotero behavior
  chat      contract + chat / compare / session verification
  full      chat + wiki reindex wait + index stats assertions

Environment:
  LABWIKI_LOCAL_OVERRIDE=true
    Include compose.override.yaml in docker compose commands.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="${2:-}"
      shift
      ;;
    --skip-smoke)
      RUN_SMOKE="false"
      ;;
    --commit-draft)
      COMMIT_DRAFT="true"
      ;;
    --reindex-timeout)
      REINDEX_TIMEOUT="${2:-}"
      shift
      ;;
    --poll-interval)
      POLL_INTERVAL="${2:-}"
      shift
      ;;
    --report-file)
      REPORT_FILE="${2:-}"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

case "${PROFILE}" in
  contract|chat|full)
    ;;
  *)
    printf 'Unsupported profile: %s\n' "${PROFILE}" >&2
    usage >&2
    exit 1
    ;;
esac

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not in PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose plugin is not available." >&2
  exit 1
fi

echo "[step] Verify assistant-related services exist"
"${compose_cmd[@]}" ps assistant_store assistant_api assistant_worker mw_private caddy_private >/dev/null
PRIVATE_PROXY_HOST_HEADER="$("${compose_cmd[@]}" exec -T mw_private sh -lc 'printf %s "$MW_SERVER"' | python -c 'from urllib.parse import urlparse; import sys; raw = sys.stdin.read().strip(); print(urlparse(raw).netloc if raw else "")')"

if [[ "${RUN_SMOKE}" == "true" ]]; then
  echo "[step] Run smoke test"
  bash ops/scripts/smoke-test.sh
else
  echo "[step] Check private wiki runtime resources match repo"
  python ops/scripts/check_mediawiki_resource_sync.py --service mw_private >/dev/null
fi

echo "[step] Run assistant validation profile: ${PROFILE}"
OUTPUT_CAPTURE_FILE="$(mktemp)"
trap 'rm -f "${OUTPUT_CAPTURE_FILE}"' EXIT
set +e
"${compose_cmd[@]}" exec -T \
  -e VALIDATION_PROFILE="${PROFILE}" \
  -e VALIDATION_COMMIT_DRAFT="${COMMIT_DRAFT}" \
  -e VALIDATION_REINDEX_TIMEOUT="${REINDEX_TIMEOUT}" \
  -e VALIDATION_POLL_INTERVAL="${POLL_INTERVAL}" \
  -e VALIDATION_PROXY_HOST_HEADER="${PRIVATE_PROXY_HOST_HEADER}" \
  assistant_api python - <<'PY' 2>&1 | tee "${OUTPUT_CAPTURE_FILE}" | sed '/^__VALIDATION_REPORT_JSON__=/d'
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


PROFILE = os.getenv("VALIDATION_PROFILE", "contract")
COMMIT_DRAFT = os.getenv("VALIDATION_COMMIT_DRAFT", "false").lower() == "true"
REINDEX_TIMEOUT = int(os.getenv("VALIDATION_REINDEX_TIMEOUT", "1200"))
POLL_INTERVAL = int(os.getenv("VALIDATION_POLL_INTERVAL", "5"))
API_BASE = "http://127.0.0.1:8000"
API_PROXY_BASE = "http://caddy_private/tools/assistant/api"
PROXY_HOST_HEADER = os.getenv("VALIDATION_PROXY_HOST_HEADER", "").strip()
EMBEDDING_MODEL = os.getenv("ASSISTANT_EMBEDDING_MODEL", "").strip()
EMBEDDING_DIMENSIONS = int(os.getenv("ASSISTANT_EMBEDDING_DIMENSIONS", "1536"))
DRAFT_PREFIX = os.getenv("ASSISTANT_DRAFT_PREFIX", "知识助手草稿")
CHECKS: list[dict[str, object]] = []
REPORT: dict[str, object] = {
    "profile": PROFILE,
    "commit_draft": COMMIT_DRAFT,
    "embedding_model": EMBEDDING_MODEL,
    "embedding_dimensions": EMBEDDING_DIMENSIONS,
    "validation_generation_model": None,
    "api_base": API_BASE,
    "api_proxy_base": API_PROXY_BASE,
    "status": "running",
    "checks": CHECKS,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}


def emit_report() -> None:
    print(f"__VALIDATION_REPORT_JSON__={json.dumps(REPORT, ensure_ascii=False, separators=(',', ':'))}")


def fail(label: str, detail: str, payload: object | None = None) -> None:
    CHECKS.append({"label": label, "status": "failed", "detail": detail, "payload": payload})
    REPORT["status"] = "failed"
    print(f"[fail] {label}: {detail}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    emit_report()
    raise SystemExit(1)


def ok(label: str, detail: str) -> None:
    CHECKS.append({"label": label, "status": "ok", "detail": detail})
    print(f"[ok] {label}: {detail}")


def request_json(method: str, path: str, payload: dict | None = None, timeout: int = 180, attempts: int = 1, retry_statuses: tuple[int, ...] = ()) -> dict:
    return request_json_at(API_BASE, method, path, payload=payload, timeout=timeout, attempts=attempts, retry_statuses=retry_statuses)


def request_json_at(
    base_url: str,
    method: str,
    path: str,
    payload: dict | None = None,
    timeout: int = 180,
    attempts: int = 1,
    retry_statuses: tuple[int, ...] = (),
    headers: dict[str, str] | None = None,
) -> dict:
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_body = None
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(
            base_url + path,
            data=data,
            headers={"Content-Type": "application/json", **(headers or {})},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            last_body = error.read().decode("utf-8", errors="replace")
            if error.code in retry_statuses and attempt < attempts:
                time.sleep(min(5, attempt * 2))
                continue
            fail(f"{method} {base_url}{path}", f"HTTP {error.code}", last_body)
    fail(f"{method} {base_url}{path}", "request failed after retries", last_body)


def collect_sse_events(
    base_url: str,
    path: str,
    payload: dict,
    max_events: int = 8,
    timeout: int = 180,
    headers: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    for attempt in range(1, 4):
        req = urllib.request.Request(
            base_url + path,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    fail(f"POST {path}", f"unexpected HTTP status {response.status}", {"base_url": base_url})
                events: list[dict[str, object]] = []
                current_event = "message"
                data_lines: list[str] = []
                while len(events) < max_events:
                    raw_line = response.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line.startswith("event:"):
                        current_event = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line.split(":", 1)[1].strip())
                    elif line == "":
                        if data_lines:
                            try:
                                payload_data = json.loads("\n".join(data_lines))
                            except json.JSONDecodeError:
                                payload_data = {"raw": "\n".join(data_lines)}
                            events.append({"event": current_event, "data": payload_data})
                            if current_event in {"done", "error"}:
                                return events
                        current_event = "message"
                        data_lines = []
                return events
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            if error.code in {429, 500, 502, 503, 504} and attempt < 3:
                time.sleep(min(5, attempt * 2))
                continue
            fail(f"POST {base_url}{path}", f"HTTP {error.code}", body)
    fail(f"POST {base_url}{path}", "SSE request failed after retries", payload)


def assert_true(label: str, condition: bool, payload: object, detail: str) -> None:
    if not condition:
        fail(label, detail, payload)
    ok(label, detail)


def source_stats_map(payload: dict) -> dict[str, dict]:
    return {item["source_type"]: item for item in payload.get("source_stats", [])}


def pick_validation_generation_model(catalog: dict) -> str | None:
    preferred = [
        "gpt-5.4-mini",
        "gpt-5.4",
        "gemini-3-flash-preview-thinking",
        "gemini-3-flash-preview",
        "gemini-3-pro-thinking",
        "gemini-3-pro",
        "claude-sonnet-4-5-20250929",
    ]
    available = {
        item.get("id")
        for group in catalog.get("groups", [])
        for item in group.get("items", [])
        if item.get("id")
    }
    for model_id in preferred:
        if model_id in available:
            return model_id
    for group in catalog.get("groups", []):
        for item in group.get("items", []):
            if item.get("id"):
                return item["id"]
    return None


def pick_alternate_generation_model(catalog: dict, current_model: str | None) -> str | None:
    preferred = [
        "gemini-3-flash-preview-thinking",
        "gpt-5.4-mini",
        "gpt-5.4",
        "gemini-3-flash-preview",
        "gemini-3-pro-thinking",
        "gemini-3-pro",
        "claude-sonnet-4-5-20250929",
    ]
    available = {
        item.get("id")
        for group in catalog.get("groups", [])
        for item in group.get("items", [])
        if item.get("id")
    }
    for model_id in preferred:
        if model_id in available and model_id != current_model:
            return model_id
    for group in catalog.get("groups", []):
        for item in group.get("items", []):
            model_id = item.get("id")
            if model_id and model_id != current_model:
                return model_id
    return None


health = request_json("GET", "/health")
assert_true("health", health.get("status") == "ok", health, "assistant API is healthy")

proxy_headers = {"Host": PROXY_HOST_HEADER} if PROXY_HOST_HEADER else None

proxy_health = request_json_at(API_PROXY_BASE, "GET", "/health", headers=proxy_headers)
assert_true(
    "proxy-health",
    proxy_health.get("status") == "ok",
    proxy_health,
    "assistant API is reachable through the private wiki proxy path",
)

stats = request_json("GET", "/admin/stats")
assert_true(
    "admin-stats",
    all(key in stats for key in ["sessions_total", "turns_total", "chunks_total", "pending_jobs"]),
    stats,
    "admin stats returned core counters",
)

index_stats = request_json("GET", "/admin/index/stats")
assert_true(
    "index-stats-shape",
    all(key in index_stats for key in ["embedding_dimensions", "documents_total", "chunks_total", "embedded_chunks", "source_stats"]),
    index_stats,
    "index stats returned dimension and source breakdown",
)

model_catalog = request_json("GET", "/models/catalog")
catalog_group_ids = [item.get("id") for item in model_catalog.get("groups", [])]
assert_true(
    "models-catalog",
    all(group in catalog_group_ids for group in ["gpt", "claude", "gemini"]) and bool(model_catalog.get("default_model")),
    model_catalog,
    "models catalog exposes GPT, Claude, and Gemini groups",
)
validation_generation_model = pick_validation_generation_model(model_catalog)
REPORT["validation_generation_model"] = validation_generation_model
assert_true(
    "models-validation-selection",
    bool(validation_generation_model),
    model_catalog,
    "validation selected an available generation model",
)

concept_plan = request_json(
    "POST",
    "/plan",
    {"question": "总结 FAQ:知识助手使用说明 的核心用法", "mode": "qa", "detail_level": "intro", "context_pages": []},
)
assert_true(
    "plan-concept",
    concept_plan.get("task_type") == "concept" and len(concept_plan.get("planned_sources", [])) >= 2,
    concept_plan,
    "concept planning prefers local sources",
)

compare_plan = request_json(
    "POST",
    "/plan",
    {"question": "比较 TPS 和 RCF 的用途", "mode": "compare", "detail_level": "research", "context_pages": []},
)
assert_true(
    "plan-compare",
    compare_plan.get("task_type") == "compare" and compare_plan.get("needs_external_search") is True,
    compare_plan,
    "compare planning requests external expansion",
)

draft_plan = request_json(
    "POST",
    "/plan",
    {"question": "把 Shot 记录流程整理成条目草稿", "mode": "draft", "detail_level": "intro", "context_pages": []},
)
assert_true(
    "plan-draft",
    draft_plan.get("task_type") == "draft" and draft_plan.get("will_generate_draft_preview") is True,
    draft_plan,
    "draft planning enables preview generation",
)

tps_health = request_json("POST", "/tool/execute", {"tool": "tps", "action": "health", "payload": {}})
assert_true("tool-tps-health", bool(tps_health), tps_health, "TPS tool returned a non-empty payload")

rcf_health = request_json("POST", "/tool/execute", {"tool": "rcf", "action": "health", "payload": {}})
assert_true("tool-rcf-health", bool(rcf_health), rcf_health, "RCF tool returned a non-empty payload")

draft_preview = request_json(
    "POST",
    "/draft/preview",
    {
        "question": "把知识助手使用方式整理成草稿",
        "answer": "知识助手支持问答、比较、草稿预览和工具接口调用。",
        "source_titles": ["FAQ:知识助手使用说明"],
        "mode": "draft",
        "generation_model": validation_generation_model,
    },
    attempts=3,
    retry_statuses=(429, 500, 502, 503, 504),
)
assert_true(
    "draft-preview",
    draft_preview.get("target_page", "").startswith(f"{DRAFT_PREFIX}/") and bool(draft_preview.get("content")),
    draft_preview,
    "draft preview stays within the configured draft prefix",
)

if COMMIT_DRAFT:
    draft_commit = request_json("POST", "/draft/commit", {"preview_id": draft_preview["preview_id"]})
    assert_true(
        "draft-commit",
        draft_commit.get("status") == "ok" and draft_commit.get("page_title") == draft_preview["target_page"],
        draft_commit,
        "draft commit created or updated the target draft page",
    )

zotero_reindex = request_json("POST", "/reindex/zotero", {})
assert_true(
    "reindex-zotero",
    zotero_reindex.get("status") in {"disabled", "pending"},
    zotero_reindex,
    "zotero reindex is either disabled by config or successfully queued",
)

chat_session_id: str | None = None
if PROFILE in {"chat", "full"}:
    concept_chat = request_json(
        "POST",
        "/chat",
        {
            "question": "总结 FAQ:知识助手使用说明 的核心用法",
            "mode": "qa",
            "detail_level": "intro",
            "context_pages": [],
            "generation_model": validation_generation_model,
        },
        timeout=300,
        attempts=3,
        retry_statuses=(429, 500, 502, 503, 504),
    )
    assert_true(
        "chat-concept",
        bool(concept_chat.get("answer")) and len(concept_chat.get("sources", [])) >= 1,
        concept_chat,
        "concept chat returned an answer with sources",
    )
    chat_session_id = concept_chat.get("session_id")

    followup_chat = request_json(
        "POST",
        "/chat",
        {
            "question": "继续上一轮，强调多轮上下文、流式返回和草稿预览",
            "mode": "qa",
            "detail_level": "intro",
            "context_pages": [],
            "session_id": chat_session_id,
            "generation_model": validation_generation_model,
        },
        timeout=300,
        attempts=3,
        retry_statuses=(429, 500, 502, 503, 504),
    )
    assert_true(
        "chat-followup",
        followup_chat.get("session_id") == chat_session_id and bool(followup_chat.get("answer")),
        followup_chat,
        "follow-up chat reuses the existing session and returns an answer",
    )

    compare_chat = request_json(
        "POST",
        "/compare",
        {
            "question": "比较 TPS 和 RCF 的用途",
            "mode": "qa",
            "detail_level": "research",
            "context_pages": [],
            "generation_model": validation_generation_model,
        },
        timeout=300,
        attempts=3,
        retry_statuses=(429, 500, 502, 503, 504),
    )
    assert_true(
        "chat-compare",
        compare_chat.get("task_type") == "compare" and bool(compare_chat.get("answer")),
        compare_chat,
        "compare chat returned a compare answer",
    )

    tool_chat = request_json(
        "POST",
        "/chat",
        {
            "question": "RCF 堆栈验证怎么做",
            "mode": "qa",
            "detail_level": "intermediate",
            "context_pages": [],
            "generation_model": validation_generation_model,
        },
        timeout=300,
        attempts=3,
        retry_statuses=(429, 500, 502, 503, 504),
    )
    assert_true(
        "chat-tool-workflow",
        bool(tool_chat.get("answer")) and len(tool_chat.get("step_stream", [])) >= 1,
        tool_chat,
        "tool workflow chat returned a structured response",
    )

    write_chat = request_json(
        "POST",
        "/chat",
        {
            "question": "新建一个术语条目，解释TNSA，并关联Theory:激光-等离子体相互作用基础",
            "mode": "qa",
            "detail_level": "intro",
            "context_pages": [],
            "generation_model": validation_generation_model,
        },
        timeout=300,
        attempts=3,
        retry_statuses=(429, 500, 502, 503, 504),
    )
    write_trace_actions = [item.get("action") for item in write_chat.get("action_trace", [])]
    assert_true(
        "chat-write-action",
        write_chat.get("task_type") == "write_action"
        and bool(write_chat.get("write_preview"))
        and bool(write_chat.get("write_result"))
        and "commit_write" in write_trace_actions,
        write_chat,
        "write-action chat auto-commits a whitelist write and records commit_write in action_trace",
    )
    write_session_detail = request_json("GET", f"/session/{write_chat['session_id']}")
    latest_turn = (write_session_detail.get("turns") or [])[-1] if (write_session_detail.get("turns") or []) else {}
    latest_turn_actions = [item.get("action") for item in latest_turn.get("action_trace", [])]
    assert_true(
        "session-detail-rich-turns",
        latest_turn.get("turn_id") == write_chat.get("turn_id")
        and bool(latest_turn.get("write_preview"))
        and bool(latest_turn.get("write_result"))
        and "commit_write" in latest_turn_actions,
        write_session_detail,
        "session detail exposes rich turn history with previews, write results, and action trace",
    )

    if chat_session_id:
        session_detail = request_json("GET", f"/session/{chat_session_id}")
        assert_true(
            "session-detail",
            session_detail.get("session_id") == chat_session_id and len(session_detail.get("turns", [])) >= 2,
            session_detail,
            "session detail exposes multiple stored turns for the same session",
        )
        selected_switch_model = pick_alternate_generation_model(model_catalog, validation_generation_model)
        if selected_switch_model:
            model_update = request_json(
                "PATCH",
                f"/session/{chat_session_id}/model",
                {"generation_model": selected_switch_model},
            )
            assert_true(
                "session-model-update",
                model_update.get("status") == "ok" and model_update.get("model_info", {}).get("requested_model") == selected_switch_model,
                model_update,
                "session model update endpoint persists the selected model",
            )

    sse_events = collect_sse_events(
        API_BASE,
        "/chat/stream",
        {
            "question": "总结知识助手当前的流式接口和来源策略",
            "mode": "qa",
            "detail_level": "intro",
            "context_pages": [],
            "generation_model": validation_generation_model,
        },
        max_events=10,
        timeout=300,
    )
    event_names = [item.get("event") for item in sse_events]
    assert_true(
        "chat-stream-direct",
        "session_started" in event_names and "step" in event_names and "token" in event_names,
        sse_events,
        "direct SSE chat emits session, step, and token events",
    )

    proxy_sse_events = collect_sse_events(
        API_PROXY_BASE,
        "/chat/stream",
        {
            "question": "测试SSE代理链路",
            "mode": "qa",
            "detail_level": "intro",
            "context_pages": [],
            "generation_model": validation_generation_model,
        },
        max_events=6,
        timeout=300,
        headers=proxy_headers,
    )
    proxy_event_names = [item.get("event") for item in proxy_sse_events]
    assert_true(
        "chat-stream-proxy",
        "session_started" in proxy_event_names and "step" in proxy_event_names,
        proxy_sse_events,
        "SSE chat is reachable through the private wiki reverse proxy",
    )

    write_sse_events = collect_sse_events(
        API_BASE,
        "/chat/stream",
        {
            "question": "新建一个术语条目，解释TNSA，并关联Theory:激光-等离子体相互作用基础",
            "mode": "qa",
            "detail_level": "intro",
            "context_pages": [],
            "generation_model": validation_generation_model,
        },
        max_events=400,
        timeout=300,
    )
    write_sse_event_names = [item.get("event") for item in write_sse_events]
    assert_true(
        "chat-stream-write-action",
        "action_trace" in write_sse_event_names and "write_preview" in write_sse_event_names and "write_result" in write_sse_event_names and "done" in write_sse_event_names,
        write_sse_events,
        "write-action SSE emits action_trace, write_preview, write_result, and done events",
    )

if PROFILE == "full":
    reindex_wiki = request_json("POST", "/reindex/wiki", {})
    assert_true(
        "reindex-wiki-queued",
        reindex_wiki.get("status") == "pending" and bool(reindex_wiki.get("job_id")),
        reindex_wiki,
        "wiki reindex job was queued",
    )
    job_id = reindex_wiki["job_id"]
    deadline = time.time() + REINDEX_TIMEOUT
    final_job = None
    while time.time() < deadline:
        final_job = request_json("GET", f"/admin/jobs/{job_id}")
        if final_job.get("status") in {"completed", "failed"}:
            break
        time.sleep(POLL_INTERVAL)
    if final_job is None or final_job.get("status") not in {"completed", "failed"}:
        fail("reindex-wiki", f"timed out after {REINDEX_TIMEOUT}s", final_job)
    assert_true(
        "reindex-wiki-completed",
        final_job.get("status") == "completed",
        final_job,
        "wiki reindex completed successfully",
    )

    index_stats = request_json("GET", "/admin/index/stats")
    stats_map = source_stats_map(index_stats)
    assert_true(
        "index-stats-sources",
        "wiki" in stats_map and "cargo" in stats_map,
        index_stats,
        "index stats include wiki and cargo sources",
    )
    assert_true(
        "index-dimension",
        index_stats.get("embedding_dimensions") == EMBEDDING_DIMENSIONS,
        index_stats,
        "index stats match the configured embedding dimension",
    )
    wiki_stats = stats_map["wiki"]
    if EMBEDDING_MODEL:
        assert_true(
            "wiki-embeddings",
            wiki_stats.get("embedded_chunks") == wiki_stats.get("chunks"),
            index_stats,
            "all wiki chunks have embeddings when an embedding model is configured",
        )
    else:
        assert_true(
            "wiki-keyword-only",
            wiki_stats.get("embedded_chunks") == 0,
            index_stats,
            "wiki reindex stays keyword-only when no embedding model is configured",
        )

print(f"[ok] assistant validation completed with profile={PROFILE}")
REPORT["status"] = "ok"
emit_report()
PY
status=${PIPESTATUS[0]}
set -e

if [[ -n "${REPORT_FILE}" ]]; then
  report_json="$(grep '^__VALIDATION_REPORT_JSON__=' "${OUTPUT_CAPTURE_FILE}" | tail -n 1 | sed 's/^__VALIDATION_REPORT_JSON__=//')"
  if [[ -z "${report_json}" ]]; then
    echo "Validation report payload was not produced." >&2
    exit 1
  fi
  mkdir -p "$(dirname "${REPORT_FILE}")"
  REPORT_JSON="${report_json}" REPORT_PATH="${REPORT_FILE}" python - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

report = json.loads(os.environ["REPORT_JSON"])
path = Path(os.environ["REPORT_PATH"])
path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
  echo "[step] Validation report written to ${REPORT_FILE}"
fi

if [[ ${status} -ne 0 ]]; then
  exit "${status}"
fi
