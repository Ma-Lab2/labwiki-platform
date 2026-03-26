from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..schemas import ChatRequest
from .attachments import build_attachment_prompt_parts
from .prompts import build_result_fill_prompt


def _load_json_object(raw: str) -> dict[str, Any]:
    candidate = str(raw or "").strip()
    if candidate.startswith("```"):
        candidate = "\n".join(
            line for line in candidate.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    return json.loads(candidate)


def is_shot_result_fill_request(request: ChatRequest) -> bool:
    if (request.workflow_hint or "").strip() == "shot_result_fill":
        return True
    current_page = request.context_pages[0] if request.context_pages else ""
    has_image = any(
        item.kind == "image" or item.mime_type.startswith("image/")
        for item in request.attachments
    )
    if not current_page.startswith("Shot:") or not has_image:
        return False
    lowered = request.question.lower()
    return any(token in lowered for token in ["shot", "回填", "截图", "结果图", "补记录", "整理"])


def _extract_shot_metadata(current_page: str) -> dict[str, str]:
    match = re.search(r"Shot:(\d{4}-\d{2}-\d{2})-(Run[0-9A-Za-z_-]+)-(Shot[0-9A-Za-z_-]+)", current_page or "")
    if not match:
        return {}
    return {
        "date": match.group(1),
        "run": match.group(2),
        "shot": match.group(3),
        "title": match.group(0),
    }


def _normalize_missing_label(raw_item: Any) -> str:
    if isinstance(raw_item, dict):
        return str(raw_item.get("label") or raw_item.get("field") or raw_item.get("name") or "").strip()
    return str(raw_item or "").strip()


def _ensure_pending_candidates(
    *,
    field_suggestions: dict[str, Any],
    missing_items: list[Any],
    current_page: str,
) -> tuple[dict[str, Any], list[Any]]:
    metadata = _extract_shot_metadata(current_page)
    if not metadata:
        return field_suggestions, missing_items
    has_pending = any(
        isinstance(value, dict) and str(value.get("status") or "").strip().lower() in {"pending", "needs_review"}
        for value in field_suggestions.values()
    )
    if has_pending:
        return field_suggestions, missing_items

    page_evidence = [f"当前页 {current_page}"] if current_page else []
    pending_candidates = {
        "原始数据主目录": {
            "value": f"/data/shot/{metadata['date']}/{metadata['run']}",
            "status": "pending",
            "reason": "按 Shot 标题可推得本次原始数据主目录候选，请学生确认实际存储路径。",
            "evidence": page_evidence,
        },
        "处理结果文件": {
            "value": current_page.replace(":", "-") + "-analysis.zip",
            "status": "pending",
            "reason": "按 Shot 标题可推得处理结果文件命名候选，请学生确认实际文件名。",
            "evidence": page_evidence,
        },
    }
    normalized_missing = {_normalize_missing_label(item) for item in missing_items}
    updated_missing: list[Any] = []
    for item in missing_items:
        if _normalize_missing_label(item) in pending_candidates:
            continue
        updated_missing.append(item)
    for label, value in pending_candidates.items():
        if label in field_suggestions:
            continue
        if label not in normalized_missing:
            continue
        field_suggestions[label] = value
    return field_suggestions, updated_missing


def _fallback_from_page(request: ChatRequest, answer: str) -> dict[str, Any]:
    current_page = request.context_pages[0] if request.context_pages else ""
    field_suggestions: dict[str, Any] = {}
    page_evidence = f"当前页 {current_page}" if current_page else ""
    metadata = _extract_shot_metadata(current_page)
    if current_page.startswith("Shot:"):
        field_suggestions["Shot编号"] = {
            "value": current_page,
            "status": "confirmed",
            "evidence": [page_evidence] if page_evidence else [],
        }
        if metadata:
            field_suggestions["日期"] = {
                "value": metadata["date"],
                "status": "confirmed",
                "evidence": [page_evidence] if page_evidence else [],
            }
            field_suggestions["Run"] = {
                "value": metadata["run"],
                "status": "confirmed",
                "evidence": [page_evidence] if page_evidence else [],
            }
    first_image = next((item for item in request.attachments if item.kind == "image"), None)
    if first_image:
        field_suggestions["TPS结果图"] = {
            "value": first_image.name,
            "status": "confirmed",
            "evidence": [f"附件 {first_image.name}"],
        }
    missing_items: list[dict[str, Any]] = [
        {
            "label": "原始数据主目录",
            "reason": "按 Shot 标题可推得本次原始数据主目录候选，请学生确认实际存储路径。",
            "evidence": [page_evidence] if page_evidence else [],
        },
        {
            "label": "处理结果文件",
            "reason": "按 Shot 标题可推得处理结果文件命名候选，请学生确认实际文件名。",
            "evidence": [page_evidence] if page_evidence else [],
        },
        {
            "label": "主要观测",
            "reason": "当前页面和附件名称不足以稳妥提取主要观测，请学生结合截图内容补充。",
            "evidence": [f"附件 {first_image.name}"] if first_image else [],
        },
        {
            "label": "判断依据",
            "reason": "当前没有可直接支撑判断依据的结构化信息，请学生根据结果图和页面内容手动确认。",
            "evidence": [page_evidence] if page_evidence else [],
        },
    ]
    field_suggestions, missing_items = _ensure_pending_candidates(
        field_suggestions=field_suggestions,
        missing_items=missing_items,
        current_page=current_page,
    )
    return {
        "title": "Shot 结果回填建议",
        "field_suggestions": field_suggestions,
        "draft_text": answer or "== 结果摘要 ==\n* 请结合截图补充本次 Shot 记录。",
        "missing_items": missing_items,
        "evidence": [item.name for item in request.attachments],
    }


def _normalize_field_suggestions(payload: Any) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    if not isinstance(payload, dict):
        return normalized
    for key, raw_value in payload.items():
        label = str(key or "").strip()
        if not label:
            continue
        if isinstance(raw_value, dict):
            value = str(raw_value.get("value") or "").strip()
            if not value:
                continue
            normalized[label] = {
                "value": value,
                "status": str(raw_value.get("status") or "confirmed").strip() or "confirmed",
                "reason": str(raw_value.get("reason") or "").strip(),
                "evidence": [
                    str(item).strip()
                    for item in raw_value.get("evidence", [])
                    if str(item).strip()
                ] if isinstance(raw_value.get("evidence"), list) else [],
            }
            continue
        value = str(raw_value or "").strip()
        if not value:
            continue
        normalized[label] = value
    return normalized


def _normalize_missing_items(payload: Any) -> list[Any]:
    normalized: list[Any] = []
    if not isinstance(payload, list):
        return normalized
    for raw_item in payload:
        if isinstance(raw_item, dict):
            label = str(
                raw_item.get("label")
                or raw_item.get("field")
                or raw_item.get("name")
                or ""
            ).strip()
            if not label:
                continue
            item: dict[str, Any] = {"label": label}
            reason = str(raw_item.get("reason") or raw_item.get("note") or raw_item.get("message") or "").strip()
            if reason:
                item["reason"] = reason
            if isinstance(raw_item.get("evidence"), list):
                evidence = [str(entry).strip() for entry in raw_item["evidence"] if str(entry).strip()]
                if evidence:
                    item["evidence"] = evidence
            normalized.append(item)
            continue
        label = str(raw_item or "").strip()
        if label:
            normalized.append(label)
    return normalized


def prepare_shot_result_fill(
    *,
    settings: Any,
    llm,
    attachments_dir: Path,
    request: ChatRequest,
    answer: str,
    source_titles: list[str],
    conversation_history: list[dict[str, str]],
) -> dict[str, Any]:
    attachment_parts = build_attachment_prompt_parts(
        attachments_dir=attachments_dir,
        attachments=request.attachments,
    )
    if not getattr(llm.generation_provider, "enabled", False):
        return _fallback_from_page(request, answer)

    prompt = build_result_fill_prompt(
        question=request.question,
        answer=answer,
        current_page=request.context_pages[0] if request.context_pages else None,
        source_titles=source_titles,
        conversation_history=conversation_history,
        attachment_parts=attachment_parts,
    )
    try:
        raw = llm.generate_prompt(prompt)
        payload = _load_json_object(raw)
    except Exception:
        return _fallback_from_page(request, answer)
    field_suggestions = _normalize_field_suggestions(payload.get("field_suggestions"))
    missing_items = _normalize_missing_items(payload.get("missing_items"))
    field_suggestions, missing_items = _ensure_pending_candidates(
        field_suggestions=field_suggestions,
        missing_items=missing_items,
        current_page=request.context_pages[0] if request.context_pages else "",
    )
    return {
        "title": str(payload.get("title") or "Shot 结果回填建议"),
        "field_suggestions": field_suggestions,
        "draft_text": str(payload.get("draft_text") or answer or ""),
        "missing_items": missing_items,
        "evidence": [str(item).strip() for item in payload.get("evidence", []) if str(item).strip()],
    }
