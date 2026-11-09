import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.schemas.prescription import MedicineOut
from app.security.rbac import require_reviewer
from app.services import admin_dashboard, prescription_service, storage_service

router = APIRouter(prefix="/reviewer", tags=["reviewer"])


@router.get("/prescriptions")
def prescriptions(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_reviewer),
):
    items = admin_dashboard.list_prescription_sessions(db, limit=limit)
    return {
        "items": items,
        "disclaimer": (
            "Live sessions only: self-registered pharmacists, non-mock OCR. "
            "No patient identifiers or fabricated rows. Read-only — reviewers cannot edit."
        ),
    }


@router.get("/prescriptions/{session_id}")
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_reviewer),
):
    session = prescription_service.get_session_for_review(db, session_id)
    pharmacist = db.get(User, session.pharmacist_user_id)
    ocr = prescription_service.latest_ocr(db, session_id)
    return {
        "id": session.id,
        "status": session.status,
        "original_filename": session.original_filename,
        "content_type": session.content_type,
        "file_size_bytes": session.file_size_bytes,
        "selected_ocr_engine": session.selected_ocr_engine,
        "temporary_deleted_at": session.temporary_deleted_at,
        "pharmacist_username": pharmacist.username if pharmacist else None,
        "ocr_raw_text": ocr.raw_text if ocr else None,
        "ocr_confidence": ocr.confidence if ocr else None,
        "ocr_is_mock": bool(ocr.is_mock) if ocr else None,
    }


@router.get("/prescriptions/{session_id}/image")
def get_image(
    session_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_reviewer),
):
    session = prescription_service.get_session_for_review(db, session_id)
    if not session.storage_object_key or session.temporary_deleted_at:
        return Response(status_code=404)
    data = storage_service.load_decrypted_bytes(session.storage_object_key)
    return Response(content=data, media_type=session.content_type)


@router.get("/prescriptions/{session_id}/medicines", response_model=list[MedicineOut])
def medicines(
    session_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_reviewer),
):
    rows = prescription_service.list_medicines_for_review(db, session_id)
    return [_medicine_out(row) for row in rows]


def _medicine_out(row) -> MedicineOut:
    warnings = json.loads(row.formulary_warnings_json) if row.formulary_warnings_json else []
    return MedicineOut(
        id=row.id,
        item_number=row.item_number,
        ai_medicine_name=row.ai_medicine_name,
        ai_strength=row.ai_strength,
        ai_form=row.ai_form,
        ai_dose=row.ai_dose,
        ai_route=row.ai_route,
        ai_frequency=row.ai_frequency,
        ai_duration=row.ai_duration,
        source_span=row.source_span,
        parser_confidence=row.parser_confidence,
        formulary_matched=row.formulary_matched,
        formulary_id=row.formulary_id,
        formulary_warnings=warnings,
        pharmacist_status=row.pharmacist_status,
        pharmacist_medicine_name=row.pharmacist_medicine_name,
        pharmacist_strength=row.pharmacist_strength,
        pharmacist_form=row.pharmacist_form,
        pharmacist_dose=row.pharmacist_dose,
        pharmacist_route=row.pharmacist_route,
        pharmacist_frequency=row.pharmacist_frequency,
        pharmacist_duration=row.pharmacist_duration,
        pharmacist_reason=row.pharmacist_reason,
    )
