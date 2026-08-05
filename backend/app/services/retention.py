"""Encrypted temporary prescription image retention / purge.

Aligns with consent wording: temporary Rx images are securely deleted after
processing or when the retention window expires. Decision-support research only.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.prescription import PrescriptionMedicine, ReviewSession, TemporaryFileRecord
from app.services import storage_service

logger = logging.getLogger(__name__)


def retention_policy() -> dict[str, Any]:
    return {
        "retention_hours": settings.TEMP_FILE_RETENTION_HOURS,
        "delete_on_cancel": True,
        "delete_when_session_confirmed": settings.DELETE_TEMP_WHEN_SESSION_CONFIRMED,
        "purge_on_startup": settings.PURGE_EXPIRED_ON_STARTUP,
        "note": (
            "Encrypted temporary images are deleted on cancel, when all medicines are "
            "confirmed (if enabled), or after the retention window — not kept as a lasting archive."
        ),
    }


def _mark_session_temp_deleted(db: Session, session: ReviewSession, *, now: datetime) -> bool:
    deleted = False
    if session.storage_object_key:
        deleted = storage_service.delete_object(session.storage_object_key)
        for record in db.scalars(
            select(TemporaryFileRecord).where(
                TemporaryFileRecord.session_id == session.id,
                TemporaryFileRecord.deleted_at.is_(None),
            )
        ):
            record.deleted_at = now
        session.storage_object_key = None
    session.temporary_deleted_at = now
    if session.status not in {"cancelled", "temporary_deleted"}:
        session.status = "temporary_deleted"
    return deleted


def purge_expired_temporary_files(db: Session) -> dict[str, Any]:
    """Delete encrypted Rx blobs past TEMP_FILE_RETENTION_HOURS."""
    hours = max(1, int(settings.TEMP_FILE_RETENTION_HOURS))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    sessions = list(
        db.scalars(
            select(ReviewSession).where(
                ReviewSession.storage_object_key.is_not(None),
                ReviewSession.temporary_deleted_at.is_(None),
                ReviewSession.created_at < cutoff,
            )
        )
    )
    purged: list[str] = []
    for session in sessions:
        _mark_session_temp_deleted(db, session, now=now)
        purged.append(session.id)
    db.commit()
    logger.info(
        "retention_purge",
        extra={"purged_count": len(purged), "retention_hours": hours},
    )
    return {
        "purged_sessions": purged,
        "purged_count": len(purged),
        "cutoff": cutoff.isoformat(),
        "retention_hours": hours,
        "policy": retention_policy(),
    }


def maybe_delete_temp_after_confirm(db: Session, session_id: str) -> dict[str, Any] | None:
    """If enabled and every medicine row is confirmed, wipe the encrypted image."""
    if not settings.DELETE_TEMP_WHEN_SESSION_CONFIRMED:
        return None
    session = db.get(ReviewSession, session_id)
    if session is None or not session.storage_object_key or session.temporary_deleted_at:
        return None
    meds = list(
        db.scalars(select(PrescriptionMedicine).where(PrescriptionMedicine.session_id == session_id))
    )
    if not meds:
        return None
    if any(m.pharmacist_status != "confirmed" for m in meds):
        return None
    now = datetime.now(timezone.utc)
    deleted = _mark_session_temp_deleted(db, session, now=now)
    db.commit()
    return {
        "session_id": session_id,
        "deleted": deleted,
        "reason": "all_medicines_confirmed",
        "temporary_deleted_at": now.isoformat(),
    }


def retention_status(db: Session) -> dict[str, Any]:
    active = (
        db.scalar(
            select(ReviewSession.id)
            .where(
                ReviewSession.storage_object_key.is_not(None),
                ReviewSession.temporary_deleted_at.is_(None),
            )
            .limit(1)
        )
        is not None
    )
    active_count = len(
        list(
            db.scalars(
                select(ReviewSession).where(
                    ReviewSession.storage_object_key.is_not(None),
                    ReviewSession.temporary_deleted_at.is_(None),
                )
            )
        )
    )
    hours = max(1, int(settings.TEMP_FILE_RETENTION_HOURS))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    expired_count = len(
        list(
            db.scalars(
                select(ReviewSession).where(
                    ReviewSession.storage_object_key.is_not(None),
                    ReviewSession.temporary_deleted_at.is_(None),
                    ReviewSession.created_at < cutoff,
                )
            )
        )
    )
    return {
        "policy": retention_policy(),
        "active_encrypted_images": active_count,
        "expired_pending_purge": expired_count,
        "has_active_images": active,
    }


def main() -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        print("status:", retention_status(db))
        print("purge:", purge_expired_temporary_files(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
