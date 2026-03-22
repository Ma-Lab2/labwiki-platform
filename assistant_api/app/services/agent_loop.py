from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..clients.openalex import OpenAlexClient
from ..clients.tools import ToolClients
from ..clients.wiki import MediaWikiClient
from ..config import Settings
from ..constants import AssistantMode, SourceType, TaskType, ToolName
from ..providers.base import PromptEnvelope
from ..schemas import AttachmentItem, ChatRequest
from .attachments import build_attachment_evidence
from .drafts import prepare_draft_preview
from .intent import is_page_structuring_request, is_page_summary_request
from .llm import LLMClient
from .prompts import build_agent_planner_prompt
from .retrieval import RetrievalBroker
from .write_actions import commit_prepared_write, prepare_write_preview


@dataclass(frozen=True)
class AgentToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


def _append_step(steps: list[dict[str, str]], stage: str, title: str, status: str, detail: str) -> list[dict[str, str]]:
    return steps + [{
        "stage": stage,
        "title": title,
        "status": status,
        "detail": detail,
    }]


def _prefers_structured_only(question: str) -> bool:
    hints = [
        "结构化定义",
        "结构化条目",
        "只给出本组结构化定义",
        "只保留本组结构化定义",
        "只保留结构化定义",
        "只给定义",
    ]
    return any(hint in question for hint in hints)


def _source_priority(source_type: str, structured_only: bool) -> int:
    if structured_only:
        order = {
            SourceType.ATTACHMENT.value: 0,
            SourceType.CONTEXT.value: 0,
            SourceType.CARGO.value: 1,
            SourceType.WIKI.value: 2,
            SourceType.ZOTERO.value: 3,
            SourceType.OPENALEX.value: 4,
            SourceType.WEB.value: 5,
            SourceType.TOOL.value: 6,
        }
        return order.get(source_type, 99)
    order = {
        SourceType.ATTACHMENT.value: 0,
        SourceType.CONTEXT.value: 0,
        SourceType.CARGO.value: 1,
        SourceType.WIKI.value: 2,
        SourceType.ZOTERO.value: 3,
        SourceType.OPENALEX.value: 4,
        SourceType.WEB.value: 5,
        SourceType.TOOL.value: 6,
    }
    return order.get(source_type, 99)


def _dedupe_evidence(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {(item["source_type"], item["source_id"]) for item in existing}
    merged = existing[:]
    for item in incoming:
        key = (item["source_type"], item["source_id"])
        if key in seen:
            continue
        merged.append(item)
        seen.add(key)
    return merged


def _prioritize_evidence(evidence: list[dict[str, Any]], structured_only: bool) -> list[dict[str, Any]]:
    return sorted(
        evidence,
        key=lambda item: (
            _source_priority(item["source_type"], structured_only),
            -float(item.get("score", 0.0)),
        ),
    )


def _gaps_for_answer(task_type: str, evidence: list[dict[str, Any]], has_external: bool) -> list[str]:
    gaps: list[str] = []
    if len(evidence) < 2:
        gaps.append("命中证据过少，当前回答更像索引提示而不是完整结论。")
    if task_type == TaskType.COMPARE.value and len({item["title"] for item in evidence}) < 2:
        gaps.append("比较问题尚未形成至少两类独立来源的证据对照。")
    if task_type == TaskType.TOOL_WORKFLOW.value and not any(item["source_type"] in {SourceType.TOOL.value, SourceType.WIKI.value} for item in evidence):
        gaps.append("工具相关问题没有形成足够的工具结果或运行规则支撑。")
    if not has_external and task_type in {TaskType.COMPARE.value, TaskType.LITERATURE.value}:
        gaps.append("当前还没有扩展到文献外部来源。")
    return gaps


def _confidence_for_answer(evidence: list[dict[str, Any]], unresolved_gaps: list[str], external_hits: int) -> float:
    confidence = 0.28 + min(len({item["title"] for item in evidence}), 4) * 0.12 + min(external_hits, 2) * 0.07
    if any(item["source_type"] == SourceType.CARGO.value for item in evidence):
        confidence += 0.08
    if any(item["source_type"] in {SourceType.WIKI.value, SourceType.CONTEXT.value} for item in evidence):
        confidence += 0.10
    confidence -= min(len(unresolved_gaps), 3) * 0.08
    return max(0.08, min(confidence, 0.95))


def _serialize_sources(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "source_type": item["source_type"],
        "source_id": item["source_id"],
        "title": item["title"],
        "url": item.get("url"),
        "snippet": item.get("snippet"),
    } for item in evidence[:8]]


def _safe_json_load(raw: str) -> dict[str, Any]:
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = "\n".join(
            line for line in candidate.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    return json.loads(candidate)


class AgentExecutor:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        llm: LLMClient,
        wiki: MediaWikiClient,
        openalex: OpenAlexClient,
        tools: ToolClients,
    ) -> None:
        self.db = db
        self.settings = settings
        self.llm = llm
        self.wiki = wiki
        self.openalex = openalex
        self.tools = tools
        self.retrieval = RetrievalBroker(db, settings, llm, openalex)
        self.tool_specs = self._build_tool_specs()

    def _record_action(
        self,
        state: dict[str, Any],
        action: str,
        action_input: dict[str, Any],
        status: str,
        summary: str,
        output: dict[str, Any] | None = None,
    ) -> None:
        state["action_trace"].append({
            "action": action,
            "status": status,
            "summary": summary,
            "action_input": action_input,
            "output": output or {},
        })

    def _build_tool_specs(self) -> list[AgentToolSpec]:
        return [
            AgentToolSpec(
                name="search_local",
                description="检索本地 assistant 索引，返回 cargo/wiki/context/zotero 证据。",
                input_schema={"query": "string", "source_types": ["cargo", "wiki"], "limit": 6},
            ),
            AgentToolSpec(
                name="wiki_search",
                description="直接搜索 MediaWiki 页面标题和片段。",
                input_schema={"query": "string", "limit": 5},
            ),
            AgentToolSpec(
                name="wiki_read",
                description="读取指定 wiki 页正文，适合补充某个命中的关键页。",
                input_schema={"title": "string"},
            ),
            AgentToolSpec(
                name="openalex_search",
                description="检索外部学术文献线索。",
                input_schema={"query": "string", "limit": 4},
            ),
            AgentToolSpec(
                name="web_search",
                description="检索通用网页线索，仅在确实需要补外部信息时使用。",
                input_schema={"query": "string", "limit": 3},
            ),
            AgentToolSpec(
                name="tool_execute",
                description="调用实验室工具，只允许白名单动作，例如 tps/rcf health 或分析动作。",
                input_schema={"tool": "tps|rcf", "action": "string", "payload": {}},
            ),
            AgentToolSpec(
                name="prepare_draft_preview",
                description="基于当前回答和证据生成草稿预览，不提交。",
                input_schema={},
            ),
            AgentToolSpec(
                name="prepare_write_preview",
                description="基于当前请求生成结构化写入预览，不提交。",
                input_schema={},
            ),
            AgentToolSpec(
                name="commit_write",
                description="对白名单结构化页面或周日志白名单区块执行直接写入；只有字段完整时才允许使用。",
                input_schema={},
            ),
            AgentToolSpec(
                name="answer",
                description="结束工具循环并给出最终回答。",
                input_schema={"answer_strategy": "grounded|brief|compare|draft_oriented"},
            ),
        ]

    def execute(
        self,
        request: ChatRequest,
        *,
        conversation_history: list[dict[str, str]],
        task_type: str,
        planned_sources: list[str],
    ) -> dict[str, Any]:
        state: dict[str, Any] = {
            "session_id": request.session_id,
            "question": request.question,
            "mode": request.mode.value,
            "detail_level": request.detail_level.value,
            "task_type": task_type,
            "planned_sources": planned_sources,
            "context_pages": request.context_pages,
            "attachments": [item.model_dump() for item in request.attachments],
            "conversation_history": conversation_history,
            "steps": [],
            "evidence": [],
            "tool_calls": [],
            "action_trace": [],
            "external_hits": 0,
            "unresolved_gaps": [],
            "answer": "",
            "draft_preview_data": None,
            "write_preview_data": None,
            "write_result_data": None,
            "stop_reason": None,
        }
        state["structured_only"] = _prefers_structured_only(request.question)
        state["steps"] = _append_step(state["steps"], "intake", "理解问题", "complete", "已接收问题并进入 agent loop。")
        state["steps"] = _append_step(
            state["steps"],
            "plan",
            "初始化策略",
            "complete",
            f"任务类型 {task_type}；可用来源：{' / '.join(planned_sources)}。",
        )
        state = self._seed_context(state)

        for _ in range(self.settings.loop_max_steps):
            state["unresolved_gaps"] = _gaps_for_answer(
                state["task_type"],
                state["evidence"],
                has_external=bool(state["external_hits"]),
            )
            decision = self._choose_action(state)
            action_name = decision.get("action")
            action_input = decision.get("action_input") or {}
            if action_name == "answer":
                state["stop_reason"] = decision.get("stop_reason") or "agent_answered"
                break
            self._run_tool(state, action_name, action_input)
            if state.get("stop_reason"):
                break

        state["unresolved_gaps"] = _gaps_for_answer(
            state["task_type"],
            state["evidence"],
            has_external=bool(state["external_hits"]),
        )
        return state

    def stream_answer(self, state: dict[str, Any]) -> Any:
        yield {
            "event": "step",
            "data": {
                "stage": "synthesize",
                "title": "生成回答",
                "status": "running",
                "detail": "agent loop 已完成，正在流式生成最终回答。",
            },
        }
        chunks: list[str] = []
        for chunk in self.llm.answer_stream(
            question=state["question"],
            task_type=state["task_type"],
            detail_level=state["detail_level"],
            mode=state["mode"],
            current_page=state["context_pages"][0] if state["context_pages"] else None,
            evidence=state["evidence"],
            unresolved_gaps=state["unresolved_gaps"],
            conversation_history=state.get("conversation_history", []),
        ):
            chunks.append(chunk)
            yield {"event": "token", "data": {"delta": chunk}}
        state["answer"] = "".join(chunks).strip()
        state["steps"] = _append_step(state["steps"], "synthesize", "生成回答", "complete", "回答已生成。")
        yield {"event": "step", "data": state["steps"][-1]}

    def finalize(self, state: dict[str, Any], request: ChatRequest) -> dict[str, Any]:
        if request.mode == AssistantMode.DRAFT and not state.get("draft_preview_data"):
            prepared = prepare_draft_preview(
                self.settings,
                self.llm,
                question=state["question"],
                answer=state["answer"],
                source_titles=[item["title"] for item in state["evidence"][:6]],
                conversation_history=state.get("conversation_history", []),
            )
            state["draft_preview_data"] = prepared
            state["steps"] = _append_step(
                state["steps"],
                "draft_preview",
                "生成草稿预览",
                "complete",
                f"已生成预览：{prepared['target_page']}。",
            )

        if state["task_type"] == TaskType.WRITE_ACTION.value and not state.get("write_preview_data"):
            prepared = prepare_write_preview(
                self.settings,
                self.llm,
                self.wiki,
                question=state["question"],
                answer=state["answer"],
                source_titles=[item["title"] for item in state["evidence"][:6]],
                current_page=request.context_pages[0] if request.context_pages else None,
                conversation_history=state.get("conversation_history", []),
            )
            metadata = prepared["metadata_json"]
            state["write_preview_data"] = {
                "action_type": metadata.get("action_type"),
                "operation": metadata.get("operation"),
                "target_page": prepared["target_page"],
                "preview_text": prepared["preview_text"],
                "structured_payload": metadata.get("structured_payload") or {},
                "metadata_json": metadata,
            }
            state["steps"] = _append_step(
                state["steps"],
                "write_preview",
                "生成写入预览",
                "complete",
                f"已生成 {prepared['target_page']} 的写入预览。",
            )
        elif state["task_type"] == TaskType.WRITE_ACTION.value and state.get("write_result_data"):
            state["steps"] = _append_step(
                state["steps"],
                "write_commit",
                "完成白名单直写",
                "complete",
                f"已写入 {state['write_result_data'].get('page_title', '目标页')}。",
            )

        confidence = _confidence_for_answer(state["evidence"], state["unresolved_gaps"], state["external_hits"])
        state["confidence"] = confidence
        state["suggested_followups"] = [
            "请继续补充某个具体页面后再判断。",
            "请把当前结论整理成条目或草稿。",
            "请只保留站内结构化证据再回答一次。",
        ]
        stop_reason = state.get("stop_reason") or "answer_ready"
        state["stop_reason"] = stop_reason
        state["steps"] = _append_step(
            state["steps"],
            "finalize",
            "完成本轮循环",
            "complete",
            f"置信度 {confidence:.2f}；停止原因：{stop_reason}。",
        )
        return state

    def _seed_context(self, state: dict[str, Any]) -> dict[str, Any]:
        loaded = 0
        attachments = state.get("attachments") or []
        if attachments:
            state["evidence"] = _dedupe_evidence(
                state["evidence"],
                build_attachment_evidence([AttachmentItem(**item) for item in attachments]),
            )
            state["steps"] = _append_step(
                state["steps"],
                "attachment",
                "纳入附件上下文",
                "complete",
                f"已附加 {len(attachments)} 个文件，当前仅纳入元信息。",
            )
        for title in state["context_pages"]:
            text = self.wiki.get_page_text(title)
            if not text:
                continue
            state["evidence"] = _dedupe_evidence(state["evidence"], [{
                "source_type": SourceType.CONTEXT.value,
                "source_id": title,
                "title": title,
                "url": self.wiki.page_url(title),
                "snippet": " ".join(text.split())[:280],
                "content": text,
                "score": 2.0,
            }])
            loaded += 1
        if loaded:
            state["steps"] = _append_step(
                state["steps"],
                "context",
                "载入上下文页面",
                "complete",
                f"已纳入 {loaded} 个显式上下文页面。",
            )
        return state

    def _choose_action(self, state: dict[str, Any]) -> dict[str, Any]:
        if state["task_type"] == TaskType.WRITE_ACTION.value:
            return self._fallback_action(state)
        if not self.llm.generation_provider.enabled:
            return self._fallback_action(state)
        prompt = build_agent_planner_prompt(
            question=state["question"],
            task_type=state["task_type"],
            detail_level=state["detail_level"],
            mode=state["mode"],
            current_page=state["context_pages"][0] if state["context_pages"] else None,
            conversation_history=state.get("conversation_history", []),
            steps=state["steps"],
            evidence=state["evidence"],
            unresolved_gaps=state["unresolved_gaps"],
            tool_specs=self.tool_specs,
        )
        try:
            raw = self.llm.generate_prompt(prompt)
            decision = _safe_json_load(raw)
            action = str(decision.get("action") or "").strip()
            if action not in {spec.name for spec in self.tool_specs}:
                raise ValueError(f"Unknown action: {action}")
            if action in {"prepare_write_preview", "commit_write"} and state["task_type"] != TaskType.WRITE_ACTION.value:
                return self._fallback_action(state)
            if action == "prepare_draft_preview" and state["task_type"] != TaskType.DRAFT.value:
                return self._fallback_action(state)
            return {
                "thought": str(decision.get("thought") or "").strip(),
                "action": action,
                "action_input": decision.get("action_input") or {},
                "stop_reason": decision.get("stop_reason"),
            }
        except Exception:
            return self._fallback_action(state)

    def _fallback_action(self, state: dict[str, Any]) -> dict[str, Any]:
        evidence = state["evidence"]
        task_type = state["task_type"]
        external_hits = state["external_hits"]
        current_page = state["context_pages"][0] if state["context_pages"] else None
        has_context_evidence = any(item["source_type"] == SourceType.CONTEXT.value for item in evidence)
        page_focused = is_page_structuring_request(state["question"], current_page) or is_page_summary_request(state["question"], current_page)
        if task_type == TaskType.WRITE_ACTION.value:
            preview = state.get("write_preview_data")
            if not preview:
                return {"action": "prepare_write_preview", "action_input": {}}
            if preview.get("metadata_json", {}).get("missing_fields"):
                return {"action": "answer", "action_input": {"answer_strategy": "grounded"}, "stop_reason": "write_preview_missing_fields"}
            if not state.get("write_result_data"):
                return {"action": "commit_write", "action_input": {}}
            return {"action": "answer", "action_input": {"answer_strategy": "grounded"}, "stop_reason": "write_committed"}
        if task_type == TaskType.DRAFT.value and has_context_evidence and page_focused and not state.get("answer"):
            return {"action": "answer", "action_input": {"answer_strategy": "grounded"}, "stop_reason": "current_page_draft_ready"}
        if task_type == TaskType.DRAFT.value and not state.get("draft_preview_data") and state.get("answer"):
            return {"action": "prepare_draft_preview", "action_input": {}, "stop_reason": "draft_preview_requested"}
        if has_context_evidence and page_focused and not state.get("answer"):
            return {"action": "answer", "action_input": {"answer_strategy": "grounded"}, "stop_reason": "current_page_grounded"}
        if len(evidence) < 3:
            source_types = [SourceType.CARGO.value] if state["structured_only"] else [SourceType.CARGO.value, SourceType.WIKI.value]
            if self.settings.enable_zotero and task_type in {TaskType.COMPARE.value, TaskType.LITERATURE.value}:
                source_types.append(SourceType.ZOTERO.value)
            return {"action": "search_local", "action_input": {"query": state["question"], "source_types": source_types, "limit": 6}}
        if task_type == TaskType.TOOL_WORKFLOW.value and not any(item["source_type"] == SourceType.TOOL.value for item in evidence):
            return {"action": "tool_execute", "action_input": {"tool": "tps", "action": "health", "payload": {}}}
        if task_type in {TaskType.COMPARE.value, TaskType.LITERATURE.value} and external_hits < self.settings.loop_max_external:
            return {"action": "openalex_search", "action_input": {"query": state["question"], "limit": 4}}
        if self.settings.enable_web_search and not external_hits and task_type in {TaskType.COMPARE.value, TaskType.LITERATURE.value}:
            return {"action": "web_search", "action_input": {"query": state["question"], "limit": 3}}
        return {"action": "answer", "action_input": {"answer_strategy": "grounded"}, "stop_reason": "fallback_answer"}

    def _run_tool(self, state: dict[str, Any], action_name: str, action_input: dict[str, Any]) -> None:
        if action_name == "search_local":
            self._tool_search_local(state, action_input)
            return
        if action_name == "wiki_search":
            self._tool_wiki_search(state, action_input)
            return
        if action_name == "wiki_read":
            self._tool_wiki_read(state, action_input)
            return
        if action_name == "openalex_search":
            self._tool_openalex_search(state, action_input)
            return
        if action_name == "web_search":
            self._tool_web_search(state, action_input)
            return
        if action_name == "tool_execute":
            self._tool_execute(state, action_input)
            return
        if action_name == "prepare_draft_preview":
            self._tool_prepare_draft_preview(state)
            state["stop_reason"] = "draft_preview_requested"
            return
        if action_name == "prepare_write_preview":
            self._tool_prepare_write_preview(state)
            return
        if action_name == "commit_write":
            self._tool_commit_write(state)
            state["stop_reason"] = "write_committed"
            return
        if action_name == "answer":
            self._record_action(state, "answer", action_input, "complete", "已停止工具循环，进入最终回答。")
            state["stop_reason"] = "agent_answered"
            return
        raise ValueError(f"Unsupported agent action: {action_name}")

    def _tool_search_local(self, state: dict[str, Any], action_input: dict[str, Any]) -> None:
        query = str(action_input.get("query") or state["question"]).strip()
        source_types = action_input.get("source_types") or state["planned_sources"]
        allowed = {SourceType.CARGO.value, SourceType.WIKI.value, SourceType.CONTEXT.value, SourceType.ZOTERO.value}
        source_types = [value for value in source_types if value in allowed]
        hits = self.retrieval.search_local(
            query,
            source_types=source_types,
            limit=int(action_input.get("limit") or 6),
        )
        state["evidence"] = _prioritize_evidence(_dedupe_evidence(state["evidence"], hits), state["structured_only"])
        self._record_action(
            state,
            "search_local",
            action_input,
            "complete",
            f"命中 {len(hits)} 条站内证据。",
            {"hits": len(hits), "source_types": source_types},
        )
        state["steps"] = _append_step(
            state["steps"],
            "agent_tool",
            "执行本地检索",
            "complete",
            f"命中 {len(hits)} 条站内证据。",
        )

    def _tool_wiki_search(self, state: dict[str, Any], action_input: dict[str, Any]) -> None:
        query = str(action_input.get("query") or state["question"]).strip()
        results = self.wiki.search_pages(query, limit=int(action_input.get("limit") or 5))
        hits = []
        for item in results:
            hits.append({
                "source_type": SourceType.WIKI.value,
                "source_id": item.title,
                "title": item.title,
                "url": self.wiki.page_url(item.title),
                "snippet": item.snippet,
                "content": "",
                "score": 1.0,
            })
        state["evidence"] = _prioritize_evidence(_dedupe_evidence(state["evidence"], hits), state["structured_only"])
        self._record_action(
            state,
            "wiki_search",
            action_input,
            "complete",
            f"命中 {len(hits)} 个页面候选。",
            {"hits": len(hits)},
        )
        state["steps"] = _append_step(
            state["steps"],
            "agent_tool",
            "搜索 Wiki 页面",
            "complete",
            f"命中 {len(hits)} 个页面候选。",
        )

    def _tool_wiki_read(self, state: dict[str, Any], action_input: dict[str, Any]) -> None:
        title = str(action_input.get("title") or "").strip()
        if not title:
            self._record_action(state, "wiki_read", action_input, "error", "缺少 title。")
            state["steps"] = _append_step(state["steps"], "agent_tool", "读取 Wiki 页面", "error", "缺少 title。")
            return
        text = self.wiki.get_page_text(title)
        if not text:
            self._record_action(state, "wiki_read", action_input, "error", f"{title} 无正文。")
            state["steps"] = _append_step(state["steps"], "agent_tool", "读取 Wiki 页面", "error", f"{title} 无正文。")
            return
        hit = {
            "source_type": SourceType.WIKI.value,
            "source_id": title,
            "title": title,
            "url": self.wiki.page_url(title),
            "snippet": " ".join(text.split())[:280],
            "content": text,
            "score": 1.5,
        }
        state["evidence"] = _prioritize_evidence(_dedupe_evidence(state["evidence"], [hit]), state["structured_only"])
        self._record_action(
            state,
            "wiki_read",
            action_input,
            "complete",
            f"已读取 {title}。",
            {"title": title},
        )
        state["steps"] = _append_step(
            state["steps"],
            "agent_tool",
            "读取 Wiki 页面",
            "complete",
            f"已读取 {title}。",
        )

    def _tool_openalex_search(self, state: dict[str, Any], action_input: dict[str, Any]) -> None:
        query = str(action_input.get("query") or state["question"]).strip()
        hits = self.retrieval.search_openalex(query, limit=int(action_input.get("limit") or 4))
        state["evidence"] = _prioritize_evidence(_dedupe_evidence(state["evidence"], hits), state["structured_only"])
        state["external_hits"] += len(hits)
        self._record_action(
            state,
            "openalex_search",
            action_input,
            "complete",
            f"新增 {len(hits)} 条 OpenAlex 线索。",
            {"hits": len(hits)},
        )
        state["steps"] = _append_step(
            state["steps"],
            "agent_tool",
            "检索学术外部来源",
            "complete",
            f"新增 {len(hits)} 条 OpenAlex 线索。",
        )

    def _tool_web_search(self, state: dict[str, Any], action_input: dict[str, Any]) -> None:
        if not self.settings.enable_web_search:
            self._record_action(state, "web_search", action_input, "error", "网页搜索未启用。")
            state["steps"] = _append_step(state["steps"], "agent_tool", "网页搜索", "error", "网页搜索未启用。")
            return
        query = str(action_input.get("query") or state["question"]).strip()
        hits = self.retrieval.search_web(query, limit=int(action_input.get("limit") or 3))
        state["evidence"] = _prioritize_evidence(_dedupe_evidence(state["evidence"], hits), state["structured_only"])
        state["external_hits"] += len(hits)
        self._record_action(
            state,
            "web_search",
            action_input,
            "complete",
            f"新增 {len(hits)} 条网页线索。",
            {"hits": len(hits)},
        )
        state["steps"] = _append_step(
            state["steps"],
            "agent_tool",
            "检索网页线索",
            "complete",
            f"新增 {len(hits)} 条网页线索。",
        )

    def _tool_execute(self, state: dict[str, Any], action_input: dict[str, Any]) -> None:
        tool_name = str(action_input.get("tool") or "").strip().lower()
        action = str(action_input.get("action") or "health").strip()
        payload = action_input.get("payload") or {}
        if tool_name == ToolName.TPS.value:
            result = self.tools.tps_execute(action, payload)
        elif tool_name == ToolName.RCF.value:
            result = self.tools.rcf_execute(action, payload)
        else:
            raise ValueError(f"Unsupported tool: {tool_name}")
        state["tool_calls"].append({"tool": tool_name, "action": action, "status": "ok"})
        self._record_action(
            state,
            "tool_execute",
            action_input,
            "complete",
            f"{tool_name}.{action} 执行完成。",
            {"tool": tool_name, "action": action},
        )
        hit = {
            "source_type": SourceType.TOOL.value,
            "source_id": f"{tool_name}:{action}",
            "title": f"{tool_name.upper()} {action}",
            "url": None,
            "snippet": json.dumps(result, ensure_ascii=False)[:280],
            "content": json.dumps(result, ensure_ascii=False, indent=2),
            "score": 1.1,
        }
        state["evidence"] = _prioritize_evidence(_dedupe_evidence(state["evidence"], [hit]), state["structured_only"])
        state["steps"] = _append_step(
            state["steps"],
            "agent_tool",
            "调用实验工具",
            "complete",
            f"{tool_name}.{action} 执行完成。",
        )

    def _tool_prepare_draft_preview(self, state: dict[str, Any]) -> None:
        prepared = prepare_draft_preview(
            self.settings,
            self.llm,
            question=state["question"],
            answer=state["answer"] or self.llm.answer_from_evidence(
                question=state["question"],
                task_type=state["task_type"],
                detail_level=state["detail_level"],
                mode=state["mode"],
                current_page=state["context_pages"][0] if state["context_pages"] else None,
                evidence=state["evidence"],
                unresolved_gaps=state["unresolved_gaps"],
                conversation_history=state.get("conversation_history", []),
            ),
            source_titles=[item["title"] for item in state["evidence"][:6]],
            conversation_history=state.get("conversation_history", []),
        )
        state["draft_preview_data"] = prepared
        self._record_action(
            state,
            "prepare_draft_preview",
            {},
            "complete",
            f"已生成草稿预览：{prepared['target_page']}。",
            {"target_page": prepared["target_page"]},
        )
        state["steps"] = _append_step(
            state["steps"],
            "agent_tool",
            "准备草稿预览",
            "complete",
            f"已生成草稿预览：{prepared['target_page']}。",
        )

    def _tool_prepare_write_preview(self, state: dict[str, Any]) -> None:
        try:
            prepared = prepare_write_preview(
                self.settings,
                self.llm,
                self.wiki,
                question=state["question"],
                answer=state["answer"] or self.llm.answer_from_evidence(
                    question=state["question"],
                    task_type=state["task_type"],
                    detail_level=state["detail_level"],
                    mode=state["mode"],
                    current_page=state["context_pages"][0] if state["context_pages"] else None,
                    evidence=state["evidence"],
                    unresolved_gaps=state["unresolved_gaps"],
                    conversation_history=state.get("conversation_history", []),
                ),
                source_titles=[item["title"] for item in state["evidence"][:6]],
                current_page=state["context_pages"][0] if state["context_pages"] else None,
                conversation_history=state.get("conversation_history", []),
            )
        except Exception as error:
            self._record_action(
                state,
                "prepare_write_preview",
                {},
                "error",
                str(error),
                {"detail": str(error)},
            )
            state["steps"] = _append_step(
                state["steps"],
                "agent_tool",
                "准备写入预览",
                "error",
                str(error),
            )
            return
        metadata = prepared["metadata_json"]
        state["write_preview_data"] = {
            "action_type": metadata.get("action_type"),
            "operation": metadata.get("operation"),
            "target_page": prepared["target_page"],
            "preview_text": prepared["preview_text"],
            "structured_payload": metadata.get("structured_payload") or {},
            "metadata_json": metadata,
        }
        self._record_action(
            state,
            "prepare_write_preview",
            {},
            "complete",
            f"已生成写入预览：{prepared['target_page']}。",
            {
                "target_page": prepared["target_page"],
                "missing_fields": metadata.get("missing_fields", []),
            },
        )
        state["steps"] = _append_step(
            state["steps"],
            "agent_tool",
            "准备写入预览",
            "complete",
            f"已生成写入预览：{prepared['target_page']}。",
        )

    def _tool_commit_write(self, state: dict[str, Any]) -> None:
        prepared = state.get("write_preview_data")
        if not prepared:
            self._record_action(state, "commit_write", {}, "error", "未找到写入预览。")
            state["steps"] = _append_step(state["steps"], "agent_tool", "执行白名单直写", "error", "未找到写入预览。")
            return
        metadata = prepared.get("metadata_json") or {}
        try:
            result = commit_prepared_write(
                self.db,
                self.wiki,
                target_page=prepared["target_page"],
                metadata=metadata,
                session_id=state.get("session_id"),
            )
            state["write_result_data"] = result
            self._record_action(
                state,
                "commit_write",
                {},
                "complete",
                f"已写入 {result['page_title']}。",
                result,
            )
            state["steps"] = _append_step(
                state["steps"],
                "agent_tool",
                "执行白名单直写",
                "complete",
                f"已写入 {result['page_title']}。",
            )
        except Exception as error:
            self._record_action(
                state,
                "commit_write",
                {},
                "error",
                str(error),
                {"detail": str(error)},
            )
            state["steps"] = _append_step(
                state["steps"],
                "agent_tool",
                "执行白名单直写",
                "error",
                str(error),
            )
