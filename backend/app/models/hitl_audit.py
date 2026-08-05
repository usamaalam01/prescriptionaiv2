"""HITL pharmacist field corrections and confirmations (audit schema)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.auth import uuid_pk


class HitlAuditEvent(Base):
    __tablename__ = "hitl_audit_events"
    __table_args__ = {"schema": "audit"}

    id: Mapped[str] = uuid_pk()
    session_id: Mapped[str] = mapped_column(
        ForeignKey("prescription.review_sessions.id"), nullable=False, index=True
    )
    medicine_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    pharmacist_user_id: Mapped[str] = mapped_column(ForeignKey("auth.users.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
