from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import RegistrationStatus, UserStatus
from app.core.research_content import CONSENT_STATEMENTS, CONSENT_VERSION, PIS_VERSION
from app.models.admin import RegistrationRequest
from app.models.auth import User
from app.models.consent import (
    ConsentFormVersion,
    ConsentStatementVersion,
    ParticipantInformationSheet,
    UserConsent,
    UserConsentResponse,
    UserPisAcknowledgement,
)
from app.security.encryption import encrypt_field
from app.security.passwords import hash_password, validate_password_policy


def register_pharmacist(
    db: Session,
    *,
    username: str,
    password: str,
    pharmacist_registration_id: str,
    age_over_18: bool,
    pis_version: str,
    pis_scroll_acknowledged: bool,
    pis_label_accepted: bool,
    consent_form_version: str,
    accepted_statement_numbers: list[int],
    electronic_affirmation: bool,
) -> RegistrationRequest:
    if not age_over_18:
        raise HTTPException(status_code=422, detail="Applicants must be at least 18 years old")
    if not pis_scroll_acknowledged or not pis_label_accepted:
        raise HTTPException(status_code=422, detail="PIS acknowledgement is required")
    if pis_version != PIS_VERSION or consent_form_version != CONSENT_VERSION:
        raise HTTPException(status_code=422, detail="Research document version mismatch")
    if not electronic_affirmation:
        raise HTTPException(status_code=422, detail="Electronic affirmation is required")
    if set(accepted_statement_numbers) != set(range(1, len(CONSENT_STATEMENTS) + 1)):
        raise HTTPException(status_code=422, detail="All consent statements must be accepted")
    validate_password_policy(password, username=username)
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=409, detail="Registration cannot be completed")

    pis = db.scalar(
        select(ParticipantInformationSheet).where(
            ParticipantInformationSheet.version == pis_version,
            ParticipantInformationSheet.is_current.is_(True),
        )
    )
    form = db.scalar(
        select(ConsentFormVersion).where(
            ConsentFormVersion.version == consent_form_version,
            ConsentFormVersion.is_current.is_(True),
        )
    )
    if not pis or not form:
        raise HTTPException(status_code=503, detail="Research documents are not configured")

    statements = list(
        db.scalars(select(ConsentStatementVersion).where(ConsentStatementVersion.form_id == form.id))
    )
    if len(statements) != 18:
        raise HTTPException(status_code=503, detail="Consent statements are not configured")

    user = User(
        username=username,
        password_hash=hash_password(password),
        role="pharmacist",
        status=UserStatus.PENDING.value,
        must_change_password=False,
        is_active=False,
        encrypted_pharmacist_registration_id=encrypt_field(pharmacist_registration_id),
    )
    db.add(user)
    db.flush()

    request = RegistrationRequest(
        user_id=user.id,
        requested_role="pharmacist",
        age_over_18_confirmed=True,
        status=RegistrationStatus.PENDING_REVIEW.value,
    )
    db.add(request)
    db.flush()

    db.add(
        UserPisAcknowledgement(
            user_id=user.id,
            pis_id=pis.id,
            pis_version=pis_version,
            scroll_acknowledged=True,
            label_accepted=True,
        )
    )

    consent = UserConsent(
        user_id=user.id,
        form_id=form.id,
        study_code=settings.STUDY_CODE,
        pis_version=pis_version,
        consent_form_version=consent_form_version,
        consent_status="accepted",
        age_over_18_confirmed=True,
        all_statements_accepted=True,
        electronic_affirmation_accepted=True,
        accepted_at=datetime.now(timezone.utc),
    )
    db.add(consent)
    db.flush()
    for statement in statements:
        db.add(
            UserConsentResponse(
                user_consent_id=consent.id,
                statement_id=statement.id,
                statement_number=statement.statement_number,
                accepted=True,
            )
        )

    db.commit()
    db.refresh(request)
    return request
