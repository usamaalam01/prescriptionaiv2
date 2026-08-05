from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.auth import uuid_pk


class RegistrationRequest(Base):
    __tablename__ = "registration_requests"
    __table_args__ = {"schema": "admin"}

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("auth.users.id"), unique=True, nullable=False)
    requested_role: Mapped[str] = mapped_column(String(32), nullable=False, default="pharmacist")
    age_over_18_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_review")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RegistrationDecision(Base):
    __tablename__ = "registration_decisions"
    __table_args__ = {"schema": "admin"}

    id: Mapped[str] = uuid_pk()
    registration_id: Mapped[str] = mapped_column(
        ForeignKey("admin.registration_requests.id"), nullable=False
    )
    administrator_id: Mapped[str] = mapped_column(ForeignKey("auth.users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    confirmed_role: Mapped[str] = mapped_column(String(32), nullable=False, default="pharmacist")
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
