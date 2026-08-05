from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.clinical import AlternativeFeedback, AlternativeSuggestion
from app.models.auth import User
from app.models.prescription import OcrJob, PrescriptionMedicine, ReviewSession, TemporaryFileRecord
from app.services import alternatives_service, storage_service
from app.services.ocr_service import run_ocr
from app.services.pipeline import PrescriptionPipeline

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    # PDF deferred until rasterization exists — accepting PDF today collapses OCR to mock/error
}

_pipeline = PrescriptionPipeline()


def create_session_from_upload(db: Session, pharmacist: User, upload: UploadFile) -> ReviewSession:
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Unsupported file type. Use JPG or PNG. PDF is disabled until page rasterization is available.",
        )
    data = upload.file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty file")
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=422, detail="File exceeds maximum upload size")

    object_key = storage_service.store_encrypted_bytes(data, suffix=".enc")
    session = ReviewSession(
        pharmacist_user_id=pharmacist.id,
        status="uploaded",
        original_filename=upload.filename or "prescription.bin",
        content_type=upload.content_type or "application/octet-stream",
        file_size_bytes=len(data),
        storage_object_key=object_key,
    )
    db.add(session)
    db.flush()
    db.add(TemporaryFileRecord(session_id=session.id, object_key=object_key, encrypted=True))
    db.commit()
    db.refresh(session)
    return session


def get_owned_session(db: Session, pharmacist: User, session_id: str) -> ReviewSession:
    session = db.get(ReviewSession, session_id)
    if not session or session.pharmacist_user_id != pharmacist.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def run_session_pipeline(db: Session, pharmacist: User, session_id: str) -> OcrJob:
    """Full academic pipeline: OCR → merge → parser → formulary (synchronous)."""
    session = get_owned_session(db, pharmacist, session_id)
    if not session.storage_object_key or session.temporary_deleted_at:
        raise HTTPException(status_code=409, detail="Temporary prescription image is not available")
    return _execute_pipeline_for_session(db, session, job=None)


def enqueue_session_pipeline(db: Session, pharmacist: User, session_id: str) -> OcrJob:
    """Create a queued OCR job; caller schedules execute_queued_pipeline(job.id)."""
    session = get_owned_session(db, pharmacist, session_id)
    if not session.storage_object_key or session.temporary_deleted_at:
        raise HTTPException(status_code=409, detail="Temporary prescription image is not available")

    job = OcrJob(
        session_id=session.id,
        engine="pipeline",
        status="queued",
        raw_text="",
        confidence=0.0,
        character_count=0,
        processing_ms=0,
        is_mock=False,
        warnings_json=json.dumps(["Job queued — awaiting OCR worker"]),
        pipeline_json=None,
    )
    session.status = "ocr_queued"
    session.selected_ocr_engine = "pipeline"
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def execute_queued_pipeline(job_id: str) -> None:
    """Background worker entry — opens its own DB session."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(OcrJob, job_id)
        if job is None:
            return
        if job.status not in {"queued", "running"}:
            return
        session = db.get(ReviewSession, job.session_id)
        if session is None:
            job.status = "failed"
            job.warnings_json = json.dumps(["Session missing"])
            db.commit()
            return
        job.status = "running"
        job.warnings_json = json.dumps(["OCR pipeline running"])
        db.commit()
        try:
            _execute_pipeline_for_session(db, session, job=job)
        except Exception as exc:  # noqa: BLE001
            job = db.get(OcrJob, job_id)
            if job is not None:
                job.status = "failed"
                job.warnings_json = json.dumps([f"Pipeline failed: {type(exc).__name__}: {exc}"])
                db.commit()
    finally:
        db.close()


def get_ocr_job_for_pharmacist(db: Session, pharmacist: User, job_id: str) -> OcrJob:
    job = db.get(OcrJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="OCR job not found")
    get_owned_session(db, pharmacist, job.session_id)
    return job


def _execute_pipeline_for_session(
    db: Session,
    session: ReviewSession,
    *,
    job: OcrJob | None,
) -> OcrJob:
    if not session.storage_object_key or session.temporary_deleted_at:
        raise HTTPException(status_code=409, detail="Temporary prescription image is not available")

    image_bytes = storage_service.load_decrypted_bytes(session.storage_object_key)
    result = _pipeline.run(image_bytes)

    # Replace previous AI medicine rows + alternatives for this session
    old_meds = list(db.scalars(select(PrescriptionMedicine).where(PrescriptionMedicine.session_id == session.id)))
    old_ids = [m.id for m in old_meds]
    if old_ids:
        old_alts = list(
            db.scalars(select(AlternativeSuggestion).where(AlternativeSuggestion.medicine_id.in_(old_ids)))
        )
        alt_ids = [a.id for a in old_alts]
        if alt_ids:
            for fb in db.scalars(select(AlternativeFeedback).where(AlternativeFeedback.suggestion_id.in_(alt_ids))):
                db.delete(fb)
            db.flush()
        for alt in old_alts:
            db.delete(alt)
        db.flush()
    for old in old_meds:
        db.delete(old)
    db.flush()

    medicine_rows: list[PrescriptionMedicine] = []
    for med, check in zip(result.parsed_medicines, result.formulary_checks, strict=False):
        row = PrescriptionMedicine(
            session_id=session.id,
            item_number=med.item_number,
            ai_medicine_name=med.medicine_name,
            ai_strength=med.strength,
            ai_form=med.form,
            ai_dose=med.dose,
            ai_route=med.route,
            ai_frequency=med.frequency,
            ai_duration=med.duration,
            source_span=med.source_span,
            parser_confidence=med.parser_confidence,
            formulary_matched=check.matched,
            formulary_id=check.formulary_id,
            formulary_warnings_json=json.dumps(check.warnings),
            pharmacist_status="extracted" if check.matched else "manual_review_required",
        )
        db.add(row)
        medicine_rows.append(row)
    db.flush()

    if job is None:
        job = OcrJob(
            session_id=session.id,
            engine="pipeline",
            status="completed",
            raw_text=result.raw_text,
            confidence=result.overall_ocr_confidence,
            character_count=len(result.raw_text),
            processing_ms=result.processing_ms,
            is_mock=result.is_mock,
            warnings_json=json.dumps(result.warnings),
            pipeline_json=result.to_json(),
        )
        db.add(job)
    else:
        job.engine = "pipeline"
        job.status = "completed"
        job.raw_text = result.raw_text
        job.confidence = result.overall_ocr_confidence
        job.character_count = len(result.raw_text)
        job.processing_ms = result.processing_ms
        job.is_mock = result.is_mock
        job.warnings_json = json.dumps(result.warnings)
        job.pipeline_json = result.to_json()

    session.selected_ocr_engine = "pipeline"
    session.pipeline_json = result.to_json()
    session.status = "awaiting_pharmacist_verification"
    db.commit()
    db.refresh(job)
    alternatives_service.materialize_suggestions(db, session.id, medicine_rows)
    return job


def run_session_ocr(db: Session, pharmacist: User, session_id: str, engine: str) -> OcrJob:
    if engine == "pipeline":
        return run_session_pipeline(db, pharmacist, session_id)

    session = get_owned_session(db, pharmacist, session_id)
    if not session.storage_object_key or session.temporary_deleted_at:
        raise HTTPException(status_code=409, detail="Temporary prescription image is not available")
    image_bytes = storage_service.load_decrypted_bytes(session.storage_object_key)
    try:
        result = run_ocr(engine, image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job = OcrJob(
        session_id=session.id,
        engine=result.engine,
        status="completed",
        raw_text=result.raw_text,
        confidence=result.confidence,
        character_count=len(result.raw_text),
        processing_ms=result.processing_ms,
        is_mock=result.is_mock,
        warnings_json=json.dumps(result.warnings),
    )
    session.selected_ocr_engine = result.engine
    session.status = "ocr_completed"
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def latest_ocr(db: Session, session_id: str) -> OcrJob | None:
    return db.scalar(select(OcrJob).where(OcrJob.session_id == session_id).order_by(OcrJob.created_at.desc()))


def list_medicines(db: Session, pharmacist: User, session_id: str) -> list[PrescriptionMedicine]:
    get_owned_session(db, pharmacist, session_id)
    return list(
        db.scalars(
            select(PrescriptionMedicine)
            .where(PrescriptionMedicine.session_id == session_id)
            .order_by(PrescriptionMedicine.item_number)
        )
    )


def verify_medicine(
    db: Session,
    pharmacist: User,
    session_id: str,
    medicine_id: str,
    *,
    status: str,
    medicine_name: str | None = None,
    strength: str | None = None,
    form: str | None = None,
    dose: str | None = None,
    route: str | None = None,
    frequency: str | None = None,
    duration: str | None = None,
    reason: str | None = None,
) -> PrescriptionMedicine:
    get_owned_session(db, pharmacist, session_id)
    medicine = db.get(PrescriptionMedicine, medicine_id)
    if not medicine or medicine.session_id != session_id:
        raise HTTPException(status_code=404, detail="Medicine not found")

    allowed = {
        "confirmed",
        "corrected",
        "unidentified",
        "excluded",
        "manual_review_required",
        "reviewed",
    }
    if status not in allowed:
        raise HTTPException(status_code=422, detail="Invalid pharmacist status")

    if status in {"unidentified", "excluded", "manual_review_required"} and not reason:
        raise HTTPException(status_code=422, detail="Reason is required for this status")

    if status == "confirmed":
        from app.services.field_verification import (
            _assert_confirm_allowed_for_ocr,
            build_field_state,
        )
        from app.services.hitl_audit import record_hitl_event

        _assert_confirm_allowed_for_ocr(db, session_id)

        state = build_field_state(medicine)
        # Allow confirm body to supply final field values first
        if medicine_name:
            medicine.pharmacist_medicine_name = medicine_name
        if strength:
            medicine.pharmacist_strength = strength
        if form:
            medicine.pharmacist_form = form
        if dose:
            medicine.pharmacist_dose = dose
        if route:
            medicine.pharmacist_route = route
        if frequency:
            medicine.pharmacist_frequency = frequency
        if duration:
            medicine.pharmacist_duration = duration
        db.flush()
        state = build_field_state(medicine)
        if not state["can_confirm"]:
            raise HTTPException(
                status_code=422,
                detail=state.get("confirm_hint")
                or (
                    "Cannot confirm until drug, route, strength, dosage, and frequency are "
                    "catalog-matched (indication optional). Use Unable to verify if unmatched."
                ),
            )
        medicine.pharmacist_route = state["fields"]["route"]["value"]
        medicine.formulary_matched = True
        medicine.formulary_id = state["formulary_id"]
        medicine.pharmacist_medicine_name = state["canonical_drug"]
        medicine.pharmacist_strength = state["fields"]["strength"]["value"]
        medicine.pharmacist_dose = state["fields"]["dose"]["value"]
        medicine.pharmacist_frequency = state["fields"]["frequency"]["value"]
        medicine.pharmacist_verified_indication = state["fields"]["indication"]["value"]
        medicine.pharmacist_status = status
        medicine.pharmacist_reason = reason
        medicine.verified_at = datetime.now(timezone.utc)
        record_hitl_event(
            db,
            session_id=session_id,
            pharmacist_user_id=pharmacist.id,
            medicine_id=medicine.id,
            event_type="hitl.row_confirmed",
            field_name=None,
            payload={
                "item_number": medicine.item_number,
                "drug": medicine.pharmacist_medicine_name,
                "strength": medicine.pharmacist_strength,
                "dose": medicine.pharmacist_dose,
                "frequency": medicine.pharmacist_frequency,
                "indication": medicine.pharmacist_verified_indication,
                "via": "legacy_verify_endpoint",
            },
        )
        db.commit()
        _invalidate = __import__(
            "app.services.field_verification", fromlist=["_invalidate_session_analytics"]
        )._invalidate_session_analytics
        _invalidate(db, session_id)
        db.refresh(medicine)
        return medicine

    medicine.pharmacist_status = status
    medicine.pharmacist_medicine_name = medicine_name or medicine.ai_medicine_name
    medicine.pharmacist_strength = strength or medicine.ai_strength
    medicine.pharmacist_form = form or medicine.ai_form
    medicine.pharmacist_dose = dose or medicine.ai_dose
    medicine.pharmacist_route = route or medicine.ai_route
    medicine.pharmacist_frequency = frequency or medicine.ai_frequency
    medicine.pharmacist_duration = duration or medicine.ai_duration
    medicine.pharmacist_reason = reason
    medicine.verified_at = datetime.now(timezone.utc)
    from app.services.hitl_audit import record_hitl_event

    record_hitl_event(
        db,
        session_id=session_id,
        pharmacist_user_id=pharmacist.id,
        medicine_id=medicine.id,
        event_type=f"hitl.row_{status}",
        field_name=None,
        payload={
            "item_number": medicine.item_number,
            "status": status,
            "reason": reason,
            "drug": medicine.pharmacist_medicine_name,
            "via": "verify_endpoint",
        },
    )
    db.commit()
    _invalidate = __import__(
        "app.services.field_verification", fromlist=["_invalidate_session_analytics"]
    )._invalidate_session_analytics
    _invalidate(db, session_id)
    db.refresh(medicine)
    return medicine


def delete_temporary(db: Session, pharmacist: User, session_id: str) -> dict:
    session = get_owned_session(db, pharmacist, session_id)
    deleted = False
    if session.storage_object_key:
        deleted = storage_service.delete_object(session.storage_object_key)
        for record in db.scalars(
            select(TemporaryFileRecord).where(
                TemporaryFileRecord.session_id == session.id,
                TemporaryFileRecord.deleted_at.is_(None),
            )
        ):
            record.deleted_at = datetime.now(timezone.utc)
    session.storage_object_key = None
    session.temporary_deleted_at = datetime.now(timezone.utc)
    session.status = "temporary_deleted"
    db.commit()
    return {"deleted": deleted, "session_id": session.id}


def cancel_session(db: Session, pharmacist: User, session_id: str) -> dict:
    result = delete_temporary(db, pharmacist, session_id)
    session = get_owned_session(db, pharmacist, session_id)
    session.status = "cancelled"
    session.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    return result


def submit_session(db: Session, pharmacist: User, session_id: str) -> dict:
    """Finalize pharmacist catalog verification for a prescription session.

    Requires every medicine row to be resolved (confirmed or unable/excluded).
    Decision-support only — not a patient clinical record.
    """
    session = get_owned_session(db, pharmacist, session_id)
    medicines = list_medicines(db, pharmacist, session_id)
    if not medicines:
        raise HTTPException(
            status_code=422,
            detail="No medicine rows to submit. Run OCR / HITL first.",
        )

    unresolved = [
        m
        for m in medicines
        if m.pharmacist_status
        not in {"confirmed", "excluded", "unidentified"}
    ]
    if unresolved:
        nums = ", ".join(str(m.item_number) for m in unresolved)
        raise HTTPException(
            status_code=422,
            detail=(
                f"Resolve all medicines before Submit "
                f"(Confirm or Unable to verify). Still open: #{nums}."
            ),
        )

    confirmed = sum(1 for m in medicines if m.pharmacist_status == "confirmed")
    excluded = sum(
        1 for m in medicines if m.pharmacist_status in {"excluded", "unidentified"}
    )
    session.status = "submitted"
    db.commit()
    db.refresh(session)

    try:
        from app.services.hitl_audit import record_hitl_event

        record_hitl_event(
            db,
            session_id=session_id,
            pharmacist_user_id=pharmacist.id,
            medicine_id=None,
            event_type="hitl.session_submitted",
            field_name=None,
            payload={
                "confirmed": confirmed,
                "excluded": excluded,
                "total": len(medicines),
            },
        )
        db.commit()
    except Exception:
        pass

    return {
        "session_id": session.id,
        "status": session.status,
        "confirmed": confirmed,
        "excluded": excluded,
        "total": len(medicines),
        "message": "Prescription catalog verification submitted.",
    }
