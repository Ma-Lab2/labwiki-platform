from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog


def log_audit(
    db: Session,
    *,
    action_type: str,
    payload: dict[str, Any] | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
) -> None:
    db.add(
        AuditLog(
            session_id=session_id,
            turn_id=turn_id,
            action_type=action_type,
            payload=payload or {},
        )
    )
