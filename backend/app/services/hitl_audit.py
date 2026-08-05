"""Append-only HITL audit trail for pharmacist field edits and confirms."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hitl_audit import HitlAuditEvent


def record_hitl_event(
    db: Session,
    *,
    session_id: str,
    pharmacist_user_id: str,
    event_type: str,
    medicine_id: str | None = None,
    field_name: str | None = None,
    payload: dict[str, Any] | None = None,
    commit: bool = False,
) -> HitlAuditEvent:
    row = HitlAuditEvent(
        session_id=session_id,
        medicine_id=medicine_id,
        pharmacist_user_id=pharmacist_user_id,
        event_type=event_type,
        field_name=field_name,
        payload_json=json.dumps(payload or {}, default=str),
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


def list_session_hitl_events(
    db: Session,
    session_id: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(HitlAuditEvent)
            .where(HitlAuditEvent.session_id == session_id)
            .order_by(HitlAuditEvent.created_at.desc())
            .limit(max(1, min(limit, 500)))
        )
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            payload = json.loads(r.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {"raw": r.payload_json}
        out.append(
            {
                "id": r.id,
                "session_id": r.session_id,
                "medicine_id": r.medicine_id,
                "pharmacist_user_id": r.pharmacist_user_id,
                "event_type": r.event_type,
                "field_name": r.field_name,
                "payload": payload,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return out
