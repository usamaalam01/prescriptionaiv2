import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.schemas.clinical import (
    AlternativeFeedbackIn,
    AlternativeFeedbackOut,
    AlternativeSuggestionOut,
    CitationOut,
    EvaluationSnapshotOut,
    FieldCorrectionIn,
)
from app.security.rbac import require_pharmacist, require_reviewer
from app.services import alternatives_service, field_verification
from app.services.formulary_catalog import FORMULARY_DRUGS, all_canonical_names, suggest_drugs

router = APIRouter(tags=["clinical"])


def _suggestion_out(row) -> AlternativeSuggestionOut:
    citations_raw = json.loads(row.citations_json) if row.citations_json else []
    citations = [CitationOut.model_validate(c) for c in citations_raw]
    return AlternativeSuggestionOut(
        id=row.id,
        session_id=row.session_id,
        medicine_id=row.medicine_id,
        rank=row.rank,
        source_medicine=row.source_medicine,
        alternative_medicine_name=row.alternative_medicine_name,
        strength=row.strength,
        form=row.form,
        route=row.route,
        relationship=row.relationship,
        rationale=row.rationale,
        contraindications_note=row.contraindications_note,
        confidence=row.confidence,
        explanation=row.explanation,
        citations=citations,
        knowledge_source=row.knowledge_source,
        is_mock_knowledge=row.is_mock_knowledge,
    )


@router.get(
    "/reviews/{session_id}/alternatives",
    response_model=list[AlternativeSuggestionOut],
)
def list_session_alternatives(
    session_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    rows = alternatives_service.list_suggestions_for_session(db, pharmacist, session_id)
    return [_suggestion_out(row) for row in rows]


@router.get(
    "/reviews/{session_id}/medicines/{medicine_id}/alternatives",
    response_model=list[AlternativeSuggestionOut],
)
def list_medicine_alternatives(
    session_id: str,
    medicine_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    rows = alternatives_service.list_suggestions_for_medicine(db, pharmacist, session_id, medicine_id)
    return [_suggestion_out(row) for row in rows]


@router.post(
    "/reviews/{session_id}/alternatives/{suggestion_id}/feedback",
    response_model=AlternativeFeedbackOut,
)
def post_alternative_feedback(
    session_id: str,
    suggestion_id: str,
    body: AlternativeFeedbackIn,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    row = alternatives_service.record_feedback(
        db,
        pharmacist,
        session_id,
        suggestion_id,
        decision=body.decision,
        note=body.note,
    )
    return AlternativeFeedbackOut.model_validate(row)


@router.get("/research/evaluation-snapshot", response_model=EvaluationSnapshotOut)
def evaluation_snapshot(
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    return EvaluationSnapshotOut.model_validate(alternatives_service.evaluation_snapshot(db))


@router.get("/formulary/drugs")
def list_formulary_drugs(_pharmacist: User = Depends(require_pharmacist)):
    return [
        {
            "formulary_id": d.formulary_id,
            "canonical_name": d.canonical_name,
            "aliases": list(d.aliases),
            "strengths": list(d.strengths),
            "doses": list(d.doses),
            "frequencies": list(d.frequencies),
            "forms": list(d.forms),
            "routes": list(d.routes),
        }
        for d in FORMULARY_DRUGS
    ]


@router.get("/formulary/suggest")
def formulary_suggest(
    q: str,
    limit: int = 15,
    _pharmacist: User = Depends(require_pharmacist),
):
    """Typeahead for HITL drug dropdown (catalog when built, else seed formulary)."""
    query = (q or "").strip()
    if len(query) < 1:
        return {"query": query, "options": []}
    lim = max(1, min(limit, 25))
    return {"query": query, "options": suggest_drugs(query, limit=lim)}


@router.get("/reviews/{session_id}/verification-table")
def verification_table(
    session_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    return {
        "session_id": session_id,
        "canonical_drugs": all_canonical_names(),
        "rows": field_verification.list_verification_table(db, pharmacist, session_id),
    }


@router.post("/reviews/{session_id}/medicines/{medicine_id}/fields")
def correct_field(
    session_id: str,
    medicine_id: str,
    body: FieldCorrectionIn,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    return field_verification.apply_field_correction(
        db,
        pharmacist,
        session_id,
        medicine_id,
        field=body.field,
        value=body.value,
    )


@router.post("/reviews/{session_id}/medicines/{medicine_id}/confirm-fields")
def confirm_fields(
    session_id: str,
    medicine_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    return field_verification.confirm_when_ready(db, pharmacist, session_id, medicine_id)


@router.post("/reviews/{session_id}/submit")
def submit_review_session(
    session_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    """Submit completed HITL catalog verification for the prescription session."""
    from app.services import prescription_service

    return prescription_service.submit_session(db, pharmacist, session_id)


@router.get("/reviews/{session_id}/hitl-audit")
def hitl_audit_trail(
    session_id: str,
    limit: int = 50,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    """Append-only pharmacist HITL field corrections and confirms for a session."""
    from app.services.hitl_audit import list_session_hitl_events
    from app.services import prescription_service

    prescription_service.get_owned_session(db, pharmacist, session_id)
    return {
        "session_id": session_id,
        "events": list_session_hitl_events(db, session_id, limit=limit),
        "note": "Audit trail for research / accountability — not clinical documentation.",
    }
