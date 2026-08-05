import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.schemas.prescription import (
    MedicineOut,
    MedicineVerifyIn,
    OcrJobOut,
    OcrRunIn,
    ReviewSessionOut,
)
from app.security.rbac import require_pharmacist
from app.services import prescription_service, storage_service

router = APIRouter(tags=["prescriptions"])


@router.post("/prescriptions/upload", response_model=ReviewSessionOut)
def upload_prescription(
    request: Request,
    file: UploadFile = File(...),
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    from app.core.rate_limit import client_key, limiter

    limiter.check(client_key(request, "upload"), limit=30, window_seconds=60)
    session = prescription_service.create_session_from_upload(db, pharmacist, file)
    return ReviewSessionOut.model_validate(session)


@router.get("/prescriptions/{session_id}", response_model=ReviewSessionOut)
def get_session(
    session_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    session = prescription_service.get_owned_session(db, pharmacist, session_id)
    return ReviewSessionOut.model_validate(session)


@router.get("/prescriptions/{session_id}/image")
def get_image(
    session_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    session = prescription_service.get_owned_session(db, pharmacist, session_id)
    if not session.storage_object_key or session.temporary_deleted_at:
        return Response(status_code=404)
    data = storage_service.load_decrypted_bytes(session.storage_object_key)
    return Response(content=data, media_type=session.content_type)


@router.delete("/prescriptions/{session_id}/temporary-file")
def delete_temp(
    session_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    return prescription_service.delete_temporary(db, pharmacist, session_id)


@router.post("/prescriptions/{session_id}/cancel")
def cancel(
    session_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    return prescription_service.cancel_session(db, pharmacist, session_id)


@router.post("/ocr/{session_id}/run", response_model=OcrJobOut)
def run_ocr(
    session_id: str,
    body: OcrRunIn,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    """Synchronous OCR (kept for tests / fallback). Prefer /run-async for UI."""
    job = prescription_service.run_session_ocr(db, pharmacist, session_id, body.engine)
    return _job_out(job)


@router.post("/ocr/{session_id}/run-async", response_model=OcrJobOut)
def run_ocr_async(
    session_id: str,
    body: OcrRunIn,
    request: Request,
    background_tasks: BackgroundTasks,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    """Enqueue OCR pipeline and return immediately (poll GET /ocr/jobs/{id})."""
    from app.core.rate_limit import client_key, limiter

    limiter.check(client_key(request, "ocr-async"), limit=20, window_seconds=60)
    if body.engine != "pipeline":
        job = prescription_service.run_session_ocr(db, pharmacist, session_id, body.engine)
        return _job_out(job)
    job = prescription_service.enqueue_session_pipeline(db, pharmacist, session_id)
    background_tasks.add_task(prescription_service.execute_queued_pipeline, job.id)
    return _job_out(job)


@router.get("/ocr/jobs/{job_id}", response_model=OcrJobOut)
def get_ocr_job(
    job_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    job = prescription_service.get_ocr_job_for_pharmacist(db, pharmacist, job_id)
    return _job_out(job)


@router.get("/ocr/{session_id}/results", response_model=OcrJobOut | None)
def ocr_results(
    session_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    prescription_service.get_owned_session(db, pharmacist, session_id)
    job = prescription_service.latest_ocr(db, session_id)
    return _job_out(job) if job else None


@router.get("/reviews/{session_id}/medicines", response_model=list[MedicineOut])
def medicines(
    session_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    rows = prescription_service.list_medicines(db, pharmacist, session_id)
    return [_medicine_out(row) for row in rows]


@router.post("/reviews/{session_id}/medicines/{medicine_id}/verify", response_model=MedicineOut)
def verify_medicine(
    session_id: str,
    medicine_id: str,
    body: MedicineVerifyIn,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    row = prescription_service.verify_medicine(
        db,
        pharmacist,
        session_id,
        medicine_id,
        status=body.status,
        medicine_name=body.medicine_name,
        strength=body.strength,
        form=body.form,
        dose=body.dose,
        route=body.route,
        frequency=body.frequency,
        duration=body.duration,
        reason=body.reason,
    )
    return _medicine_out(row)


def _job_out(job) -> OcrJobOut:
    warnings = json.loads(job.warnings_json) if job.warnings_json else []
    pipeline = json.loads(job.pipeline_json) if job.pipeline_json else None
    return OcrJobOut(
        id=job.id,
        session_id=job.session_id,
        engine=job.engine,
        status=job.status,
        raw_text=job.raw_text,
        confidence=job.confidence,
        character_count=job.character_count,
        processing_ms=job.processing_ms,
        is_mock=job.is_mock,
        warnings=warnings,
        pipeline=pipeline,
    )


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
