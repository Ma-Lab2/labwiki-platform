from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..models import AssistantSession, AssistantTurn


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "未知"
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "-", _safe_text(value))
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "labassistant-session"


def build_session_export_filename(session_record: AssistantSession) -> str:
    short_id = (session_record.id or "session")[:8]
    if session_record.current_page:
        return f"{_slugify(session_record.current_page)}-session-{short_id}.md"
    return f"labassistant-session-{short_id}.md"


def _append_lines(lines: list[str], *items: str) -> None:
    for item in items:
        lines.append(item)


def _render_sources(lines: list[str], sources: list[dict[str, Any]] | None) -> None:
    _append_lines(lines, "### 来源")
    if not sources:
        _append_lines(lines, "暂无来源。", "")
        return
    for source in sources:
        title = _safe_text(source.get("title") or source.get("source_id") or "未命名来源")
        url = _safe_text(source.get("url"))
        snippet = _safe_text(source.get("snippet"))
        if url:
            _append_lines(lines, f"- [{title}]({url})")
        else:
            _append_lines(lines, f"- {title}")
        if snippet:
            _append_lines(lines, f"  - 摘要：{snippet}")
    _append_lines(lines, "")


def _render_result_fill(lines: list[str], result_fill: dict[str, Any]) -> None:
    field_suggestions = result_fill.get("field_suggestions") or {}
    confirmed: list[tuple[str, dict[str, Any]]] = []
    pending: list[tuple[str, dict[str, Any]]] = []
    missing = result_fill.get("missing_items") or []

    for label, raw_value in field_suggestions.items():
        if isinstance(raw_value, dict):
            status = _safe_text(raw_value.get("status")).lower()
            if status == "confirmed":
                confirmed.append((label, raw_value))
            else:
                pending.append((label, raw_value))
        elif _safe_text(raw_value):
            confirmed.append((label, {"value": raw_value}))

    _append_lines(lines, "#### 结果回填")
    if confirmed:
        _append_lines(lines, "##### 已识别字段")
        for label, payload in confirmed:
            value = _safe_text(payload.get("value"))
            _append_lines(lines, f"- {label}：{value}")
            for evidence in payload.get("evidence") or []:
                _append_lines(lines, f"  - 证据：{_safe_text(evidence)}")
    if pending:
        _append_lines(lines, "##### 待确认字段")
        for label, payload in pending:
            value = _safe_text(payload.get("value"))
            reason = _safe_text(payload.get("reason"))
            _append_lines(lines, f"- {label}：{value}")
            if reason:
                _append_lines(lines, f"  - 原因：{reason}")
            for evidence in payload.get("evidence") or []:
                _append_lines(lines, f"  - 证据：{_safe_text(evidence)}")
    if missing:
        _append_lines(lines, "##### 缺失字段")
        for item in missing:
            if isinstance(item, dict):
                label = _safe_text(item.get("label") or "未命名字段")
                reason = _safe_text(item.get("reason"))
                _append_lines(lines, f"- {label}")
                if reason:
                    _append_lines(lines, f"  - 原因：{reason}")
                for evidence in item.get("evidence") or []:
                    _append_lines(lines, f"  - 证据：{_safe_text(evidence)}")
            else:
                _append_lines(lines, f"- {_safe_text(item)}")
    draft_text = _safe_text(result_fill.get("draft_text"))
    if draft_text:
        _append_lines(lines, "##### 草稿摘要", "```markdown", draft_text, "```")
    _append_lines(lines, "")


def _render_preview(lines: list[str], title: str, payload: dict[str, Any] | None) -> None:
    if not payload:
        return
    _append_lines(lines, f"#### {title}")
    preview_title = _safe_text(payload.get("title") or payload.get("action_type") or payload.get("status") or title)
    target_page = _safe_text(payload.get("target_page") or payload.get("page_title"))
    detail = _safe_text(
        payload.get("detail")
        or payload.get("preview_text")
        or payload.get("content")
        or payload.get("operation")
    )
    _append_lines(lines, f"- 标题：{preview_title}")
    if target_page:
        _append_lines(lines, f"- 目标：{target_page}")
    if detail:
        _append_lines(lines, f"- 摘要：{detail}")


def _render_pdf_ingest_review(lines: list[str], review: dict[str, Any]) -> None:
    _append_lines(lines, "#### PDF 摄取建议")
    summary = _safe_text(review.get("document_summary"))
    file_name = _safe_text(review.get("file_name"))
    if file_name:
        _append_lines(lines, f"- 文件：{file_name}")
    if summary:
        _append_lines(lines, f"- 摘要：{summary}")
    proposed_draft_title = _safe_text(review.get("proposed_draft_title"))
    if proposed_draft_title:
        _append_lines(lines, f"- 草稿页：{proposed_draft_title}")
    recommended_targets = review.get("recommended_targets") or []
    if recommended_targets:
        _append_lines(lines, "##### 建议归档区域")
        for item in recommended_targets[:3]:
            target_title = _safe_text(item.get("target_title"))
            reason = _safe_text(item.get("reason"))
            if not target_title:
                continue
            _append_lines(lines, f"- {target_title}")
            if reason:
                _append_lines(lines, f"  - 原因：{reason}")
    section_outline = review.get("section_outline") or []
    if section_outline:
        _append_lines(lines, "##### 建议章节")
        for item in section_outline[:6]:
            title = _safe_text(item.get("title"))
            content = _safe_text(item.get("content"))
            if title:
                _append_lines(lines, f"- {title}")
            if content:
                _append_lines(lines, f"  - 摘要：{content}")
    evidence = review.get("evidence") or []
    if evidence:
        _append_lines(lines, "##### 提取依据")
        for item in evidence[:8]:
            _append_lines(lines, f"- {_safe_text(item)}")
    _append_lines(lines, "")


def _render_turn_summary(lines: list[str], turn: AssistantTurn) -> None:
    has_summary = False
    _append_lines(lines, "### 结果摘要")
    if turn.result_fill:
        _render_result_fill(lines, turn.result_fill)
        has_summary = True
    if turn.pdf_ingest_review:
        _render_pdf_ingest_review(lines, turn.pdf_ingest_review)
        has_summary = True
    if turn.draft_preview:
        _render_preview(lines, "草稿预览", turn.draft_preview)
        has_summary = True
    if turn.write_preview:
        _render_preview(lines, "写入预览", turn.write_preview)
        has_summary = True
    if turn.write_result:
        _render_preview(lines, "写入结果", turn.write_result)
        has_summary = True
    if turn.unresolved_gaps:
        has_summary = True
        _append_lines(lines, "#### 未解决问题")
        for item in turn.unresolved_gaps or []:
            _append_lines(lines, f"- {_safe_text(item)}")
    if turn.suggested_followups:
        has_summary = True
        _append_lines(lines, "#### 建议后续问题")
        for item in turn.suggested_followups or []:
            _append_lines(lines, f"- {_safe_text(item)}")
    if not has_summary:
        _append_lines(lines, "暂无结果摘要。")
    _append_lines(lines, "")


def build_session_markdown(session_record: AssistantSession, turns: list[AssistantTurn]) -> str:
    lines: list[str] = []
    _append_lines(
        lines,
        "# 智能助手聊天记录导出",
        "",
        f"- 会话 ID：`{_safe_text(session_record.id)}`",
        f"- 用户：{_safe_text(session_record.user_name) or '未知'}",
        f"- 页面：{_safe_text(session_record.current_page) or '未绑定页面'}",
        f"- 创建时间：{_format_dt(session_record.created_at)}",
        f"- 更新时间：{_format_dt(session_record.updated_at)}",
        f"- 总轮数：{len(turns)}",
        "",
    )

    if not turns:
        _append_lines(lines, "当前会话暂无聊天记录。", "")
        return "\n".join(lines).strip() + "\n"

    for index, turn in enumerate(turns, start=1):
        _append_lines(
            lines,
            f"## 第 {index} 轮",
            "",
            f"- 时间：{_format_dt(turn.created_at)}",
            f"- 模式：{_safe_text(turn.mode) or 'qa'}",
            f"- 任务类型：{_safe_text(turn.task_type) or 'unknown'}",
            "",
            "### 用户",
            _safe_text(turn.question) or "（空）",
            "",
            "### 助手",
            _safe_text(turn.answer) or "（空）",
            "",
        )
        _render_sources(lines, turn.sources or [])
        _render_turn_summary(lines, turn)

    return "\n".join(lines).strip() + "\n"
