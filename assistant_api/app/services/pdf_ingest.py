from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import fitz

from ..schemas import ChatRequest
from .attachments import load_attachment_file
from .prompts import build_pdf_ingest_prompt

CONTROL_MANAGED_START = "<!-- LABASSISTANT_CONTROL_START -->"
CONTROL_MANAGED_END = "<!-- LABASSISTANT_CONTROL_END -->"
CONTROL_INDEX_START = "<!-- LABASSISTANT_CONTROL_TOPIC_INDEX_START -->"
CONTROL_INDEX_END = "<!-- LABASSISTANT_CONTROL_TOPIC_INDEX_END -->"
CONTROL_OVERVIEW_PAGE = "Control:控制与运行总览"


def is_pdf_ingest_request(request: ChatRequest) -> bool:
    if (request.workflow_hint or "").strip() == "pdf_ingest_write":
        return True
    has_pdf = any(
        str(item.mime_type or "").strip().lower() == "application/pdf"
        for item in request.attachments
    )
    if not has_pdf:
        return False
    lowered = str(request.question or "").lower()
    return any(token in lowered for token in ["pdf", "手册", "写入", "区域", "归档", "提取", "文档"])


def _sanitize_file_stem(value: str) -> str:
    stem = Path(value or "pdf-ingest").stem.strip() or "pdf-ingest"
    stem = re.sub(r"[^\w\-\u4e00-\u9fff]+", "-", stem, flags=re.UNICODE).strip("-")
    return stem or "pdf-ingest"


def _normalize_line(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()


def _extract_pdf_artifacts(*, attachments_dir: Path, attachment_id: str) -> dict[str, Any]:
    item, blob_path = load_attachment_file(
        attachments_dir=attachments_dir,
        attachment_id=attachment_id,
    )
    if str(item.mime_type or "").lower() != "application/pdf":
        raise ValueError("Attachment is not a PDF document")

    file_stem = _sanitize_file_stem(item.name)
    short_id = str(item.id)[:8]
    derived_dir = attachments_dir / item.id / "pdf_ingest_pages"
    derived_dir.mkdir(parents=True, exist_ok=True)

    document = fitz.open(blob_path)
    pages: list[dict[str, Any]] = []
    text_lines: list[str] = []
    try:
        for index, page in enumerate(document, start=1):
            text = _normalize_line(page.get_text("text"))
            if text:
                text_lines.append(text)
            image_path = derived_dir / f"page-{index:02d}.png"
            if not image_path.exists():
                pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
                pix.save(image_path)
            pages.append(
                {
                    "page_number": index,
                    "text": text,
                    "image_path": image_path,
                    "wiki_file_title": f"PDF提取-{file_stem}-p{index:02d}-{short_id}.png",
                }
            )
    finally:
        document.close()

    return {
        "attachment_id": item.id,
        "file_name": item.name,
        "file_stem": file_stem,
        "page_count": len(pages),
        "combined_text": "\n".join(text_lines).strip(),
        "pages": pages,
    }


def _build_fallback_targets(file_stem: str, combined_text: str) -> list[dict[str, Any]]:
    lowered = combined_text.lower()
    control_score = 0.30
    device_score = 0.22
    literature_score = 0.08

    control_keywords = ["控制", "电机", "软件", "smc basic studio", "ip", "轴", "限位", "主控"]
    device_keywords = ["设备", "参数", "用途", "系统", "运行"]
    literature_keywords = ["doi", "abstract", "author", "年份", "journal", "paper", "论文"]

    control_hits = sum(1 for token in control_keywords if token in lowered)
    device_hits = sum(1 for token in device_keywords if token in lowered)
    literature_hits = sum(1 for token in literature_keywords if token in lowered)

    control_score += min(control_hits * 0.08, 0.56)
    device_score += min(device_hits * 0.06, 0.30)
    literature_score += min(literature_hits * 0.05, 0.20)

    targets = [
        {
            "target_type": "control",
            "target_title": f"Control:{file_stem}",
            "score": round(min(control_score, 0.96), 2),
            "reason": "文档包含控制软件、控制器 IP、轴使能或限位等操作信息，更像控制/运行手册。",
        },
        {
            "target_type": "device_entry",
            "target_title": f"设备条目/{file_stem}",
            "score": round(min(device_score, 0.88), 2),
            "reason": "文档也包含设备名称、系统用途和关键参数，可作为设备条目补充来源。",
        },
        {
            "target_type": "literature_guide",
            "target_title": f"文献导读/{file_stem}",
            "score": round(min(literature_score, 0.42), 2),
            "reason": "只有在文档具备作者、年份、DOI 等学术元信息时才适合写入文献导读。",
        },
    ]
    return sorted(targets, key=lambda item: float(item.get("score") or 0.0), reverse=True)


def _build_fallback_summary(file_name: str, combined_text: str) -> str:
    summary_parts: list[str] = [f"《{file_name}》更像一份设备控制/操作手册。"]
    lowered = combined_text.lower()
    if "smc basic studio" in lowered:
        summary_parts.append("文档明确提到需要打开 SMC Basic Studio 控制软件。")
    if "128" in lowered and "ip" in lowered:
        summary_parts.append("其中包含将控制器 IP 调整为 128 的配置步骤。")
    if "轴" in combined_text or "使所有轴能开" in combined_text:
        summary_parts.append("还整理了各轴使能相关操作。")
    if "限位" in combined_text:
        summary_parts.append("文档中带有限位和操作注意事项。")
    return "".join(summary_parts)


def _extract_numbered_lines(combined_text: str) -> list[str]:
    candidates = re.findall(
        r"(?:^|[\s])(\d+[.、]\s*.*?)(?=(?:\s+\d+[.、])|$)",
        combined_text,
        flags=re.S,
    )
    cleaned = [_normalize_line(item) for item in candidates if _normalize_line(item)]
    return list(dict.fromkeys(cleaned))


def _build_fallback_sections(combined_text: str) -> list[dict[str, str]]:
    numbered = _extract_numbered_lines(combined_text)
    control_lines = [
        _normalize_line(line)
        for line in re.findall(r"[^。；;\n]*(?:SMC Basic Studio|IP|控制器|轴|限位)[^。；;\n]*", combined_text, flags=re.IGNORECASE)
        if _normalize_line(line)
    ]
    note_lines = [
        _normalize_line(line)
        for line in re.findall(r"[^。；;\n]*(?:注意|限位)[^。；;\n]*", combined_text)
        if _normalize_line(line)
    ]

    sections: list[dict[str, str]] = []
    if numbered:
        sections.append({
            "title": "操作步骤",
            "content": "\n".join(f"- {item}" for item in numbered[:8]),
        })
    if control_lines:
        sections.append({
            "title": "关键参数与软件",
            "content": "\n".join(f"- {item}" for item in list(dict.fromkeys(control_lines))[:8]),
        })
    if note_lines:
        sections.append({
            "title": "注意事项",
            "content": "\n".join(f"- {item}" for item in list(dict.fromkeys(note_lines))[:6]),
        })
    if not sections:
        sections.append({
            "title": "文档摘要",
            "content": _normalize_line(combined_text)[:800],
        })
    return sections


def _load_json_object(raw: str) -> dict[str, Any]:
    candidate = str(raw or "").strip()
    if candidate.startswith("```"):
        candidate = "\n".join(
            line for line in candidate.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    return json.loads(candidate)


def _iter_control_target(review: dict[str, Any]) -> dict[str, Any] | None:
    for item in review.get("recommended_targets") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("target_type") or "").strip() != "control":
            continue
        title = str(item.get("target_title") or "").strip()
        if title.startswith("Control:"):
            return item
    return None


def _sanitize_control_section_title(value: str) -> str:
    title = _normalize_line(value) or "未命名章节"
    return re.sub(r"[=]+", "", title).strip() or "未命名章节"


def _sensitive_reason_for_line(line: str) -> str | None:
    text = _normalize_line(line)
    lowered = text.lower()
    if not text:
        return None
    if any(token in lowered for token in ["密码", "口令", "password"]):
        return "包含密码或口令信息，应只在受限页人工维护。"
    if any(token in lowered for token in ["账号", "用户名", "user name", "username", "login"]):
        return "包含账号或登录信息，应只在受限页人工维护。"
    if re.search(r"https?://", lowered):
        return "包含下载或访问地址，应转到受限页人工维护。"
    if re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", lowered):
        return "包含完整网络地址，应转到受限页人工维护。"
    if "安装包" in text:
        return "包含安装包位置，应转到受限页人工维护。"
    return None


def _filter_section_content(title: str, content: str) -> tuple[str, list[dict[str, str]]]:
    safe_lines: list[str] = []
    blocked_items: list[dict[str, str]] = []
    blocked_lines: list[str] = []
    blocked_reason = ""
    for raw_line in str(content or "").splitlines():
        line = _normalize_line(raw_line)
        if not line:
            continue
        reason = _sensitive_reason_for_line(line)
        if reason:
            blocked_reason = blocked_reason or reason
            blocked_lines.append(line)
            continue
        safe_lines.append(line)
    if blocked_lines:
        blocked_items.append({
            "label": _sanitize_control_section_title(title),
            "reason": blocked_reason or "包含受限信息，应转到受限页人工维护。",
            "content": "\n".join(blocked_lines),
        })
    return "\n".join(safe_lines), blocked_items


def _build_control_page_content(
    *,
    draft_page: str,
    file_name: str,
    target_page: str,
    document_summary: str,
    section_outline: list[dict[str, str]],
    evidence: list[str],
    image_items: list[dict[str, Any]],
) -> tuple[str, list[dict[str, str]]]:
    blocked_items: list[dict[str, str]] = []
    lines = [
        CONTROL_MANAGED_START,
        f"= {target_page} =",
        "",
        "== 页面定位 ==",
        "由知识助手从 PDF 手册整理的控制专题页，保留可公开维护的操作说明和软件信息。",
        "",
        "== 文档来源 ==",
        f"* 原始文件：{file_name}",
        f"* 来源草稿：[[{draft_page}]]",
        f"* 总览入口：[[{CONTROL_OVERVIEW_PAGE}]]",
    ]
    for item in evidence[:4]:
        normalized = _normalize_line(item)
        if normalized:
            lines.append(f"* 证据：{normalized}")
    lines.extend([
        "",
        "== 文档摘要 ==",
        _normalize_line(document_summary),
        "",
    ])

    for section in section_outline:
        title = _sanitize_control_section_title(str(section.get("title") or ""))
        content = str(section.get("content") or "")
        filtered_content, blocked = _filter_section_content(title, content)
        blocked_items.extend(blocked)
        if not filtered_content:
            continue
        lines.extend([
            f"== {title} ==",
            filtered_content,
            "",
        ])

    lines.append("== 原文页图 ==")
    for item in image_items:
        file_title = str(item.get("file_title") or "").strip()
        page_number = item.get("page_number")
        if not file_title:
            continue
        lines.append(f"[[File:{file_title}|center|thumb|第 {page_number} 页]]")

    lines.extend([
        "",
        "== 相关页面 ==",
        f"* [[{CONTROL_OVERVIEW_PAGE}]]",
        f"* [[{draft_page}]]",
        CONTROL_MANAGED_END,
    ])
    return "\n".join(lines).strip(), blocked_items


def _build_control_overview_content(existing_text: str, *, target_page: str, summary: str) -> str:
    entry_line = f"* [[{target_page}]]：{_normalize_line(summary)[:120]}"
    managed_block = "\n".join([
        CONTROL_INDEX_START,
        "== 助手整理专题 ==",
        entry_line,
        CONTROL_INDEX_END,
    ])
    current = str(existing_text or "").strip()
    pattern = re.compile(
        rf"{re.escape(CONTROL_INDEX_START)}.*?{re.escape(CONTROL_INDEX_END)}",
        flags=re.S,
    )
    if pattern.search(current):
        return pattern.sub(managed_block, current)
    if current:
        return current.rstrip() + "\n\n" + managed_block
    return managed_block


def _build_prompt_page_parts(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for page in pages[:3]:
        image_bytes = page["image_path"].read_bytes()
        parts.append({
            "type": "text",
            "text": f"PDF 第 {page['page_number']} 页渲染图",
        })
        parts.append({
            "type": "image",
            "mime_type": "image/png",
            "data": base64.b64encode(image_bytes).decode("ascii"),
        })
    return parts


def _normalize_review_payload(payload: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    def canonical_target_title(target_type: str, raw_title: str) -> str:
        title = str(raw_title or "").strip()
        if not title:
            return ""
        if target_type == "control" and not title.startswith("Control:"):
            return f"Control:{title}"
        if target_type == "device_entry" and not title.startswith("设备条目/"):
            return f"设备条目/{title}"
        if target_type == "literature_guide" and not title.startswith("文献导读/"):
            return f"文献导读/{title}"
        return title

    recommended_targets: list[dict[str, Any]] = []
    for item in payload.get("recommended_targets") or []:
        if not isinstance(item, dict):
            continue
        target_type = str(item.get("target_type") or "").strip()
        target_title = canonical_target_title(
            target_type,
            str(item.get("target_title") or "").strip(),
        )
        if not target_type or not target_title:
            continue
        normalized = {
            "target_type": target_type,
            "target_title": target_title,
            "reason": str(item.get("reason") or "").strip(),
        }
        try:
            if item.get("score") is not None:
                normalized["score"] = float(item.get("score"))
        except Exception:
            pass
        recommended_targets.append(normalized)

    section_outline: list[dict[str, str]] = []
    for item in payload.get("section_outline") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        if not title or not content:
            continue
        section_outline.append({"title": title, "content": content})

    return {
        "title": str(payload.get("title") or "PDF 解析与写入建议"),
        "source_attachment_id": artifacts["attachment_id"],
        "file_name": artifacts["file_name"],
        "document_summary": str(payload.get("document_summary") or "").strip(),
        "recommended_targets": recommended_targets,
        "proposed_draft_title": str(payload.get("proposed_draft_title") or "").strip(),
        "section_outline": section_outline,
        "extracted_page_count": int(payload.get("extracted_page_count") or artifacts["page_count"]),
        "staged_image_count": int(payload.get("staged_image_count") or len(artifacts["pages"])),
        "evidence": [
            str(item).strip()
            for item in payload.get("evidence", [])
            if str(item).strip()
        ],
        "needs_confirmation": bool(payload.get("needs_confirmation", True)),
    }


def _build_fallback_review(*, artifacts: dict[str, Any]) -> dict[str, Any]:
    targets = _build_fallback_targets(artifacts["file_stem"], artifacts["combined_text"])
    summary = _build_fallback_summary(artifacts["file_name"], artifacts["combined_text"])
    sections = _build_fallback_sections(artifacts["combined_text"])
    return {
        "title": "PDF 解析与写入建议",
        "source_attachment_id": artifacts["attachment_id"],
        "file_name": artifacts["file_name"],
        "document_summary": summary,
        "recommended_targets": targets,
        "proposed_draft_title": f"知识助手草稿/PDF提取/{artifacts['file_stem']}",
        "section_outline": sections,
        "extracted_page_count": artifacts["page_count"],
        "staged_image_count": len(artifacts["pages"]),
        "evidence": [
            f"PDF 文件：{artifacts['file_name']}",
            f"共 {artifacts['page_count']} 页",
        ],
        "needs_confirmation": True,
    }


def prepare_pdf_ingest_review(
    *,
    settings: Any,
    llm,
    attachments_dir: Path,
    request: ChatRequest,
) -> dict[str, Any]:
    pdf_attachment = next(
        (
            item
            for item in request.attachments
            if str(item.mime_type or "").strip().lower() == "application/pdf"
        ),
        None,
    )
    if pdf_attachment is None:
        raise ValueError("当前请求缺少 PDF 附件")

    artifacts = _extract_pdf_artifacts(
        attachments_dir=attachments_dir,
        attachment_id=pdf_attachment.id,
    )
    fallback_payload = _build_fallback_review(artifacts=artifacts)

    if not getattr(getattr(llm, "generation_provider", None), "enabled", False):
        return fallback_payload

    prompt = build_pdf_ingest_prompt(
        question=request.question,
        current_page=request.context_pages[0] if request.context_pages else None,
        file_name=artifacts["file_name"],
        page_count=artifacts["page_count"],
        extracted_text=artifacts["combined_text"][:6000],
        page_prompt_parts=_build_prompt_page_parts(artifacts["pages"]),
    )
    try:
        raw = llm.generate_prompt(prompt)
        payload = _normalize_review_payload(_load_json_object(raw), artifacts)
    except Exception:
        return fallback_payload

    if not payload["document_summary"]:
        payload["document_summary"] = fallback_payload["document_summary"]
    if not payload["recommended_targets"]:
        payload["recommended_targets"] = fallback_payload["recommended_targets"]
    if not payload["section_outline"]:
        payload["section_outline"] = fallback_payload["section_outline"]
    if not payload["proposed_draft_title"]:
        payload["proposed_draft_title"] = fallback_payload["proposed_draft_title"]
    if not payload["evidence"]:
        payload["evidence"] = fallback_payload["evidence"]
    payload["needs_confirmation"] = True
    return payload


def prepare_pdf_draft_preview(
    *,
    settings: Any,
    attachments_dir: Path,
    attachment_id: str,
    review: dict[str, Any],
) -> dict[str, Any]:
    artifacts = _extract_pdf_artifacts(
        attachments_dir=attachments_dir,
        attachment_id=attachment_id,
    )
    normalized_review = review if review.get("source_attachment_id") else _build_fallback_review(artifacts=artifacts)
    target_page = str(
        normalized_review.get("proposed_draft_title")
        or f"{settings.draft_prefix}/PDF提取/{artifacts['file_stem']}"
    ).strip()
    if not target_page.startswith(f"{settings.draft_prefix}/"):
        target_page = f"{settings.draft_prefix}/PDF提取/{artifacts['file_stem']}"

    recommended_targets = normalized_review.get("recommended_targets") or []
    primary_target = recommended_targets[0]["target_title"] if recommended_targets else f"Control:{artifacts['file_stem']}"
    secondary_target = recommended_targets[1]["target_title"] if len(recommended_targets) > 1 else ""

    lines = [
        "== 文档基本信息 ==",
        f"* 原始文件：{artifacts['file_name']}",
        f"* 页数：{artifacts['page_count']}",
        f"* 建议正式归档区域：{primary_target}",
    ]
    if secondary_target:
        lines.append(f"* 次选区域：{secondary_target}")
    lines.extend([
        "",
        "== 文档摘要 ==",
        str(normalized_review.get("document_summary") or "").strip() or _build_fallback_summary(artifacts["file_name"], artifacts["combined_text"]),
        "",
        "== 建议拆分写入 ==",
    ])
    for item in recommended_targets[:3]:
        reason = str(item.get("reason") or "").strip()
        line = f"* {item['target_title']}"
        if reason:
            line += f"：{reason}"
        lines.append(line)

    lines.extend(["", "== 章节整理 =="])
    for section in normalized_review.get("section_outline") or []:
        title = str(section.get("title") or "").strip()
        content = str(section.get("content") or "").strip()
        if not title or not content:
            continue
        lines.extend([f"=== {title} ===", content, ""])

    lines.append("== 全部页图 ==")
    image_metadata: list[dict[str, Any]] = []
    for page in artifacts["pages"]:
        lines.append(f"[[File:{page['wiki_file_title']}|center|thumb|第 {page['page_number']} 页]]")
        image_metadata.append(
            {
                "file_title": page["wiki_file_title"],
                "blob_path": str(page["image_path"]),
                "mime_type": "image/png",
                "page_number": page["page_number"],
            }
        )

    return {
        "title": artifacts["file_stem"],
        "target_page": target_page,
        "content": "\n".join(lines).strip(),
        "metadata_json": {
            "kind": "pdf_ingest_draft",
            "source_attachment_id": artifacts["attachment_id"],
            "file_name": artifacts["file_name"],
            "document_summary": normalized_review.get("document_summary") or "",
            "recommended_targets": recommended_targets,
            "review_snapshot": normalized_review,
            "pdf_ingest_images": image_metadata,
        },
    }


def prepare_pdf_control_preview(*, wiki, draft_preview) -> dict[str, Any]:
    metadata = draft_preview.metadata_json or {}
    if metadata.get("kind") != "pdf_ingest_draft":
        raise ValueError("当前草稿不是 PDF 摄取草稿")

    review = metadata.get("review_snapshot") or {}
    control_target = _iter_control_target(review)
    if control_target is None:
        raise ValueError("当前草稿没有可写入的 Control 正式页目标")

    target_page = str(control_target.get("target_title") or "").strip()
    if not target_page.startswith("Control:"):
        raise ValueError("Control 正式页标题不合法")

    overview_page = CONTROL_OVERVIEW_PAGE
    existing_target_text = wiki.get_page_text(target_page)
    existing_overview_text = wiki.get_page_text(overview_page)
    content, blocked_items = _build_control_page_content(
        draft_page=str(draft_preview.target_page or "").strip(),
        file_name=str(review.get("file_name") or metadata.get("file_name") or draft_preview.title or "").strip(),
        target_page=target_page,
        document_summary=str(review.get("document_summary") or metadata.get("document_summary") or "").strip(),
        section_outline=list(review.get("section_outline") or []),
        evidence=list(review.get("evidence") or []),
        image_items=list(metadata.get("pdf_ingest_images") or []),
    )
    overview_content = _build_control_overview_content(
        existing_overview_text,
        target_page=target_page,
        summary=str(review.get("document_summary") or metadata.get("document_summary") or target_page),
    )
    operation = "update" if existing_target_text.strip() else "create"
    return {
        "title": target_page,
        "target_page": target_page,
        "overview_page": overview_page,
        "content": content,
        "overview_update": overview_content,
        "blocked_items": blocked_items,
        "metadata_json": {
            "kind": "pdf_control_formal_preview",
            "operation": operation,
            "overview_page": overview_page,
            "overview_content": overview_content,
            "blocked_items": blocked_items,
            "source_draft_page": draft_preview.target_page,
            "source_file_name": str(review.get("file_name") or metadata.get("file_name") or ""),
        },
    }


def commit_pdf_control_preview(*, wiki, preview) -> dict[str, Any]:
    metadata = preview.metadata_json or {}
    if metadata.get("kind") != "pdf_control_formal_preview":
        raise ValueError("当前预览不是 PDF Control 正式写入预览")
    overview_page = str(metadata.get("overview_page") or CONTROL_OVERVIEW_PAGE).strip() or CONTROL_OVERVIEW_PAGE
    overview_content = str(metadata.get("overview_content") or "").strip()
    if not preview.target_page.startswith("Control:"):
        raise ValueError("正式写入目标页不在 Control: 命名空间")
    if not overview_content:
        raise ValueError("缺少 Control 总览页更新内容")
    wiki.edit_page(
        preview.target_page,
        preview.content,
        "Create assistant Control topic from PDF draft",
    )
    wiki.edit_page(
        overview_page,
        overview_content,
        "Update Control overview topic links from assistant PDF draft",
    )
    return {
        "status": "ok",
        "page_title": preview.target_page,
        "overview_page": overview_page,
        "blocked_count": len(metadata.get("blocked_items") or []),
    }


def commit_pdf_ingest_draft_preview(*, wiki, preview) -> None:
    metadata = preview.metadata_json or {}
    image_items = metadata.get("pdf_ingest_images") or []
    for item in image_items:
        blob_path = Path(str(item.get("blob_path") or ""))
        if not blob_path.exists():
            raise FileNotFoundError(f"Missing staged PDF page image: {blob_path}")
        wiki.upload_file(
            str(item.get("file_title") or blob_path.name),
            blob_path.read_bytes(),
            "Assistant extracted PDF page image",
            content_type=str(item.get("mime_type") or "image/png"),
        )
    wiki.edit_page(
        preview.target_page,
        preview.content,
        "Create assistant PDF ingestion draft",
    )
