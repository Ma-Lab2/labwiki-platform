from __future__ import annotations

import re

from sqlalchemy.orm import Session

from ..config import Settings
from ..models import DraftPreview
from .audit import log_audit
from .llm import LLMClient


def _sanitize_title(text: str) -> str:
    cleaned = re.sub(r"[\[\]#<>|{}]", " ", text).strip()
    return re.sub(r"\s+", " ", cleaned)[:80] or "知识助手草稿"


def prepare_draft_preview(
    settings: Settings,
    llm: LLMClient,
    *,
    question: str,
    answer: str,
    source_titles: list[str],
) -> dict[str, object]:
    draft = llm.draft_from_answer(
        question=question,
        answer=answer,
        source_titles=source_titles,
        draft_prefix=settings.draft_prefix,
    )
    title = _sanitize_title(draft["title"])
    target_page = f"{settings.draft_prefix}/{title}"
    return {
        "title": title,
        "target_page": target_page,
        "content": draft["content"],
        "metadata_json": {"source_titles": source_titles},
    }


def create_draft_preview(
    db: Session,
    settings: Settings,
    llm: LLMClient,
    *,
    session_id: str | None,
    turn_id: str | None,
    question: str,
    answer: str,
    source_titles: list[str],
) -> DraftPreview:
    prepared = prepare_draft_preview(
        settings,
        llm,
        question=question,
        answer=answer,
        source_titles=source_titles,
    )
    return save_draft_preview(
        db,
        session_id=session_id,
        turn_id=turn_id,
        title=prepared["title"],  # type: ignore[arg-type]
        target_page=prepared["target_page"],  # type: ignore[arg-type]
        content=prepared["content"],  # type: ignore[arg-type]
        metadata_json=prepared["metadata_json"],  # type: ignore[arg-type]
    )


def save_draft_preview(
    db: Session,
    *,
    session_id: str | None,
    turn_id: str | None,
    title: str,
    target_page: str,
    content: str,
    metadata_json: dict | None = None,
) -> DraftPreview:
    preview = DraftPreview(
        session_id=session_id,
        turn_id=turn_id,
        title=title,
        target_page=target_page,
        content=content,
        metadata_json=metadata_json,
    )
    db.add(preview)
    db.flush()
    log_audit(
        db,
        action_type="draft_preview",
        session_id=session_id,
        turn_id=turn_id,
        payload={"preview_id": preview.id, "target_page": preview.target_page},
    )
    return preview
