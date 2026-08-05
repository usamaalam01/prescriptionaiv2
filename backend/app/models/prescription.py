from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.auth import uuid_pk


class ReviewSession(Base):
    __tablename__ = "review_sessions"
    __table_args__ = {"schema": "prescription"}

    id: Mapped[str] = uuid_pk()
    pharmacist_user_id: Mapped[str] = mapped_column(ForeignKey("auth.users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="uploaded")
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_object_key: Mapped[str | None] = mapped_column(String(500))
    selected_ocr_engine: Mapped[str | None] = mapped_column(String(40))
    pipeline_json: Mapped[str | None] = mapped_column(Text)
    analytics_json: Mapped[str | None] = mapped_column(Text)
    analytics_fingerprint: Mapped[str | None] = mapped_column(String(64))
    analytics_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    temporary_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TemporaryFileRecord(Base):
    __tablename__ = "temporary_file_records"
    __table_args__ = {"schema": "security"}

    id: Mapped[str] = uuid_pk()
    session_id: Mapped[str] = mapped_column(ForeignKey("prescription.review_sessions.id"), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OcrJob(Base):
    __tablename__ = "ocr_jobs"
    __table_args__ = {"schema": "ocr"}

    id: Mapped[str] = uuid_pk()
    session_id: Mapped[str] = mapped_column(
        ForeignKey("prescription.review_sessions.id"), nullable=False, index=True
    )
    engine: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="completed")
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    warnings_json: Mapped[str | None] = mapped_column(Text)
    pipeline_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PrescriptionMedicine(Base):
    __tablename__ = "prescription_medicines"
    __table_args__ = {"schema": "prescription"}

    id: Mapped[str] = uuid_pk()
    session_id: Mapped[str] = mapped_column(
        ForeignKey("prescription.review_sessions.id"), nullable=False, index=True
    )
    item_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_medicine_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ai_strength: Mapped[str | None] = mapped_column(String(100))
    ai_form: Mapped[str | None] = mapped_column(String(100))
    ai_dose: Mapped[str | None] = mapped_column(String(100))
    ai_route: Mapped[str | None] = mapped_column(String(100))
    ai_frequency: Mapped[str | None] = mapped_column(String(100))
    ai_duration: Mapped[str | None] = mapped_column(String(100))
    source_span: Mapped[str | None] = mapped_column(Text)
    parser_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    formulary_matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    formulary_id: Mapped[str | None] = mapped_column(String(100))
    formulary_warnings_json: Mapped[str | None] = mapped_column(Text)
    pharmacist_status: Mapped[str] = mapped_column(String(40), nullable=False, default="extracted")
    pharmacist_medicine_name: Mapped[str | None] = mapped_column(String(255))
    pharmacist_strength: Mapped[str | None] = mapped_column(String(100))
    pharmacist_form: Mapped[str | None] = mapped_column(String(100))
    pharmacist_dose: Mapped[str | None] = mapped_column(String(100))
    pharmacist_route: Mapped[str | None] = mapped_column(String(100))
    pharmacist_frequency: Mapped[str | None] = mapped_column(String(100))
    pharmacist_duration: Mapped[str | None] = mapped_column(String(100))
    pharmacist_reason: Mapped[str | None] = mapped_column(Text)
    pharmacist_verified_indication: Mapped[str | None] = mapped_column(String(255))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
