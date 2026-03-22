from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

from ..schemas import AttachmentItem


ALLOWED_ATTACHMENT_MIME_TYPES: dict[str, str] = {
    "image/png": "image",
    "image/jpeg": "image",
    "image/webp": "image",
    "application/pdf": "document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
    "text/plain": "document",
    "text/markdown": "document",
}


class AttachmentStorageError(ValueError):
    pass


def _sanitize_filename(filename: str) -> str:
    candidate = Path(filename or "attachment").name.strip() or "attachment"
    sanitized = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "-", candidate).strip("-.")
    return sanitized or "attachment"


def store_attachment(
    *,
    attachments_dir: Path,
    filename: str,
    content_type: str,
    content: bytes,
) -> AttachmentItem:
    mime_type = (content_type or "").split(";")[0].strip().lower()
    kind = ALLOWED_ATTACHMENT_MIME_TYPES.get(mime_type)
    if not kind:
        raise AttachmentStorageError(f"Unsupported attachment type: {content_type or 'unknown'}")
    attachment_id = str(uuid.uuid4())
    attachment_name = _sanitize_filename(filename)
    target_dir = attachments_dir / attachment_id
    target_dir.mkdir(parents=True, exist_ok=False)
    blob_path = target_dir / "blob"
    blob_path.write_bytes(content)
    payload = AttachmentItem(
        id=attachment_id,
        kind=kind,
        name=attachment_name,
        mime_type=mime_type,
        size_bytes=len(content),
    )
    (target_dir / "meta.json").write_text(
        json.dumps(payload.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def delete_attachment(*, attachments_dir: Path, attachment_id: str) -> bool:
    target_dir = attachments_dir / attachment_id
    if not target_dir.exists():
        return False
    shutil.rmtree(target_dir)
    return True


def build_attachment_evidence(attachments: list[AttachmentItem]) -> list[dict[str, str | float | None]]:
    evidence: list[dict[str, str | float | None]] = []
    for item in attachments:
        evidence.append(
            {
                "source_type": "attachment",
                "source_id": item.id,
                "title": item.name,
                "url": None,
                "snippet": f"{item.kind} · {item.mime_type} · {item.size_bytes} bytes",
                "content": f"用户附加了一个{item.kind}：{item.name}（{item.mime_type}，{item.size_bytes} bytes）。当前轮次只能使用附件元信息，不直接解析内容。",
                "score": 1.9,
            }
        )
    return evidence
