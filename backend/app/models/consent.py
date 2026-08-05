from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.auth import uuid_pk


class ParticipantInformationSheet(Base):
    __tablename__ = "participant_information_sheets"
    __table_args__ = {"schema": "consent"}

    id: Mapped[str] = uuid_pk()
    version: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    study_title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    effective_date: Mapped[str] = mapped_column(String(40), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsentFormVersion(Base):
    __tablename__ = "consent_form_versions"
    __table_args__ = {"schema": "consent"}

    id: Mapped[str] = uuid_pk()
    version: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    study_title: Mapped[str] = mapped_column(String(500), nullable=False)
    effective_date: Mapped[str] = mapped_column(String(40), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsentStatementVersion(Base):
    __tablename__ = "consent_statement_versions"
    __table_args__ = (
        UniqueConstraint("form_id", "statement_number"),
        {"schema": "consent"},
    )

    id: Mapped[str] = uuid_pk()
    form_id: Mapped[str] = mapped_column(ForeignKey("consent.consent_form_versions.id"), nullable=False)
    statement_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class UserPisAcknowledgement(Base):
    __tablename__ = "user_pis_acknowledgements"
    __table_args__ = {"schema": "consent"}

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("auth.users.id"), nullable=False, index=True)
    pis_id: Mapped[str] = mapped_column(
        ForeignKey("consent.participant_information_sheets.id"), nullable=False
    )
    pis_version: Mapped[str] = mapped_column(String(20), nullable=False)
    scroll_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False)
    label_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserConsent(Base):
    __tablename__ = "user_consents"
    __table_args__ = {"schema": "consent"}

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("auth.users.id"), nullable=False, index=True)
    form_id: Mapped[str] = mapped_column(ForeignKey("consent.consent_form_versions.id"), nullable=False)
    study_code: Mapped[str] = mapped_column(String(100), nullable=False)
    pis_version: Mapped[str] = mapped_column(String(20), nullable=False)
    consent_form_version: Mapped[str] = mapped_column(String(20), nullable=False)
    consent_status: Mapped[str] = mapped_column(String(30), nullable=False, default="accepted")
    age_over_18_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    all_statements_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    electronic_affirmation_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserConsentResponse(Base):
    __tablename__ = "user_consent_responses"
    __table_args__ = (
        UniqueConstraint("user_consent_id", "statement_id"),
        {"schema": "consent"},
    )

    id: Mapped[str] = uuid_pk()
    user_consent_id: Mapped[str] = mapped_column(ForeignKey("consent.user_consents.id"), nullable=False)
    statement_id: Mapped[str] = mapped_column(
        ForeignKey("consent.consent_statement_versions.id"), nullable=False
    )
    statement_number: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
