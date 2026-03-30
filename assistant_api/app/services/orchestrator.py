from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clients.openalex import OpenAlexClient
from ..clients.tools import ToolClients
from ..clients.wiki import MediaWikiClient
from ..config import Settings
from ..constants import AssistantMode, SourceType, TaskType
from ..models import AssistantSession, AssistantTurn
from ..schemas import ActionTraceItem, ChatRequest, ChatResponse, DraftPreviewPayload, ModelInfoPayload, OperationPreviewPayload, OperationResultPayload, PdfIngestReviewPayload, PlanResponse, ResultFillPayload, SourceItem, StepItem, WritePreviewPayload, WriteResultPayload
from .agent_loop import AgentExecutor
from .attachments import build_attachment_evidence
from .audit import log_audit
from .drafts import prepare_draft_preview, save_draft_preview
from .intent import (
    is_compare_request,
    is_learning_path_request,
    is_page_structuring_request,
    is_tool_workflow_request,
    is_write_action_request,
)
from .llm import LLMClient
from .model_catalog import fallback_model_for, resolve_workflow_generation_selection
from .operation_payloads import derive_operation_preview, derive_operation_result
from .pdf_ingest import is_pdf_ingest_request, prepare_pdf_ingest_review
from .result_fill import is_shot_result_fill_request, prepare_shot_result_fill
from .search import search_chunks
from .write_actions import prepare_write_preview


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
    action_trace: list[dict[str, Any]]
    unresolved_gaps: list[str]
    confidence: float
    answer: str
    suggested_followups: list[str]
    draft_preview_data: dict[str, Any] | None
    write_preview_data: dict[str, Any] | None
    write_result_data: dict[str, Any] | None
    result_fill_data: dict[str, Any] | None
    pdf_ingest_review_data: dict[str, Any] | None
    pending_write_action: dict[str, Any] | None
    stop_reason: str | None
    structured_only: bool
    conversation_history: list[dict[str, str]]
    should_generate_write_preview: bool


def _append_step(steps: list[dict[str, str]], stage: str, title: str, status: str, detail: str) -> list[dict[str, str]]:
    return steps + [{
        "stage": stage,
        "title": title,
        "status": status,
        "detail": detail,
    }]


def classify_question(question: str, mode: AssistantMode | str, context_pages: list[str] | None = None) -> TaskType:
    mode_value = mode.value if isinstance(mode, AssistantMode) else str(mode)
    lowered = question.lower()
    current_page = context_pages[0] if context_pages else None
    if is_write_action_request(question, current_page):
        return TaskType.WRITE_ACTION
    if is_compare_request(question):
        return TaskType.COMPARE
    if (
        mode_value == AssistantMode.DRAFT.value
        or is_page_structuring_request(question, current_page)
        or any(token in question for token in ["草稿", "整理成条目", "生成条目", "生成模板"])
    ):
        return TaskType.DRAFT
    if any(token in lowered for token in ["paper", "zotero", "doi"]) or any(token in question for token in ["论文", "文献", "参考文献"]):
        return TaskType.LITERATURE
    if is_learning_path_request(question):
        return TaskType.LEARNING_PATH
    if is_tool_workflow_request(question):
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
        SourceType.CONTEXT.value: 0,
        SourceType.CARGO.value: 1,
        SourceType.WIKI.value: 2,
        SourceType.ZOTERO.value: 3,
        SourceType.OPENALEX.value: 4,
        SourceType.WEB.value: 5,
        SourceType.TOOL.value: 6,
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


def plan_sources(
    task_type: TaskType,
    context_pages: list[str],
    structured_only: bool,
    enable_zotero: bool,
) -> tuple[list[str], bool]:
    if structured_only:
        sources = [SourceType.CARGO.value]
        needs_external = task_type in {TaskType.COMPARE, TaskType.LITERATURE}
        if needs_external and enable_zotero:
            sources.append(SourceType.ZOTERO.value)
        return sources, needs_external
    sources = [SourceType.CARGO.value, SourceType.WIKI.value]
    if context_pages:
        sources.insert(0, SourceType.CONTEXT.value)
    needs_external = False
    if task_type in {TaskType.COMPARE, TaskType.LITERATURE} and enable_zotero:
        sources.append(SourceType.ZOTERO.value)
    if task_type in {TaskType.COMPARE, TaskType.LITERATURE}:
        needs_external = True
    if task_type == TaskType.TOOL_WORKFLOW:
        sources.append(SourceType.TOOL.value)
    if task_type == TaskType.WRITE_ACTION:
        needs_external = False
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


def _apply_generation_selection(
    settings: Settings,
    session_record: AssistantSession,
    request: ChatRequest,
) -> Any:
    selection = resolve_workflow_generation_selection(
        settings,
        requested_provider=request.generation_provider,
        requested_model=request.generation_model,
        session_provider=session_record.generation_provider,
        session_model=session_record.generation_model,
        workflow_hint=request.workflow_hint,
    )
    session_record.generation_provider = selection.provider
    session_record.generation_model = selection.requested_model
    session_record.generation_fallback_model = fallback_model_for(selection.requested_model)
    return selection


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


def _conversation_history_for_session(db: Session, session_id: str | None, limit: int) -> list[dict[str, str]]:
    if not session_id:
        return []
    turns = db.execute(
        select(AssistantTurn)
        .where(AssistantTurn.session_id == session_id)
        .order_by(AssistantTurn.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return [
        {"question": turn.question, "answer": turn.answer or ""}
        for turn in reversed(turns)
    ]


def _serialize_sources(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "source_type": item["source_type"],
        "source_id": item["source_id"],
        "title": item["title"],
        "url": item.get("url"),
        "snippet": item.get("snippet"),
    } for item in evidence[:8]]


def _context_evidence(wiki: MediaWikiClient, context_pages: list[str]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for title in context_pages[:1]:
        text = wiki.get_page_text(title) or ""
        evidence.append({
            "source_type": SourceType.CONTEXT.value,
            "source_id": title,
            "title": title,
            "url": wiki.page_url(title),
            "snippet": " ".join(text.split())[:280] if text else title,
            "content": text,
            "score": 2.0,
        })
    return evidence


def _result_fill_answer(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    title = str(payload.get("title") or "Shot 结果回填建议")
    draft_text = str(payload.get("draft_text") or "").strip()
    missing_items: list[str] = []
    for item in payload.get("missing_items", []) or []:
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("field") or item.get("name") or "").strip()
            reason = str(item.get("reason") or item.get("note") or item.get("message") or "").strip()
            evidence = [
                str(entry).strip()
                for entry in item.get("evidence", [])
                if str(entry).strip()
            ] if isinstance(item.get("evidence"), list) else []
            if not label:
                continue
            line = label
            if reason:
                line += "：" + reason
            if evidence:
                line += "（证据：" + "；".join(evidence) + "）"
            missing_items.append(line)
            continue
        value = str(item).strip()
        if value:
            missing_items.append(value)
    evidence = [str(item).strip() for item in payload.get("evidence", []) if str(item).strip()]

    parts.append(f"## {title}")
    if draft_text:
        parts.append(draft_text)
    if missing_items:
        parts.append("### 待确认项\n- " + "\n- ".join(missing_items))
    if evidence:
        parts.append("### 识别依据\n- " + "\n- ".join(evidence))
    return "\n\n".join(parts).strip()


def _run_shot_result_fill(
    *,
    settings: Settings,
    llm: LLMClient,
    wiki: MediaWikiClient,
    request: ChatRequest,
    conversation_history: list[dict[str, str]],
) -> WorkflowState:
    evidence = _dedupe_evidence(
        _context_evidence(wiki, request.context_pages),
        build_attachment_evidence(request.attachments),
    )
    result_fill_data = prepare_shot_result_fill(
        settings=settings,
        llm=llm,
        attachments_dir=Path(settings.attachments_dir),
        request=request,
        answer="",
        source_titles=[item["title"] for item in evidence[:6]],
        conversation_history=conversation_history,
    )
    answer = _result_fill_answer(result_fill_data)
    return {
        "question": request.question,
        "mode": request.mode.value,
        "detail_level": request.detail_level.value,
        "context_pages": request.context_pages,
        "user_name": request.user_name,
        "conversation_history": conversation_history,
        "task_type": TaskType.DRAFT.value,
        "planned_sources": [SourceType.CONTEXT.value, "attachment"],
        "needs_external_search": False,
        "structured_only": False,
        "should_generate_draft_preview": False,
        "should_generate_write_preview": False,
        "steps": [
            {
                "stage": "intake",
                "title": "理解结果回填请求",
                "status": "complete",
                "detail": "已接收 Shot 页面、附件截图和回填需求。",
            },
            {
                "stage": "result_fill",
                "title": "生成 Shot 回填建议",
                "status": "complete",
                "detail": "已生成字段建议、正文草稿和待确认项。",
            },
            {
                "stage": "finalize",
                "title": "完成本轮循环",
                "status": "complete",
                "detail": "shot_result_fill_ready",
            },
        ],
        "evidence": evidence,
        "external_attempts": 0,
        "external_hits": 0,
        "tool_calls": [],
        "action_trace": [],
        "unresolved_gaps": [
            str(item.get("label") or item.get("field") or item.get("name") or "").strip()
            if isinstance(item, dict) else str(item).strip()
            for item in (result_fill_data.get("missing_items") or [])
            if (isinstance(item, dict) and str(item.get("label") or item.get("field") or item.get("name") or "").strip()) or (not isinstance(item, dict) and str(item).strip())
        ],
        "confidence": 0.84,
        "answer": answer,
        "suggested_followups": [
            "请只保留可自动回填的字段。",
            "请把这版结果草稿填入编辑框。",
            "请把待确认项改写成检查清单。",
        ],
        "draft_preview_data": None,
        "write_preview_data": None,
        "write_result_data": None,
        "result_fill_data": result_fill_data,
        "pending_write_action": None,
        "stop_reason": "shot_result_fill_ready",
    }


def _pdf_ingest_answer(payload: dict[str, Any]) -> str:
    lines = [f"## {str(payload.get('title') or 'PDF 解析与写入建议')}"]
    summary = str(payload.get("document_summary") or "").strip()
    if summary:
        lines.append(summary)
    targets = payload.get("recommended_targets") or []
    if targets:
        lines.append("### 建议归档区域")
        for item in targets[:3]:
            target_title = str(item.get("target_title") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if not target_title:
                continue
            line = f"- {target_title}"
            if reason:
                line += f"：{reason}"
            lines.append(line)
    sections = payload.get("section_outline") or []
    if sections:
        lines.append("### 提取章节")
        for item in sections[:3]:
            title = str(item.get("title") or "").strip()
            content = str(item.get("content") or "").strip()
            if title and content:
                lines.append(f"- {title}：{content[:120]}")
    return "\n\n".join(lines).strip()


def _run_pdf_ingest_review(
    *,
    settings: Settings,
    llm: LLMClient,
    wiki: MediaWikiClient,
    request: ChatRequest,
    conversation_history: list[dict[str, str]],
) -> WorkflowState:
    evidence = _dedupe_evidence(
        _context_evidence(wiki, request.context_pages),
        build_attachment_evidence(request.attachments),
    )
    review_data = prepare_pdf_ingest_review(
        settings=settings,
        llm=llm,
        attachments_dir=Path(settings.attachments_dir),
        request=request,
    )
    answer = _pdf_ingest_answer(review_data)
    return {
        "question": request.question,
        "mode": request.mode.value,
        "detail_level": request.detail_level.value,
        "context_pages": request.context_pages,
        "user_name": request.user_name,
        "conversation_history": conversation_history,
        "task_type": TaskType.DRAFT.value,
        "planned_sources": [SourceType.CONTEXT.value, "attachment"],
        "needs_external_search": False,
        "structured_only": False,
        "should_generate_draft_preview": False,
        "should_generate_write_preview": False,
        "steps": [
            {
                "stage": "intake",
                "title": "理解 PDF 摄取请求",
                "status": "complete",
                "detail": "已接收 PDF 附件并准备提取内容。",
            },
            {
                "stage": "pdf_ingest",
                "title": "生成 PDF 解析与写入建议",
                "status": "complete",
                "detail": "已整理摘要、归档区域建议和草稿章节。",
            },
            {
                "stage": "finalize",
                "title": "完成本轮循环",
                "status": "complete",
                "detail": "pdf_ingest_review_ready",
            },
        ],
        "evidence": evidence,
        "external_attempts": 0,
        "external_hits": 0,
        "tool_calls": [],
        "action_trace": [],
        "unresolved_gaps": [],
        "confidence": 0.86,
        "answer": answer,
        "suggested_followups": [
            "请生成草稿预览。",
            "请只保留建议写入 Control 的部分。",
            "请把这份 PDF 拆成设备摘要和控制步骤两部分。",
        ],
        "draft_preview_data": None,
        "write_preview_data": None,
        "write_result_data": None,
        "result_fill_data": None,
        "pdf_ingest_review_data": review_data,
        "pending_write_action": None,
        "stop_reason": "pdf_ingest_review_ready",
    }


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

    def run(self, request: ChatRequest, conversation_history: list[dict[str, str]] | None = None) -> WorkflowState:
        initial_state: WorkflowState = {
            "question": request.question,
            "mode": request.mode.value,
            "detail_level": request.detail_level.value,
            "context_pages": request.context_pages,
            "user_name": request.user_name,
            "conversation_history": conversation_history or [],
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
            "write_preview_data": None,
            "write_result_data": None,
            "result_fill_data": None,
            "pdf_ingest_review_data": None,
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
        planned_sources, needs_external = plan_sources(
            task_type,
            state["context_pages"],
            structured_only,
            self.settings.enable_zotero,
        )
        return {
            "planned_sources": planned_sources,
            "needs_external_search": needs_external,
            "structured_only": structured_only,
            "should_generate_draft_preview": state["mode"] == AssistantMode.DRAFT.value or task_type == TaskType.DRAFT,
            "should_generate_write_preview": task_type == TaskType.WRITE_ACTION,
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
        if self.settings.enable_zotero and TaskType(state["task_type"]) in {TaskType.COMPARE, TaskType.LITERATURE}:
            indexed_source_types.append(SourceType.ZOTERO.value)
        query_embedding = self.llm.embed([state["question"]])
        indexed_hits = search_chunks(
            self.db,
            state["question"],
            source_types=indexed_source_types,
            limit=8,
            query_embedding=query_embedding[0] if query_embedding else None,
        )
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
        academic_hits: list[dict[str, Any]] = []
        web_hits: list[dict[str, Any]] = []
        detail_parts: list[str] = []

        try:
            academic_hits = self.openalex.search(state["question"], limit=4)
            detail_parts.append(f"新增 {len(academic_hits)} 条学术线索")
        except Exception as error:
            detail_parts.append(f"学术检索失败：{error}")

        if self.settings.enable_web_search:
            try:
                web_hits = self.llm.search_web(state["question"], limit=3)
                detail_parts.append(f"新增 {len(web_hits)} 条网页线索")
            except Exception as error:
                detail_parts.append(f"网页搜索失败：{error}")
        else:
            detail_parts.append("网页搜索未启用")

        external_hits_list = academic_hits + web_hits
        detail = "；".join(detail_parts) if detail_parts else "外部检索未返回新线索。"

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
            conversation_history=state.get("conversation_history", []),
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
        elif state["should_generate_write_preview"]:
            stop_reason = "write_preview_requested"
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
            conversation_history=state.get("conversation_history", []),
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


def build_plan(question: str, mode: AssistantMode | str, context_pages: list[str], settings: Settings) -> PlanResponse:
    task_type = classify_question(question, mode)
    sources, needs_external = plan_sources(task_type, context_pages, _prefers_structured_only(question), settings.enable_zotero)
    mode_value = mode.value if isinstance(mode, AssistantMode) else str(mode)
    return PlanResponse(
        task_type=task_type,
        planned_sources=sources,
        needs_external_search=needs_external,
        will_generate_draft_preview=(mode_value == AssistantMode.DRAFT.value or task_type == TaskType.DRAFT),
    )


def _persist_chat_state(
    db: Session,
    settings: Settings,
    session_record: AssistantSession,
    request: ChatRequest,
    state: WorkflowState,
) -> tuple[
    AssistantTurn,
    OperationPreviewPayload | None,
    OperationResultPayload | None,
    DraftPreviewPayload | None,
    WritePreviewPayload | None,
    WriteResultPayload | None,
    ResultFillPayload | None,
    PdfIngestReviewPayload | None,
]:
    turn = AssistantTurn(
        session_id=session_record.id,
        question=request.question,
        mode=request.mode.value,
        detail_level=request.detail_level.value,
        task_type=state["task_type"],
        answer=state["answer"],
        step_stream=state["steps"],
        action_trace=state.get("action_trace", []),
        sources=_serialize_sources(state["evidence"]),
        draft_preview=state.get("draft_preview_data"),
        write_preview=state.get("write_preview_data"),
        write_result=state.get("write_result_data"),
        result_fill=state.get("result_fill_data"),
        pdf_ingest_review=state.get("pdf_ingest_review_data"),
        model_info=state.get("model_info"),
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
        turn.draft_preview = draft_preview.model_dump()

    write_preview = None
    if state.get("write_preview_data"):
        prepared = state["write_preview_data"]
        preview = save_draft_preview(
            db,
            session_id=session_record.id,
            turn_id=turn.id,
            title=prepared["action_type"],
            target_page=prepared["target_page"],
            content=prepared["preview_text"],
            metadata_json=prepared.get("metadata_json"),
        )
        metadata = preview.metadata_json or {}
        write_preview = WritePreviewPayload(
            preview_id=preview.id,
            action_type=prepared["action_type"],
            operation=prepared["operation"],
            target_page=preview.target_page,
            target_section=metadata.get("target_section"),
            preview_text=preview.content,
            structured_payload=prepared["structured_payload"],
            missing_fields=metadata.get("missing_fields", []),
            metadata=metadata,
        )
        turn.write_preview = write_preview.model_dump()

    write_result = None
    if state.get("write_result_data"):
        write_result = WriteResultPayload(**state["write_result_data"])
        turn.write_result = write_result.model_dump()
    result_fill = None
    if state.get("result_fill_data"):
        result_fill = ResultFillPayload(**state["result_fill_data"])
        turn.result_fill = result_fill.model_dump()
    pdf_ingest_review = None
    if state.get("pdf_ingest_review_data"):
        pdf_ingest_review = PdfIngestReviewPayload(**state["pdf_ingest_review_data"])
        turn.pdf_ingest_review = pdf_ingest_review.model_dump()
    if state.get("model_info"):
        turn.model_info = state["model_info"]

    operation_preview = derive_operation_preview(
        draft_preview=draft_preview,
        write_preview=write_preview,
        result_fill=result_fill,
    )
    operation_result = derive_operation_result(write_result=write_result)

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
            "action_trace": state.get("action_trace", []),
            "model_info": state.get("model_info"),
            "write_result": state.get("write_result_data"),
        },
    )
    return turn, operation_preview, operation_result, draft_preview, write_preview, write_result, result_fill, pdf_ingest_review


def _build_chat_response(
    session_record: AssistantSession,
    turn: AssistantTurn,
    state: WorkflowState,
    operation_preview: OperationPreviewPayload | None,
    operation_result: OperationResultPayload | None,
    draft_preview: DraftPreviewPayload | None,
    write_preview: WritePreviewPayload | None,
    write_result: WriteResultPayload | None,
    result_fill: ResultFillPayload | None,
    pdf_ingest_review: PdfIngestReviewPayload | None,
) -> ChatResponse:
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
        action_trace=[ActionTraceItem(**item) for item in state.get("action_trace", [])],
        operation_preview=operation_preview,
        operation_result=operation_result,
        draft_preview=draft_preview,
        write_preview=write_preview,
        write_result=write_result,
        result_fill=result_fill,
        pdf_ingest_review=pdf_ingest_review,
        model_info=ModelInfoPayload(**state["model_info"]) if state.get("model_info") else None,
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
    selection = _apply_generation_selection(settings, session_record, request)
    request_llm = llm.with_generation_config(selection)
    conversation_history = _conversation_history_for_session(db, session_record.id, settings.conversation_history_turns)
    if is_pdf_ingest_request(request):
        state = _run_pdf_ingest_review(
            settings=settings,
            llm=request_llm,
            wiki=wiki,
            request=request,
            conversation_history=conversation_history,
        )
        state["model_info"] = request_llm.model_info
        turn, operation_preview, operation_result, draft_preview, write_preview, write_result, result_fill, pdf_ingest_review = _persist_chat_state(db, settings, session_record, request, state)
        return _build_chat_response(
            session_record,
            turn,
            state,
            operation_preview,
            operation_result,
            draft_preview,
            write_preview,
            write_result,
            result_fill,
            pdf_ingest_review,
        )
    if is_shot_result_fill_request(request):
        state = _run_shot_result_fill(
            settings=settings,
            llm=request_llm,
            wiki=wiki,
            request=request,
            conversation_history=conversation_history,
        )
        state["model_info"] = request_llm.model_info
        turn, operation_preview, operation_result, draft_preview, write_preview, write_result, result_fill, pdf_ingest_review = _persist_chat_state(db, settings, session_record, request, state)
        return _build_chat_response(
            session_record,
            turn,
            state,
            operation_preview,
            operation_result,
            draft_preview,
            write_preview,
            write_result,
            result_fill,
            pdf_ingest_review,
        )
    task_type = classify_question(request.question, request.mode, request.context_pages).value
    planned_sources, _ = plan_sources(task_type=TaskType(task_type), context_pages=request.context_pages, structured_only=_prefers_structured_only(request.question), enable_zotero=settings.enable_zotero)
    executor = AgentExecutor(db, settings, request_llm, wiki, openalex, tools)
    state = executor.execute(
        request,
        conversation_history=conversation_history,
        task_type=task_type,
        planned_sources=planned_sources,
    )
    if not state.get("answer"):
        state["answer"] = request_llm.answer_from_evidence(
            question=request.question,
            task_type=task_type,
            detail_level=request.detail_level.value,
            mode=request.mode.value,
            current_page=request.context_pages[0] if request.context_pages else None,
            evidence=state["evidence"],
            unresolved_gaps=state["unresolved_gaps"],
            conversation_history=conversation_history,
        )
        state["steps"] = _append_step(state["steps"], "synthesize", "生成回答", "complete", "回答已生成。")
    state = executor.finalize(state, request)
    state["model_info"] = request_llm.model_info
    turn, operation_preview, operation_result, draft_preview, write_preview, write_result, result_fill, pdf_ingest_review = _persist_chat_state(db, settings, session_record, request, state)
    return _build_chat_response(
        session_record,
        turn,
        state,
        operation_preview,
        operation_result,
        draft_preview,
        write_preview,
        write_result,
        result_fill,
        pdf_ingest_review,
    )


def run_chat_stream(
    db: Session,
    settings: Settings,
    llm: LLMClient,
    wiki: MediaWikiClient,
    openalex: OpenAlexClient,
    tools: ToolClients,
    request: ChatRequest,
) -> Iterator[dict[str, Any]]:
    session_record = _session_for_request(db, request)
    session_record.current_page = request.context_pages[0] if request.context_pages else session_record.current_page
    selection = _apply_generation_selection(settings, session_record, request)
    request_llm = llm.with_generation_config(selection)
    conversation_history = _conversation_history_for_session(db, session_record.id, settings.conversation_history_turns)

    yield {
        "event": "session_started",
        "data": {
            "session_id": session_record.id,
            "history": conversation_history,
            "model_info": request_llm.model_info,
        },
    }
    if is_pdf_ingest_request(request):
        state = _run_pdf_ingest_review(
            settings=settings,
            llm=request_llm,
            wiki=wiki,
            request=request,
            conversation_history=conversation_history,
        )
        state["model_info"] = request_llm.model_info
        for step in state["steps"]:
            yield {"event": "step", "data": step}
        yield {"event": "sources", "data": {"sources": _serialize_sources(state["evidence"])}}
        turn, operation_preview, operation_result, draft_preview, write_preview, write_result, result_fill, pdf_ingest_review = _persist_chat_state(db, settings, session_record, request, state)
        if pdf_ingest_review is not None:
            yield {"event": "pdf_ingest_review", "data": pdf_ingest_review.model_dump()}
        if operation_preview is not None:
            yield {"event": "operation_preview", "data": operation_preview.model_dump()}
        if operation_result is not None:
            yield {"event": "operation_result", "data": operation_result.model_dump()}
        response = _build_chat_response(
            session_record,
            turn,
            state,
            operation_preview,
            operation_result,
            draft_preview,
            write_preview,
            write_result,
            result_fill,
            pdf_ingest_review,
        )
        yield {"event": "done", "data": response.model_dump()}
        return
    if is_shot_result_fill_request(request):
        state = _run_shot_result_fill(
            settings=settings,
            llm=request_llm,
            wiki=wiki,
            request=request,
            conversation_history=conversation_history,
        )
        state["model_info"] = request_llm.model_info
        for step in state["steps"]:
            yield {"event": "step", "data": step}
        yield {"event": "sources", "data": {"sources": _serialize_sources(state["evidence"])}}
        turn, operation_preview, operation_result, draft_preview, write_preview, write_result, result_fill, pdf_ingest_review = _persist_chat_state(db, settings, session_record, request, state)
        if operation_preview is not None:
            yield {"event": "operation_preview", "data": operation_preview.model_dump()}
        if operation_result is not None:
            yield {"event": "operation_result", "data": operation_result.model_dump()}
        if result_fill is not None:
            yield {"event": "result_fill", "data": result_fill.model_dump()}
        response = _build_chat_response(
            session_record,
            turn,
            state,
            operation_preview,
            operation_result,
            draft_preview,
            write_preview,
            write_result,
            result_fill,
            pdf_ingest_review,
        )
        yield {"event": "done", "data": response.model_dump()}
        return
    task_type = classify_question(request.question, request.mode, request.context_pages).value
    planned_sources, _ = plan_sources(task_type=TaskType(task_type), context_pages=request.context_pages, structured_only=_prefers_structured_only(request.question), enable_zotero=settings.enable_zotero)
    executor = AgentExecutor(db, settings, request_llm, wiki, openalex, tools)
    state = executor.execute(
        request,
        conversation_history=conversation_history,
        task_type=task_type,
        planned_sources=planned_sources,
    )
    for step in state["steps"]:
        yield {"event": "step", "data": step}
    if state.get("action_trace"):
        yield {"event": "action_trace", "data": {"items": state["action_trace"]}}
    should_stream_answer = not (
        task_type == TaskType.WRITE_ACTION.value
        and (state.get("write_preview_data") or state.get("write_result_data"))
    )
    if should_stream_answer:
        yield from executor.stream_answer(state)
    state = executor.finalize(state, request)
    state["model_info"] = request_llm.model_info
    final_steps_to_emit = 1
    if state.get("draft_preview_data"):
        final_steps_to_emit += 1
    if state.get("write_preview_data"):
        final_steps_to_emit += 1
    for step in state["steps"][-final_steps_to_emit:]:
        yield {"event": "step", "data": step}
    yield {"event": "sources", "data": {"sources": _serialize_sources(state["evidence"])}}

    turn, operation_preview, operation_result, draft_preview, write_preview, write_result, result_fill, pdf_ingest_review = _persist_chat_state(db, settings, session_record, request, state)
    if operation_preview is not None:
        yield {"event": "operation_preview", "data": operation_preview.model_dump()}
    if operation_result is not None:
        yield {"event": "operation_result", "data": operation_result.model_dump()}
    if draft_preview is not None:
        yield {"event": "draft_preview", "data": draft_preview.model_dump()}
    if write_preview is not None:
        yield {"event": "write_preview", "data": write_preview.model_dump()}
    if write_result is not None:
        yield {"event": "write_result", "data": write_result.model_dump()}
    if result_fill is not None:
        yield {"event": "result_fill", "data": result_fill.model_dump()}
    if pdf_ingest_review is not None:
        yield {"event": "pdf_ingest_review", "data": pdf_ingest_review.model_dump()}
    response = _build_chat_response(
        session_record,
        turn,
        state,
        operation_preview,
        operation_result,
        draft_preview,
        write_preview,
        write_result,
        result_fill,
        pdf_ingest_review,
    )
    yield {"event": "done", "data": response.model_dump()}
