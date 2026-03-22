from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..clients.tools import ToolClients
from ..clients.wiki import MediaWikiClient
from ..config import Settings
from ..models import DraftPreview
from .audit import log_audit
from .drafts import create_draft_preview
from .llm import LLMClient
from .write_actions import commit_write_preview, create_write_preview


def _provider(
    *,
    provider_id: str,
    label: str,
    available: bool,
    transport: str,
    description: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": provider_id,
        "label": label,
        "available": available,
        "transport": transport,
        "description": description,
        "metadata": metadata or {},
    }


def _capability(
    *,
    capability_id: str,
    label: str,
    provider: str,
    mode: str,
    description: str,
    requires_confirmation: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": capability_id,
        "label": label,
        "provider": provider,
        "mode": mode,
        "description": description,
        "requires_confirmation": requires_confirmation,
        "metadata": metadata or {},
    }


def _discover_opencli_commands() -> tuple[bool, str | None, list[dict[str, Any]]]:
    binary = shutil.which("opencli")
    if not binary:
        return False, None, []

    commands: list[dict[str, Any]] = []
    attempts = [
        [binary, "list", "--format", "json"],
        [binary, "list", "-f", "json"],
    ]
    for command in attempts:
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            continue
        items = payload if isinstance(payload, list) else payload.get("data", [])
        if not isinstance(items, list):
            continue
        for item in items[:100]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("id") or "").strip()
            if not name:
                continue
            commands.append(
                _capability(
                    capability_id=f"opencli.{name}",
                    label=name,
                    provider="opencli",
                    mode="read",
                    description=str(item.get("description") or "OpenCLI discovered command"),
                    metadata={"command": name, "discovered": True},
                )
            )
        break

    if not commands:
        commands.append(
            _capability(
                capability_id="opencli.command",
                label="OpenCLI command",
                provider="opencli",
                mode="read",
                description="Execute a read-only OpenCLI command that reuses the local browser session.",
                metadata={"discovered": False},
            )
        )
    return True, binary, commands


def build_capability_catalog(settings: Settings) -> dict[str, Any]:
    opencli_available, opencli_binary, opencli_commands = _discover_opencli_commands()
    providers = [
        _provider(
            provider_id="local_knowledge",
            label="Local Knowledge",
            available=True,
            transport="internal",
            description="Wiki, cargo, session context, drafts, and structured write previews.",
        ),
        _provider(
            provider_id="native_cli",
            label="Native CLI",
            available=True,
            transport="http",
            description="Direct TPS/RCF read-only tool bridge.",
        ),
        _provider(
            provider_id="opencli",
            label="OpenCLI",
            available=opencli_available,
            transport="cli",
            description="Read-only browser and Electron application bridge via local OpenCLI.",
            metadata={"binary": opencli_binary},
        ),
        _provider(
            provider_id="mcp",
            label="MCP",
            available=False,
            transport="planned",
            description="Reserved provider slot for MCP-backed capabilities.",
        ),
    ]
    capabilities = [
        _capability(
            capability_id="draft.prepare",
            label="Prepare draft preview",
            provider="local_knowledge",
            mode="preview",
            description="Generate a wiki draft preview from the current answer and sources.",
            requires_confirmation=True,
        ),
        _capability(
            capability_id="draft.commit",
            label="Commit draft preview",
            provider="local_knowledge",
            mode="commit",
            description="Commit a previously generated draft preview into the draft namespace.",
            requires_confirmation=True,
        ),
        _capability(
            capability_id="write.prepare",
            label="Prepare structured write preview",
            provider="local_knowledge",
            mode="preview",
            description="Generate a structured write preview for whitelisted wiki pages.",
            requires_confirmation=True,
        ),
        _capability(
            capability_id="write.commit",
            label="Commit structured write preview",
            provider="local_knowledge",
            mode="commit",
            description="Commit a previously generated structured write preview.",
            requires_confirmation=True,
        ),
        _capability(
            capability_id="tool.tps.health",
            label="TPS health",
            provider="native_cli",
            mode="read",
            description="Read-only TPS health check.",
        ),
        _capability(
            capability_id="tool.rcf.health",
            label="RCF health",
            provider="native_cli",
            mode="read",
            description="Read-only RCF health check.",
        ),
    ]
    capabilities.extend(opencli_commands)
    return {"providers": providers, "capabilities": capabilities}


def _coerce_preview_payload(preview: Any) -> dict[str, Any]:
    if isinstance(preview, dict):
        return preview
    metadata = getattr(preview, "metadata_json", None)
    return {
        "preview_id": getattr(preview, "id"),
        "title": getattr(preview, "title", ""),
        "target_page": getattr(preview, "target_page", ""),
        "content": getattr(preview, "content", ""),
        "metadata": metadata,
    }


def preview_capability_action(
    *,
    db: Session | None,
    settings: Settings,
    llm: LLMClient | None,
    wiki: MediaWikiClient | None,
    tools: ToolClients | None,
    action_id: str,
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    if action_id == "draft.prepare":
        preview = create_draft_preview(
            db,
            settings,
            llm,
            session_id=request_payload.get("session_id"),
            turn_id=request_payload.get("turn_id"),
            question=request_payload["question"],
            answer=request_payload["answer"],
            source_titles=request_payload.get("source_titles", []),
            conversation_history=request_payload.get("conversation_history", []),
        )
        payload = _coerce_preview_payload(preview)
        return {
            "status": "preview_ready",
            "provider": "local_knowledge",
            "action_id": action_id,
            "preview_kind": "draft",
            "requires_confirmation": True,
            "preview": payload,
            "result": None,
        }

    if action_id == "write.prepare":
        preview = create_write_preview(
            db,
            settings,
            llm,
            wiki,
            session_id=request_payload.get("session_id"),
            turn_id=request_payload.get("turn_id"),
            question=request_payload["question"],
            answer=request_payload.get("answer", ""),
            source_titles=request_payload.get("source_titles", []),
            current_page=(request_payload.get("context_pages") or [None])[0],
            conversation_history=request_payload.get("conversation_history", []),
        )
        metadata = getattr(preview, "metadata_json", {}) or {}
        return {
            "status": "preview_ready",
            "provider": "local_knowledge",
            "action_id": action_id,
            "preview_kind": "write",
            "requires_confirmation": True,
            "preview": {
                "preview_id": getattr(preview, "id"),
                "action_type": metadata.get("action_type", ""),
                "operation": metadata.get("operation", ""),
                "target_page": getattr(preview, "target_page"),
                "preview_text": getattr(preview, "content"),
                "structured_payload": metadata.get("structured_payload") or {},
                "missing_fields": metadata.get("missing_fields", []),
                "metadata": metadata,
            },
            "result": None,
        }

    if action_id == "tool.tps.health":
        result = tools.tps_execute("health", {})
        return {
            "status": "completed",
            "provider": "native_cli",
            "action_id": action_id,
            "preview_kind": "read_result",
            "requires_confirmation": False,
            "preview": None,
            "result": result,
        }

    if action_id == "tool.rcf.health":
        result = tools.rcf_execute("health", {})
        return {
            "status": "completed",
            "provider": "native_cli",
            "action_id": action_id,
            "preview_kind": "read_result",
            "requires_confirmation": False,
            "preview": None,
            "result": result,
        }

    if action_id.startswith("opencli."):
        return {
            "status": "preview_ready",
            "provider": "opencli",
            "action_id": action_id,
            "preview_kind": "external_read",
            "requires_confirmation": False,
            "preview": {
                "command": request_payload.get("command") or action_id.removeprefix("opencli."),
                "note": "OpenCLI integration is registered as read-only in this phase.",
            },
            "result": None,
        }

    raise ValueError(f"Unsupported capability action: {action_id}")


def commit_capability_action(
    *,
    db: Session | None,
    settings: Settings,
    wiki: MediaWikiClient | None,
    action_id: str,
    request_payload: dict[str, Any],
    preview_loader: Any = None,
) -> dict[str, Any]:
    load_preview = preview_loader or (lambda inner_db, preview_id: inner_db.get(DraftPreview, preview_id))
    preview_id = request_payload.get("preview_id")
    if not preview_id:
        raise ValueError("preview_id is required for commit actions")

    preview = load_preview(db, preview_id)
    if preview is None:
        raise ValueError("Preview not found")

    if action_id == "write.commit":
        result = commit_write_preview(db, wiki, preview=preview)
        return {
            "status": result.get("status", "ok"),
            "result_kind": "write",
            "action_id": action_id,
            "result": result,
        }

    if action_id == "draft.commit":
        expected_prefix = f"{settings.draft_prefix}/"
        if not getattr(preview, "target_page", "").startswith(expected_prefix):
            raise ValueError("Draft preview target page is outside the draft prefix")
        wiki.edit_page(
            preview.target_page,
            preview.content,
            "Create assistant draft preview",
        )
        result = {
            "status": "ok",
            "page_title": preview.target_page,
            "preview_id": preview.id,
        }
        log_audit(
            db,
            session_id=getattr(preview, "session_id", None),
            turn_id=getattr(preview, "turn_id", None),
            action_type="draft_commit",
            payload=result,
        )
        return {
            "status": "ok",
            "result_kind": "draft",
            "action_id": action_id,
            "result": result,
        }

    raise ValueError(f"Unsupported capability commit action: {action_id}")
