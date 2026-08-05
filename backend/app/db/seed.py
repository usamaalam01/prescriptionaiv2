"""Seed roles, research documents, and development users. Run: python -m app.db.seed"""

from sqlalchemy import select

from app.core.enums import UserRole, UserStatus
from app.core.research_content import (
    CONSENT_DATE,
    CONSENT_STATEMENTS,
    CONSENT_TITLE,
    CONSENT_VERSION,
    PIS_DATE,
    PIS_FULL_TEXT,
    PIS_TITLE,
    PIS_VERSION,
    STUDY_TITLE_CONSENT,
    STUDY_TITLE_PIS,
)
from app.db.session import SessionLocal
from app.models.auth import Role, User
from app.models.consent import ConsentFormVersion, ConsentStatementVersion, ParticipantInformationSheet
from app.security.passwords import hash_password

DEV_USERS = (
    ("admin", "ChangeMeAdmin!234", UserRole.ADMINISTRATOR.value),
    ("pharmacist", "ChangeMePharm!234", UserRole.PHARMACIST.value),
    ("reviewer", "ChangeMeReview!234", UserRole.REVIEWER.value),
)


def seed() -> None:
    db = SessionLocal()
    try:
        for role_name, description in (
            (UserRole.ADMINISTRATOR.value, "System administrator"),
            (UserRole.PHARMACIST.value, "Human-in-the-loop pharmacist"),
            (UserRole.REVIEWER.value, "Read-only research reviewer"),
        ):
            if not db.scalar(select(Role).where(Role.name == role_name)):
                db.add(Role(name=role_name, description=description))

        pis = db.scalar(select(ParticipantInformationSheet).where(ParticipantInformationSheet.version == PIS_VERSION))
        if not pis:
            pis = ParticipantInformationSheet(
                version=PIS_VERSION,
                title=PIS_TITLE,
                study_title=STUDY_TITLE_PIS,
                content=PIS_FULL_TEXT,
                effective_date=PIS_DATE,
                is_current=True,
            )
            db.add(pis)

        form = db.scalar(select(ConsentFormVersion).where(ConsentFormVersion.version == CONSENT_VERSION))
        if not form:
            form = ConsentFormVersion(
                version=CONSENT_VERSION,
                title=CONSENT_TITLE,
                study_title=STUDY_TITLE_CONSENT,
                effective_date=CONSENT_DATE,
                is_current=True,
            )
            db.add(form)
            db.flush()
            for number, text in enumerate(CONSENT_STATEMENTS, start=1):
                db.add(
                    ConsentStatementVersion(form_id=form.id, statement_number=number, text=text)
                )

        for username, password, role in DEV_USERS:
            if not db.scalar(select(User).where(User.username == username)):
                db.add(
                    User(
                        username=username,
                        password_hash=hash_password(password),
                        role=role,
                        status=UserStatus.ACTIVE.value,
                        must_change_password=False,
                        is_active=True,
                    )
                )

        db.commit()
        print("Seed complete (roles, PIS/Consent v1.0, dev users).")
        print("Dev accounts: must_change_password=False (set True in production demos if needed).")
        for username, password, role in DEV_USERS:
            print(f"  {role:15} username={username:12} password={password}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
