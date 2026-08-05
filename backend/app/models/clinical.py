"""Clinical / knowledge models for Milestone 4 alternatives + feedback."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.auth import uuid_pk


class AlternativeSuggestion(Base):
    __tablename__ = "alternative_suggestions"
    __table_args__ = {"schema": "clinical"}

    id: Mapped[str] = uuid_pk()
    session_id: Mapped[str] = mapped_column(
        ForeignKey("prescription.review_sessions.id"), nullable=False, index=True
    )
    medicine_id: Mapped[str] = mapped_column(
        ForeignKey("prescription.prescription_medicines.id"), nullable=False, index=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_medicine: Mapped[str] = mapped_column(String(255), nullable=False)
    alternative_medicine_name: Mapped[str] = mapped_column(String(255), nullable=False)
    strength: Mapped[str | None] = mapped_column(String(100))
    form: Mapped[str | None] = mapped_column(String(100))
    route: Mapped[str | None] = mapped_column(String(100))
    relationship: Mapped[str] = mapped_column(String(60), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    contraindications_note: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    knowledge_source: Mapped[str] = mapped_column(String(80), nullable=False)
    is_mock_knowledge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlternativeFeedback(Base):
    __tablename__ = "alternative_feedback"
    __table_args__ = {"schema": "clinical"}

    id: Mapped[str] = uuid_pk()
    suggestion_id: Mapped[str] = mapped_column(
        ForeignKey("clinical.alternative_suggestions.id"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("prescription.review_sessions.id"), nullable=False, index=True
    )
    pharmacist_user_id: Mapped[str] = mapped_column(ForeignKey("auth.users.id"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
