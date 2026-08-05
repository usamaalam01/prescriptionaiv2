from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.registration import PharmacistRegistrationIn, RegistrationOut
from app.services.registration_service import register_pharmacist

router = APIRouter(prefix="/auth", tags=["registration"])


@router.post("/register/complete", response_model=RegistrationOut)
def register_complete(body: PharmacistRegistrationIn, db: Session = Depends(get_db)):
    item = register_pharmacist(
        db,
        username=body.username,
        password=body.password,
        pharmacist_registration_id=body.pharmacist_registration_id,
        age_over_18=body.age_over_18,
        pis_version=body.pis_version,
        pis_scroll_acknowledged=body.pis_scroll_acknowledged,
        pis_label_accepted=body.pis_label_accepted,
        consent_form_version=body.consent_form_version,
        accepted_statement_numbers=body.accepted_statement_numbers,
        electronic_affirmation=body.electronic_affirmation,
    )
    return RegistrationOut(id=item.id, user_id=item.user_id, status=item.status)
