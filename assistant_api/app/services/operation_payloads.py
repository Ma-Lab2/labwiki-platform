from __future__ import annotations

from typing import Any

from ..schemas import (
    DraftPreviewPayload,
    OperationPreviewPayload,
    OperationResultPayload,
    ResultFillPayload,
    WritePreviewPayload,
    WriteResultPayload,
)


def _write_preview_kind(action_type: str | None) -> str:
    if action_type == "update_managed_page_section":
        return "managed_section_edit"
    return "structured_write"


def _write_result_kind(action_type: str | None) -> str:
    if action_type == "update_managed_page_section":
        return "managed_section_edit"
    return "write_action"


def derive_operation_preview(
    *,
    draft_preview: DraftPreviewPayload | None = None,
    write_preview: WritePreviewPayload | None = None,
    result_fill: ResultFillPayload | None = None,
) -> OperationPreviewPayload | None:
    if write_preview is not None:
        return OperationPreviewPayload(
            preview_id=write_preview.preview_id,
            kind=_write_preview_kind(write_preview.action_type),
            operation=write_preview.operation,
            target_page=write_preview.target_page,
            target_section=write_preview.target_section,
            title=write_preview.target_page or "写入预览",
            content=write_preview.preview_text,
            structured_payload=write_preview.structured_payload,
            missing_fields=list(write_preview.missing_fields or []),
            metadata=write_preview.metadata,
        )
    if draft_preview is not None:
        metadata = draft_preview.metadata if isinstance(draft_preview.metadata, dict) else {}
        return OperationPreviewPayload(
            preview_id=draft_preview.preview_id,
            kind="draft_page",
            operation="replace_page_body",
            target_page=draft_preview.target_page,
            target_section=None,
            title=draft_preview.title or draft_preview.target_page or "页面草稿",
            content=draft_preview.content,
            structured_payload=metadata.get("structured_payload") or {},
            missing_fields=list(metadata.get("missing_fields") or []),
            metadata=metadata,
        )
    if result_fill is not None:
        return OperationPreviewPayload(
            preview_id=None,
            kind="shot_result_fill",
            operation="fill",
            target_page=None,
            target_section=None,
            title=result_fill.title or "结果回填建议",
            content=result_fill.draft_text,
            structured_payload={
                "field_suggestions": result_fill.field_suggestions,
                "missing_items": [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in result_fill.missing_items
                ],
                "evidence": list(result_fill.evidence or []),
            },
            missing_fields=[],
            metadata=None,
        )
    return None


def derive_operation_result(
    *,
    write_result: WriteResultPayload | None = None,
    draft_commit_result: dict[str, Any] | None = None,
) -> OperationResultPayload | None:
    if write_result is not None:
        return OperationResultPayload(
            status=write_result.status,
            kind=_write_result_kind(write_result.action_type),
            operation=write_result.operation,
            page_title=write_result.page_title,
            target_section=write_result.target_section,
            detail=write_result.detail,
            metadata={
                "action_type": write_result.action_type,
            } if write_result.action_type else None,
        )
    if draft_commit_result is not None:
        return OperationResultPayload(
            status=str(draft_commit_result.get("status") or "success"),
            kind="draft_page",
            operation="replace_page_body",
            page_title=str(draft_commit_result.get("page_title") or ""),
            target_section=None,
            detail=str(draft_commit_result.get("detail") or "草稿页已写入。"),
            metadata=draft_commit_result,
        )
    return None
