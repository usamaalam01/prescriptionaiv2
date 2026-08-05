from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.consent import ConsentFormVersion, ConsentStatementVersion, ParticipantInformationSheet

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/pis/current")
def current_pis(db: Session = Depends(get_db)):
    item = db.scalar(
        select(ParticipantInformationSheet).where(ParticipantInformationSheet.is_current.is_(True))
    )
    if not item:
        raise HTTPException(status_code=503, detail="PIS is not configured")
    return {
        "version": item.version,
        "title": item.title,
        "study_title": item.study_title,
        "effective_date": item.effective_date,
        "content": item.content,
    }


@router.get("/consent/current")
def current_consent(db: Session = Depends(get_db)):
    form = db.scalar(select(ConsentFormVersion).where(ConsentFormVersion.is_current.is_(True)))
    if not form:
        raise HTTPException(status_code=503, detail="Consent form is not configured")
    statements = list(
        db.scalars(
            select(ConsentStatementVersion)
            .where(ConsentStatementVersion.form_id == form.id)
            .order_by(ConsentStatementVersion.statement_number)
        )
    )
    return {
        "version": form.version,
        "title": form.title,
        "study_title": form.study_title,
        "effective_date": form.effective_date,
        "statements": [{"number": s.statement_number, "text": s.text} for s in statements],
    }
