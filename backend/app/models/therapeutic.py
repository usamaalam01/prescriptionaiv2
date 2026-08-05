"""Persistence for therapeutic alternative evaluations and pharmacist decisions."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.auth import uuid_pk


class TherapeuticEvaluation(Base):
    __tablename__ = "therapeutic_evaluations"
    __table_args__ = {"schema": "clinical"}

    id: Mapped[str] = uuid_pk()
    prescription_id: Mapped[str] = mapped_column(
        ForeignKey("prescription.review_sessions.id"), nullable=False, index=True
    )
    pharmacist_user_id: Mapped[str] = mapped_column(ForeignKey("auth.users.id"), nullable=False, index=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(80), nullable=False)
    rules_engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TherapeuticDecision(Base):
    __tablename__ = "therapeutic_decisions"
    __table_args__ = {"schema": "clinical"}

    id: Mapped[str] = uuid_pk()
    evaluation_id: Mapped[str] = mapped_column(
        ForeignKey("clinical.therapeutic_evaluations.id"), nullable=False, index=True
    )
    prescription_item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    candidate_drug_id: Mapped[str] = mapped_column(String(80), nullable=False)
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    candidate_type: Mapped[str | None] = mapped_column(String(64))
    override_reason: Mapped[str | None] = mapped_column(Text)
    reviewer_pseudonym: Mapped[str | None] = mapped_column(String(80))
    algorithm_version: Mapped[str | None] = mapped_column(String(80))
    catalogue_version: Mapped[str | None] = mapped_column(String(80))
    evidence_ids_json: Mapped[str | None] = mapped_column(Text)
    pharmacist_user_id: Mapped[str] = mapped_column(ForeignKey("auth.users.id"), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TherapeuticAuditEvent(Base):
    __tablename__ = "therapeutic_audit_events"
    __table_args__ = {"schema": "audit"}

    id: Mapped[str] = uuid_pk()
    evaluation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
