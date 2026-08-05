import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.models.prescription import PrescriptionMedicine, ReviewSession
from app.models.therapeutic import TherapeuticAuditEvent, TherapeuticDecision, TherapeuticEvaluation
from app.security.rbac import require_pharmacist
from app.services.therapeutic.evaluate import evaluate_prescription

router = APIRouter(prefix="/therapeutic-alternatives", tags=["therapeutic-alternatives"])


class PatientContextIn(BaseModel):
    allergy_status: str = Field(description="required: documented | none_known | unknown | not assessed")
    allergies: list[str] = []
    conditions: list[str] = []
    current_medicines: list[str] = []
    age_years: int | None = None
    pregnancy_status: str | None = None
    renal_impairment: str | None = None
    hepatic_impairment: str | None = None
    verified_indication: str | None = None


class PrescribedMedicineIn(BaseModel):
    prescription_item_id: str
    medicine_name: str
    strength: str | None = None
    form: str | None = None
    route: str | None = None
    dose: str | None = None
    frequency: str | None = None
    pharmacist_verified: bool = False
    verified_indication: str | None = None
    drugbank_id: str | None = None
    unii: str | None = None
    identity_confirmed_by_pharmacist: bool = False


class EvaluateRequest(BaseModel):
    prescription_id: str
    patient_context: PatientContextIn
    prescribed_medicines: list[PrescribedMedicineIn] = []
    top_n: int = Field(default=5, ge=1, le=10)
    use_confirmed_session_medicines: bool = True


class DecisionRequest(BaseModel):
    prescription_item_id: str
    candidate_drug_id: str
    candidate_name: str
    candidate_type: str | None = None
    action: str = Field(
        pattern="^(accept_for_review|reject|request_more_evidence)$"
    )
    reason: str = Field(default="", max_length=2000)
    note: str | None = None
    override_reason: str | None = None
    evidence_ids: list[str] = []


def _audit(db: Session, evaluation_id: str, event_type: str, payload: dict) -> None:
    db.add(
        TherapeuticAuditEvent(
            evaluation_id=evaluation_id,
            event_type=event_type,
            payload_json=json.dumps(payload, default=str),
        )
    )


@router.post("/evaluate")
def evaluate(
    body: EvaluateRequest,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    session = db.get(ReviewSession, body.prescription_id)
    if not session or session.pharmacist_user_id != pharmacist.id:
        raise HTTPException(status_code=404, detail="Prescription session not found")

    medicines_payload = [m.model_dump() for m in body.prescribed_medicines]
    if body.use_confirmed_session_medicines:
        rows = list(
            db.scalars(
                select(PrescriptionMedicine)
                .where(
                    PrescriptionMedicine.session_id == body.prescription_id,
                    PrescriptionMedicine.pharmacist_status == "confirmed",
                )
                .order_by(PrescriptionMedicine.item_number)
            )
        )
        medicines_payload = []
        for row in rows:
            # Find optional indication override from request by item id
            override = next((m for m in body.prescribed_medicines if m.prescription_item_id == row.id), None)
            medicines_payload.append(
                {
                    "prescription_item_id": row.id,
                    "medicine_name": row.pharmacist_medicine_name or row.ai_medicine_name,
                    "strength": row.pharmacist_strength or row.ai_strength,
                    "form": row.pharmacist_form or row.ai_form,
                    "route": row.pharmacist_route or row.ai_route,
                    "dose": row.pharmacist_dose or row.ai_dose,
                    "frequency": row.pharmacist_frequency or row.ai_frequency,
                    "pharmacist_verified": True,
                    "verified_indication": (override.verified_indication if override else None)
                    or row.pharmacist_verified_indication
                    or body.patient_context.verified_indication,
                    "identity_confirmed_by_pharmacist": True,
                }
            )

    if not medicines_payload:
        raise HTTPException(
            status_code=422,
            detail="No pharmacist-confirmed medicines available to evaluate. Confirm medicines in the HITL table first.",
        )

    result = evaluate_prescription(
        prescription_id=body.prescription_id,
        patient_context=body.patient_context.model_dump(),
        prescribed_medicines=medicines_payload,
        top_n=body.top_n,
    )

    evaluation = TherapeuticEvaluation(
        id=result["evaluation_id"],
        prescription_id=body.prescription_id,
        pharmacist_user_id=pharmacist.id,
        result_json=json.dumps(result, default=str),
        dataset_version=result["dataset_version"],
        rules_engine_version=result["rules_engine_version"],
    )
    db.add(evaluation)
    _audit(
        db,
        result["evaluation_id"],
        "evaluation_created",
        {
            "pharmacist_user_id": pharmacist.id,
            "prescription_id": body.prescription_id,
            "patient_context": body.patient_context.model_dump(),
            "medicine_count": len(medicines_payload),
            "result_summary": [
                {
                    "item": m["prescription_item_id"],
                    "status": m["evaluation_status"],
                    "eligible": len(m.get("eligible_alternatives") or []),
                }
                for m in result["medicine_results"]
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    session.analytics_json = None
    session.analytics_fingerprint = None
    db.commit()
    return result


@router.get("/{evaluation_id}")
def get_evaluation(
    evaluation_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    row = db.get(TherapeuticEvaluation, evaluation_id)
    if not row or row.pharmacist_user_id != pharmacist.id:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return json.loads(row.result_json)


@router.get("/{evaluation_id}/sources")
def get_sources(
    evaluation_id: str,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    row = db.get(TherapeuticEvaluation, evaluation_id)
    if not row or row.pharmacist_user_id != pharmacist.id:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    result = json.loads(row.result_json)
    claims = []
    for medicine in result.get("medicine_results") or []:
        for bucket in ("eligible_alternatives", "blocked_candidates", "withdrawn_candidates"):
            for cand in medicine.get(bucket) or []:
                for claim in cand.get("source_claims") or []:
                    claims.append({**claim, "prescription_item_id": medicine["prescription_item_id"]})
    return {"evaluation_id": evaluation_id, "demo_label": "DEMO DATA", "source_claims": claims}


@router.post("/{evaluation_id}/decision")
def post_decision(
    evaluation_id: str,
    body: DecisionRequest,
    pharmacist: User = Depends(require_pharmacist),
    db: Session = Depends(get_db),
):
    row = db.get(TherapeuticEvaluation, evaluation_id)
    if not row or row.pharmacist_user_id != pharmacist.id:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    if body.action in {"reject", "request_more_evidence"} and not (body.reason or "").strip():
        raise HTTPException(
            status_code=422,
            detail="Pharmacist reasoning is required when rejecting or requesting more evidence",
        )

    reason = (body.reason or "").strip()
    if body.action == "accept_for_review" and not reason:
        reason = "Accepted for further pharmacist review"

    # Pseudonym only — no extra PII
    reviewer_pseudonym = f"PHARM-{(pharmacist.id or '')[:8]}"

    decision = TherapeuticDecision(
        evaluation_id=evaluation_id,
        prescription_item_id=body.prescription_item_id,
        candidate_drug_id=body.candidate_drug_id,
        candidate_name=body.candidate_name,
        action=body.action,
        reason=reason,
        note=body.note,
        candidate_type=body.candidate_type,
        override_reason=body.override_reason,
        reviewer_pseudonym=reviewer_pseudonym,
        algorithm_version=row.rules_engine_version,
        catalogue_version=row.dataset_version,
        evidence_ids_json=json.dumps(body.evidence_ids or []),
        pharmacist_user_id=pharmacist.id,
        payload_json=json.dumps({**body.model_dump(), "reason": reason}, default=str),
    )
    db.add(decision)
    _audit(
        db,
        evaluation_id,
        "pharmacist_decision",
        {
            "reviewer_pseudonym": reviewer_pseudonym,
            "decision": {
                "candidate_id": body.candidate_drug_id,
                "candidate_type": body.candidate_type,
                "pharmacist_decision": body.action,
                "decision_reason": reason,
                "override_reason": body.override_reason,
                "decision_timestamp": datetime.now(timezone.utc).isoformat(),
                "algorithm_version": row.rules_engine_version,
                "catalogue_version": row.dataset_version,
                "evidence_ids": body.evidence_ids,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dataset_version": row.dataset_version,
            "rules_engine_version": row.rules_engine_version,
        },
    )
    from app.models.prescription import ReviewSession

    sess = db.get(ReviewSession, row.prescription_id)
    if sess is not None:
        sess.analytics_json = None
        sess.analytics_fingerprint = None
    db.commit()
    db.refresh(decision)
    return {
        "id": decision.id,
        "evaluation_id": evaluation_id,
        "action": decision.action,
        "created_at": decision.created_at,
    }
