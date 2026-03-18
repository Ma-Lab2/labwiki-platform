from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from ..clients.openalex import OpenAlexClient
from ..clients.tools import ToolClients
from ..clients.wiki import MediaWikiClient
from ..config import Settings
from ..constants import AssistantMode, SourceType, TaskType
from ..models import AssistantSession, AssistantTurn
from ..schemas import ChatRequest, ChatResponse, DraftPreviewPayload, PlanResponse, SourceItem, StepItem
from .audit import log_audit
from .drafts import prepare_draft_preview, save_draft_preview
from .llm import LLMClient
from .search import search_chunks


class WorkflowState(TypedDict, total=False):
    session_id: str
    turn_id: str
    user_name: str | None
    question: str
    mode: str
    detail_level: str
    context_pages: list[str]
    task_type: str
    planned_sources: list[str]
    needs_external_search: bool
    should_generate_draft_preview: bool
    steps: list[dict[str, str]]
    evidence: list[dict[str, Any]]
    external_attempts: int
    external_hits: int
    tool_calls: list[dict[str, Any]]
    unresolved_gaps: list[str]
    confidence: float
    answer: str
    suggested_followups: list[str]
    draft_preview_data: dict[str, Any] | None
    pending_write_action: dict[str, Any] | None
    stop_reason: str | None
    structured_only: bool


def _append_step(steps: list[dict[str, str]], stage: str, title: str, status: str, detail: str) -> list[dict[str, str]]:
    return steps + [{
        "stage": stage,
        "title": title,
        "status": status,
        "detail": detail,
    }]


def classify_question(question: str, mode: AssistantMode | str) -> TaskType:
    mode_value = mode.value if isinstance(mode, AssistantMode) else str(mode)
    lowered = question.lower()
    if mode_value == AssistantMode.DRAFT.value or any(token in question for token in ["草稿", "整理成条目", "生成条目", "生成模板"]):
        return TaskType.DRAFT
    if any(token in question for token in ["对照", "比较", "区别", "差异", "一致点", "不同点"]):
        return TaskType.COMPARE
    if any(token in lowered for token in ["paper", "zotero", "doi"]) or any(token in question for token in ["论文", "文献", "参考文献"]):
        return TaskType.LITERATURE
    if any(token in question for token in ["学习路径", "从哪开始", "新人", "入门"]):
        return TaskType.LEARNING_PATH
    if any(token in lowered for token in ["tps", "rcf"]) or any(token in question for token in ["解谱", "能谱", "堆栈"]):
        return TaskType.TOOL_WORKFLOW
    return TaskType.CONCEPT


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


def _extract_compare_targets(question: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", question.strip())
    patterns = [
        r"比较\s*([A-Za-z0-9_\-+/\.一-龥]+)\s*(?:和|与|及|跟|vs\.?|VS\.?|versus)\s*([A-Za-z0-9_\-+/\.一-龥]+)",
        r"对照\s*([A-Za-z0-9_\-+/\.一-龥]+)\s*(?:和|与|及|跟|vs\.?|VS\.?|versus)\s*([A-Za-z0-9_\-+/\.一-龥]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return [part.strip(" ，,。；;：:()（）") for part in match.groups() if part.strip()]
    return []


def _match_compare_targets(item: dict[str, Any], targets: list[str]) -> tuple[int, int]:
    haystack = f"{item.get('title', '')} {item.get('snippet', '')} {item.get('content', '')}".lower()
    matched = 0
    exact_title = 0
    title_lower = item.get("title", "").lower()
    for target in targets:
        target_lower = target.lower()
        if target_lower in haystack:
            matched += 1
        if target_lower in title_lower:
            exact_title += 1
    return matched, exact_title


def _source_priority(source_type: str, structured_only: bool) -> int:
    if structured_only:
        order = {
            SourceType.CARGO.value: 0,
            SourceType.CONTEXT.value: 1,
            SourceType.WIKI.value: 2,
            SourceType.ZOTERO.value: 3,
            SourceType.OPENALEX.value: 4,
            SourceType.TOOL.value: 5,
        }
        return order.get(source_type, 99)
    order = {
        SourceType.CONTEXT.value: 0,
        SourceType.CARGO.value: 1,
        SourceType.WIKI.value: 2,
        SourceType.ZOTERO.value: 3,
        SourceType.OPENALEX.value: 4,
        SourceType.TOOL.value: 5,
    }
    return order.get(source_type, 99)


def _prioritize_evidence(evidence: list[dict[str, Any]], structured_only: bool) -> list[dict[str, Any]]:
    return sorted(
        evidence,
        key=lambda item: (
            _source_priority(item["source_type"], structured_only),
            -float(item.get("score", 0.0)),
        ),
    )


def _focus_compare_evidence(evidence: list[dict[str, Any]], targets: list[str]) -> list[dict[str, Any]]:
    if len(targets) < 2:
        return evidence

    ranked: list[tuple[int, int, float, dict[str, Any]]] = []
    for item in evidence:
        matched, exact_title = _match_compare_targets(item, targets)
        ranked.append((matched, exact_title, float(item.get("score", 0.0)), item))

    matching = [item for matched, _, _, item in ranked if matched > 0]
    if len(matching) < 2:
        return evidence

    coverage: list[dict[str, Any]] = []
    used_keys: set[tuple[str, str]] = set()
    for target in targets:
        best_item: dict[str, Any] | None = None
        best_key: tuple[int, int, float] | None = None
        target_lower = target.lower()
        for matched, exact_title, score, item in ranked:
            key = (item["source_type"], item["source_id"])
            if key in used_keys:
                continue
            haystack = f"{item.get('title', '')} {item.get('snippet', '')} {item.get('content', '')}".lower()
            if target_lower not in haystack:
                continue
            current_key = (exact_title, matched, score)
            if best_key is None or current_key > best_key:
                best_item = item
                best_key = current_key
        if best_item is not None:
            used_keys.add((best_item["source_type"], best_item["source_id"]))
            coverage.append(best_item)

    remaining = [
        item
        for matched, exact_title, score, item in sorted(
            ranked,
            key=lambda row: (row[0], row[1], row[2]),
            reverse=True,
        )
        if matched > 0 and (item["source_type"], item["source_id"]) not in used_keys
    ]
    return coverage + remaining


def plan_sources(task_type: TaskType, context_pages: list[str], structured_only: bool) -> tuple[list[str], bool]:
    if structured_only:
        sources = [SourceType.CARGO.value]
        needs_external = task_type in {TaskType.COMPARE, TaskType.LITERATURE}
        if needs_external:
            sources.append(SourceType.ZOTERO.value)
        return sources, needs_external
    sources = [SourceType.CARGO.value, SourceType.WIKI.value]
    if context_pages:
        sources.insert(0, SourceType.CONTEXT.value)
    needs_external = False
    if task_type in {TaskType.COMPARE, TaskType.LITERATURE}:
        sources.append(SourceType.ZOTERO.value)
        needs_external = True
    if task_type == TaskType.TOOL_WORKFLOW:
        sources.append(SourceType.TOOL.value)
    return list(dict.fromkeys(sources)), needs_external


def _session_for_request(db: Session, request: ChatRequest) -> AssistantSession:
    if request.session_id:
        record = db.get(AssistantSession, request.session_id)
        if record:
            return record
    record = AssistantSession(
        user_name=request.user_name,
        current_page=request.context_pages[0] if request.context_pages else None,
    )
    db.add(record)
    db.flush()
    return record


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


class AssistantWorkflow:
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
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(WorkflowState)
        graph.add_node("intake", self.intake)
        graph.add_node("classify", self.classify)
        graph.add_node("plan", self.plan)
        graph.add_node("retrieve_local", self.retrieve_local)
        graph.add_node("retrieve_tools", self.retrieve_tools)
        graph.add_node("retrieve_external", self.retrieve_external)
        graph.add_node("synthesize", self.synthesize)
        graph.add_node("verify", self.verify)
        graph.add_node("draft_preview", self.draft_preview)
        graph.add_node("commit_gate", self.commit_gate)
        graph.add_node("finalize", self.finalize)

        graph.add_edge(START, "intake")
        graph.add_edge("intake", "classify")
        graph.add_edge("classify", "plan")
        graph.add_edge("plan", "retrieve_local")
        graph.add_conditional_edges(
            "retrieve_local",
            self.route_after_local,
            {
                "retrieve_tools": "retrieve_tools",
                "retrieve_external": "retrieve_external",
                "synthesize": "synthesize",
            },
        )
        graph.add_conditional_edges(
            "retrieve_tools",
            self.route_after_tools,
            {
                "retrieve_external": "retrieve_external",
                "synthesize": "synthesize",
            },
        )
        graph.add_conditional_edges(
            "retrieve_external",
            self.route_after_external,
            {
                "retrieve_external": "retrieve_external",
                "synthesize": "synthesize",
            },
        )
        graph.add_edge("synthesize", "verify")
        graph.add_conditional_edges(
            "verify",
            self.route_after_verify,
            {
                "draft_preview": "draft_preview",
                "finalize": "finalize",
            },
        )
        graph.add_edge("draft_preview", "commit_gate")
        graph.add_edge("commit_gate", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    def run(self, request: ChatRequest) -> WorkflowState:
        initial_state: WorkflowState = {
            "question": request.question,
            "mode": request.mode.value,
            "detail_level": request.detail_level.value,
            "context_pages": request.context_pages,
            "user_name": request.user_name,
            "steps": [],
            "evidence": [],
            "external_attempts": 0,
            "external_hits": 0,
            "tool_calls": [],
            "unresolved_gaps": [],
            "confidence": 0.0,
            "answer": "",
            "suggested_followups": [],
            "draft_preview_data": None,
            "pending_write_action": None,
            "stop_reason": None,
        }
        return self.graph.invoke(initial_state)

    def intake(self, state: WorkflowState) -> WorkflowState:
        return {
            "steps": _append_step(
                state["steps"],
                "intake",
                "理解问题",
                "complete",
                "已接收问题、当前页面和解释层级。",
            )
        }

    def classify(self, state: WorkflowState) -> WorkflowState:
        task_type = classify_question(state["question"], state["mode"])
        return {
            "task_type": task_type.value,
            "steps": _append_step(
                state["steps"],
                "classify",
                "判定任务类型",
                "complete",
                f"任务被识别为 {task_type.value}。",
            ),
        }

    def plan(self, state: WorkflowState) -> WorkflowState:
        task_type = TaskType(state["task_type"])
        structured_only = _prefers_structured_only(state["question"])
        planned_sources, needs_external = plan_sources(task_type, state["context_pages"], structured_only)
        return {
            "planned_sources": planned_sources,
            "needs_external_search": needs_external,
            "structured_only": structured_only,
            "should_generate_draft_preview": state["mode"] == AssistantMode.DRAFT.value or task_type == TaskType.DRAFT,
            "steps": _append_step(
                state["steps"],
                "plan",
                "规划检索路径",
                "complete",
                f"优先检索：{' / '.join(planned_sources)}。",
            ),
        }

    def retrieve_local(self, state: WorkflowState) -> WorkflowState:
        evidence = state["evidence"][:]
        structured_only = bool(state.get("structured_only"))
        compare_targets = _extract_compare_targets(state["question"]) if state["task_type"] == TaskType.COMPARE.value else []
        loaded_context = 0
        if not structured_only:
            for title in state["context_pages"]:
                text = self.wiki.get_page_text(title)
                if not text:
                    continue
                evidence = _dedupe_evidence(evidence, [{
                    "source_type": SourceType.CONTEXT.value,
                    "source_id": title,
                    "title": title,
                    "url": self.wiki.page_url(title),
                    "snippet": " ".join(text.split())[:280],
                    "content": text,
                }])
                loaded_context += 1

        indexed_source_types = [SourceType.CARGO.value] if structured_only else [SourceType.CARGO.value, SourceType.WIKI.value]
        if TaskType(state["task_type"]) in {TaskType.COMPARE, TaskType.LITERATURE}:
            indexed_source_types.append(SourceType.ZOTERO.value)
        indexed_hits = search_chunks(self.db, state["question"], source_types=indexed_source_types, limit=8)
        evidence = _dedupe_evidence(evidence, indexed_hits)

        if len(evidence) < 4 and not structured_only:
            live_hits = self.wiki.search_pages(state["question"], limit=6)
            live_evidence = []
            for item in live_hits:
                text = self.wiki.get_page_text(item.title)
                live_evidence.append({
                    "source_type": SourceType.WIKI.value,
                    "source_id": item.title,
                    "title": item.title,
                    "url": self.wiki.page_url(item.title),
                    "snippet": re.sub(r"<.*?>", "", item.snippet or "")[:280],
                    "content": text[:1600],
                })
            evidence = _dedupe_evidence(evidence, live_evidence)

        evidence = _prioritize_evidence(evidence, structured_only)
        if compare_targets:
            evidence = _focus_compare_evidence(evidence, compare_targets)
        unresolved_gaps = _gaps_for_answer(state["task_type"], evidence, has_external=False)
        detail = f"命中 {len(evidence)} 条本地证据。"
        if loaded_context:
            detail = f"已纳入 {loaded_context} 个上下文页面；" + detail
        if structured_only:
            detail += " 已按结构化定义优先排序。"
        if compare_targets:
            detail += f" 已锁定比较目标：{' / '.join(compare_targets)}。"
        return {
            "evidence": evidence,
            "unresolved_gaps": unresolved_gaps,
            "steps": _append_step(
                state["steps"],
                "retrieve",
                "检索站内知识",
                "complete",
                detail,
            ),
        }

    def retrieve_tools(self, state: WorkflowState) -> WorkflowState:
        tool_notes: list[str] = []
        tool_calls = state["tool_calls"][:]
        for tool_name, action in [("TPS", "health"), ("RCF", "health")]:
            try:
                if tool_name == "TPS":
                    result = self.tools.tps_execute(action, {})
                else:
                    result = self.tools.rcf_execute(action, {})
                tool_notes.append(f"{tool_name}={result.get('status', 'ok')}")
                tool_calls.append({"tool": tool_name.lower(), "action": action, "status": "ok"})
            except Exception as error:
                tool_notes.append(f"{tool_name}=unavailable ({error})")
                tool_calls.append({"tool": tool_name.lower(), "action": action, "status": "error", "detail": str(error)})

        evidence = _dedupe_evidence(state["evidence"], [{
            "source_type": SourceType.TOOL.value,
            "source_id": "tool-health",
            "title": "分析工具状态",
            "url": None,
            "snippet": "；".join(tool_notes),
            "content": "\n".join(tool_notes),
        }])
        unresolved_gaps = _gaps_for_answer(state["task_type"], evidence, has_external=bool(state["external_hits"]))
        return {
            "evidence": evidence,
            "tool_calls": tool_calls,
            "unresolved_gaps": unresolved_gaps,
            "steps": _append_step(
                state["steps"],
                "tool",
                "读取工具状态",
                "complete",
                "；".join(tool_notes),
            ),
        }

    def retrieve_external(self, state: WorkflowState) -> WorkflowState:
        external_attempts = state["external_attempts"] + 1
        external_hits_list: list[dict[str, Any]] = []
        detail = "当前未启用外部学术检索。"
        if self.settings.enable_web_search:
            try:
                external_hits_list = self.openalex.search(state["question"], limit=4)
                detail = f"新增 {len(external_hits_list)} 条外部线索。"
            except Exception as error:
                external_hits_list = [{
                    "source_type": SourceType.OPENALEX.value,
                    "source_id": "search-error",
                    "title": "外部搜索失败",
                    "url": None,
                    "snippet": str(error),
                    "content": str(error),
                }]
                detail = f"外部检索失败：{error}"

        evidence = _dedupe_evidence(state["evidence"], external_hits_list)
        added = len(evidence) - len(state["evidence"])
        external_hits = state["external_hits"] + max(0, added)
        unresolved_gaps = _gaps_for_answer(state["task_type"], evidence, has_external=bool(external_hits))
        stop_reason = state.get("stop_reason")
        if added == 0:
            stop_reason = "external_no_new_evidence"
        elif external_attempts >= self.settings.loop_max_external and unresolved_gaps:
            stop_reason = "external_limit_reached"
        return {
            "evidence": evidence,
            "external_attempts": external_attempts,
            "external_hits": external_hits,
            "unresolved_gaps": unresolved_gaps,
            "stop_reason": stop_reason,
            "steps": _append_step(
                state["steps"],
                "retrieve",
                "扩展外部学术来源",
                "complete",
                detail,
            ),
        }

    def synthesize(self, state: WorkflowState) -> WorkflowState:
        answer = self.llm.answer_from_evidence(
            question=state["question"],
            task_type=state["task_type"],
            detail_level=state["detail_level"],
            mode=state["mode"],
            evidence=state["evidence"],
            unresolved_gaps=state["unresolved_gaps"],
        )
        return {
            "answer": answer,
            "steps": _append_step(
                state["steps"],
                "synthesize",
                "生成回答",
                "complete",
                "回答已生成。",
            ),
        }

    def verify(self, state: WorkflowState) -> WorkflowState:
        confidence = _confidence_for_answer(state["evidence"], state["unresolved_gaps"], state["external_hits"])
        followups = [
            "请把这个回答整理成术语或机制草稿。",
            "请只保留本组站内证据，去掉外部线索。",
            "请结合某个 Shot 页面重新判断。",
        ]
        if state["should_generate_draft_preview"]:
            stop_reason = "draft_preview_requested"
        elif confidence >= self.settings.confidence_threshold and not state["unresolved_gaps"]:
            stop_reason = "confidence_threshold_reached"
        elif state["stop_reason"]:
            stop_reason = state["stop_reason"]
        elif state["unresolved_gaps"]:
            stop_reason = "evidence_gap_remaining"
        else:
            stop_reason = "answer_ready"
        return {
            "confidence": confidence,
            "suggested_followups": followups,
            "stop_reason": stop_reason,
            "steps": _append_step(
                state["steps"],
                "verify",
                "最终校验",
                "complete",
                f"置信度 {confidence:.2f}；停止原因：{stop_reason}。",
            ),
        }

    def draft_preview(self, state: WorkflowState) -> WorkflowState:
        prepared = prepare_draft_preview(
            self.settings,
            self.llm,
            question=state["question"],
            answer=state["answer"],
            source_titles=[item["title"] for item in state["evidence"][:6]],
        )
        return {
            "draft_preview_data": prepared,
            "pending_write_action": {
                "type": "draft_commit",
                "target_page": prepared["target_page"],
            },
            "steps": _append_step(
                state["steps"],
                "draft_preview",
                "生成草稿预览",
                "complete",
                f"已生成预览：{prepared['target_page']}。",
            ),
        }

    def commit_gate(self, state: WorkflowState) -> WorkflowState:
        return {
            "steps": _append_step(
                state["steps"],
                "commit_gate",
                "等待人工确认",
                "waiting",
                "草稿已生成预览，等待用户显式提交。",
            ),
        }

    def finalize(self, state: WorkflowState) -> WorkflowState:
        return {
            "steps": _append_step(
                state["steps"],
                "finalize",
                "完成本轮循环",
                "complete",
                state.get("stop_reason") or "本轮已完成。",
            ),
        }

    def route_after_local(self, state: WorkflowState) -> str:
        if state["task_type"] == TaskType.TOOL_WORKFLOW.value:
            return "retrieve_tools"
        if self._should_expand_external(state):
            return "retrieve_external"
        return "synthesize"

    def route_after_tools(self, state: WorkflowState) -> str:
        if self._should_expand_external(state):
            return "retrieve_external"
        return "synthesize"

    def route_after_external(self, state: WorkflowState) -> str:
        if self._should_expand_external(state):
            return "retrieve_external"
        return "synthesize"

    def route_after_verify(self, state: WorkflowState) -> str:
        if state["should_generate_draft_preview"]:
            return "draft_preview"
        return "finalize"

    def _should_expand_external(self, state: WorkflowState) -> bool:
        return bool(
            state.get("needs_external_search")
            and state.get("unresolved_gaps")
            and state.get("external_attempts", 0) < self.settings.loop_max_external
            and len(state.get("steps", [])) < self.settings.loop_max_steps
            and state.get("stop_reason") not in {"external_no_new_evidence", "external_limit_reached"}
        )


def build_plan(question: str, mode: AssistantMode | str, context_pages: list[str]) -> PlanResponse:
    task_type = classify_question(question, mode)
    sources, needs_external = plan_sources(task_type, context_pages)
    mode_value = mode.value if isinstance(mode, AssistantMode) else str(mode)
    return PlanResponse(
        task_type=task_type,
        planned_sources=sources,
        needs_external_search=needs_external,
        will_generate_draft_preview=(mode_value == AssistantMode.DRAFT.value or task_type == TaskType.DRAFT),
    )


def run_chat(
    db: Session,
    settings: Settings,
    llm: LLMClient,
    wiki: MediaWikiClient,
    openalex: OpenAlexClient,
    tools: ToolClients,
    request: ChatRequest,
) -> ChatResponse:
    session_record = _session_for_request(db, request)
    session_record.current_page = request.context_pages[0] if request.context_pages else session_record.current_page

    workflow = AssistantWorkflow(db, settings, llm, wiki, openalex, tools)
    state = workflow.run(request)

    turn = AssistantTurn(
        session_id=session_record.id,
        question=request.question,
        mode=request.mode.value,
        detail_level=request.detail_level.value,
        task_type=state["task_type"],
        answer=state["answer"],
        step_stream=state["steps"],
        sources=[{
            "source_type": item["source_type"],
            "source_id": item["source_id"],
            "title": item["title"],
            "url": item.get("url"),
            "snippet": item.get("snippet"),
        } for item in state["evidence"][:8]],
        unresolved_gaps=state["unresolved_gaps"],
        suggested_followups=state["suggested_followups"],
        confidence=state["confidence"],
        status="completed",
    )
    db.add(turn)
    db.flush()

    draft_preview = None
    if state.get("draft_preview_data"):
        prepared = state["draft_preview_data"]
        preview = save_draft_preview(
            db,
            session_id=session_record.id,
            turn_id=turn.id,
            title=prepared["title"],
            target_page=prepared["target_page"],
            content=prepared["content"],
            metadata_json=prepared.get("metadata_json"),
        )
        draft_preview = DraftPreviewPayload(
            preview_id=preview.id,
            title=preview.title,
            target_page=preview.target_page,
            content=preview.content,
            metadata=preview.metadata_json,
        )

    session_record.last_stage = "completed"
    session_record.step_count = len(state["steps"])
    session_record.confidence = state["confidence"]

    log_audit(
        db,
        session_id=session_record.id,
        turn_id=turn.id,
        action_type="chat_completed",
        payload={
            "task_type": state["task_type"],
            "confidence": state["confidence"],
            "mode": request.mode.value,
            "stop_reason": state.get("stop_reason"),
            "tool_calls": state.get("tool_calls", []),
        },
    )

    return ChatResponse(
        session_id=session_record.id,
        turn_id=turn.id,
        task_type=TaskType(state["task_type"]),
        answer=state["answer"],
        step_stream=[StepItem(**step) for step in state["steps"]],
        sources=[SourceItem(
            source_type=item["source_type"],
            source_id=item["source_id"],
            title=item["title"],
            url=item.get("url"),
            snippet=item.get("snippet"),
        ) for item in state["evidence"][:8]],
        confidence=state["confidence"],
        unresolved_gaps=state["unresolved_gaps"],
        suggested_followups=state["suggested_followups"],
        draft_preview=draft_preview,
    )
