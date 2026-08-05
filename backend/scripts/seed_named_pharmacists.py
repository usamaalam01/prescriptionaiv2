"""Replay normal registration for named pharmacists (form → PIS/consent → admin approve).

Creates the same rows as /register + admin approve:
  auth.users (pending→active), admin.registration_requests/decisions,
  consent.user_pis_acknowledgements, user_consents, user_consent_responses.

Dates are backfilled into 6 May 2026 – 17 July 2026.

Run inside API container:
  PYTHONPATH=/app python /app/scripts/seed_named_pharmacists.py
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.enums import RegistrationStatus, UserStatus
from app.core.research_content import CONSENT_VERSION, PIS_VERSION
from app.db.session import SessionLocal
from app.models.admin import RegistrationDecision, RegistrationRequest
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

# Inclusive registration window (UTC).
DATE_START = datetime(2026, 5, 6, 8, 0, 0, tzinfo=timezone.utc)
DATE_END = datetime(2026, 7, 17, 18, 0, 0, tzinfo=timezone.utc)

PHARMACISTS = (
    ("A-229831", "Asad", "@Asadullah#1988"),
    ("A-249831", "Najeeb", "@Najeebullah#1989"),
    ("A-245831", "Farha", "@Farhana#1990"),
    ("A-238831", "Faisal", "@Faisal#1992"),
    ("A-271932", "Mubeen", "@Mubeen#071994"),
    ("A-254764", "Tawasul", "@Tawasul#1988"),
    ("A-298765", "Ibrahim", "@Ibrahim#1990"),
)


def _registration_datetime(username: str) -> datetime:
    """Deterministic 'random' instant in [DATE_START, DATE_END] from username."""
    span = int((DATE_END - DATE_START).total_seconds())
    digest = int(hashlib.sha256(f"pharmaassist-reg-{username}".encode()).hexdigest(), 16)
    return DATE_START + timedelta(seconds=digest % (span + 1))


def seed_named_pharmacists() -> None:
    db = SessionLocal()
    try:
        pis = db.scalar(
            select(ParticipantInformationSheet).where(
                ParticipantInformationSheet.version == PIS_VERSION,
                ParticipantInformationSheet.is_current.is_(True),
            )
        )
        form = db.scalar(
            select(ConsentFormVersion).where(
                ConsentFormVersion.version == CONSENT_VERSION,
                ConsentFormVersion.is_current.is_(True),
            )
        )
        if not pis or not form:
            raise SystemExit("PIS/Consent documents missing — run app.db.seed first")

        statements = list(
            db.scalars(select(ConsentStatementVersion).where(ConsentStatementVersion.form_id == form.id))
        )
        if len(statements) != 18:
            raise SystemExit(f"Expected 18 consent statements, found {len(statements)}")

        admin = db.scalar(select(User).where(User.username == "admin"))
        if not admin:
            raise SystemExit("admin user missing — run app.db.seed first")

        created = 0
        skipped = 0
        for registration_id, username, password in PHARMACISTS:
            existing = db.scalar(select(User).where(User.username == username))
            if existing:
                print(f"  skip  {username} (already exists)")
                skipped += 1
                continue

            validate_password_policy(password, username=username)
            submitted_at = _registration_datetime(username)
            rng = random.Random(username)
            review_delay = timedelta(hours=rng.randint(2, 72))
            reviewed_at = min(submitted_at + review_delay, DATE_END)

            # Same end-state as self-registration then admin approve.
            user = User(
                username=username,
                password_hash=hash_password(password),
                role="pharmacist",
                status=UserStatus.ACTIVE.value,
                must_change_password=False,
                is_active=True,
                encrypted_pharmacist_registration_id=encrypt_field(registration_id),
                created_at=submitted_at,
                updated_at=reviewed_at,
                last_login_at=None,
            )
            db.add(user)
            db.flush()

            request = RegistrationRequest(
                user_id=user.id,
                requested_role="pharmacist",
                age_over_18_confirmed=True,
                status=RegistrationStatus.APPROVED.value,
                submitted_at=submitted_at,
                reviewed_at=reviewed_at,
            )
            db.add(request)
            db.flush()

            db.add(
                RegistrationDecision(
                    registration_id=request.id,
                    administrator_id=admin.id,
                    decision="approved",
                    confirmed_role="pharmacist",
                    reason=None,
                    created_at=reviewed_at,
                )
            )
            db.add(
                UserPisAcknowledgement(
                    user_id=user.id,
                    pis_id=pis.id,
                    pis_version=PIS_VERSION,
                    scroll_acknowledged=True,
                    label_accepted=True,
                    acknowledged_at=submitted_at,
                )
            )
            consent = UserConsent(
                user_id=user.id,
                form_id=form.id,
                study_code=settings.STUDY_CODE,
                pis_version=PIS_VERSION,
                consent_form_version=CONSENT_VERSION,
                consent_status="accepted",
                age_over_18_confirmed=True,
                all_statements_accepted=True,
                electronic_affirmation_accepted=True,
                accepted_at=submitted_at,
                created_at=submitted_at,
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

            print(
                f"  create {username:10} reg={registration_id} "
                f"submitted={submitted_at.date().isoformat()} reviewed={reviewed_at.date().isoformat()}"
            )
            created += 1

        db.commit()
        print(f"Done. created={created} skipped={skipped}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_named_pharmacists()
