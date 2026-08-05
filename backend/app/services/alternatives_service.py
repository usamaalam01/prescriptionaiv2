"""Therapeutic alternatives + evidence-linked explanations (Milestone 4).

Decision-support only. Suggestions are never auto-applied to a prescription.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.clinical import AlternativeSuggestion, AlternativeFeedback
from app.models.prescription import OcrJob, PrescriptionMedicine, ReviewSession
from app.services.knowledge import AlternativeCandidate, EvidenceCitation, lookup_drug
from app.services import prescription_service


DISCLAIMER = (
    "Decision-support only. Alternatives are generated from a synthetic academic "
    "DrugBank/FDA-style knowledge subset. A qualified pharmacist must review every "
    "suggestion before any clinical action. Not for actual patient treatment."
)


def _citation_dicts(citations: list[EvidenceCitation]) -> list[dict]:
    return [asdict(c) for c in citations]


def build_explanation(medicine_name: str, alt: AlternativeCandidate) -> str:
    cites = "; ".join(f"{c.source}:{c.source_id}" for c in alt.citations) or "none"
    return (
        f"Suggested alternative '{alt.medicine_name}' for '{medicine_name}' "
        f"({alt.relationship}). Rationale: {alt.rationale} "
        f"Safety note: {alt.contraindications_note} "
        f"Evidence anchors: {cites}. {DISCLAIMER}"
    )


def suggest_for_medicine(medicine: PrescriptionMedicine) -> list[dict]:
    name = medicine.pharmacist_medicine_name or medicine.ai_medicine_name
    drug = lookup_drug(name)
    if drug is None:
        return []

    items: list[dict] = []
    for idx, alt in enumerate(drug.alternatives, start=1):
        items.append(
            {
                "rank": idx,
                "source_medicine": drug.name,
                "alternative_medicine_name": alt.medicine_name,
                "strength": alt.strength,
                "form": alt.form,
                "route": alt.route,
                "relationship": alt.relationship,
                "rationale": alt.rationale,
                "contraindications_note": alt.contraindications_note,
                "confidence": alt.confidence,
                "explanation": build_explanation(drug.name, alt),
                "citations": _citation_dicts(alt.citations + list(drug.citations[:1])),
                "knowledge_source": "synthetic_drugbank_fda_seed",
                "is_mock_knowledge": True,
            }
        )
    return items


def materialize_suggestions(
    db: Session,
    session_id: str,
    medicines: list[PrescriptionMedicine],
) -> list[AlternativeSuggestion]:
    """Replace stored suggestions for the given medicines after a pipeline run."""
    med_ids = [m.id for m in medicines]
    if med_ids:
        old_alts = list(
            db.scalars(select(AlternativeSuggestion).where(AlternativeSuggestion.medicine_id.in_(med_ids)))
        )
        alt_ids = [a.id for a in old_alts]
        if alt_ids:
            for fb in db.scalars(select(AlternativeFeedback).where(AlternativeFeedback.suggestion_id.in_(alt_ids))):
                db.delete(fb)
            db.flush()
        for old in old_alts:
            db.delete(old)
        db.flush()

    created: list[AlternativeSuggestion] = []
    for medicine in medicines:
        for item in suggest_for_medicine(medicine):
            row = AlternativeSuggestion(
                session_id=session_id,
                medicine_id=medicine.id,
                rank=item["rank"],
                source_medicine=item["source_medicine"],
                alternative_medicine_name=item["alternative_medicine_name"],
                strength=item["strength"],
                form=item["form"],
                route=item["route"],
                relationship=item["relationship"],
                rationale=item["rationale"],
                contraindications_note=item["contraindications_note"],
                confidence=item["confidence"],
                explanation=item["explanation"],
                citations_json=json.dumps(item["citations"]),
                knowledge_source=item["knowledge_source"],
                is_mock_knowledge=item["is_mock_knowledge"],
            )
            db.add(row)
            created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return created


def list_suggestions_for_session(
    db: Session,
    pharmacist: User,
    session_id: str,
) -> list[AlternativeSuggestion]:
    prescription_service.get_owned_session(db, pharmacist, session_id)
    return list(
        db.scalars(
            select(AlternativeSuggestion)
            .where(AlternativeSuggestion.session_id == session_id)
            .order_by(AlternativeSuggestion.medicine_id, AlternativeSuggestion.rank)
        )
    )


def list_suggestions_for_medicine(
    db: Session,
    pharmacist: User,
    session_id: str,
    medicine_id: str,
) -> list[AlternativeSuggestion]:
    prescription_service.get_owned_session(db, pharmacist, session_id)
    medicine = db.get(PrescriptionMedicine, medicine_id)
    if not medicine or medicine.session_id != session_id:
        raise HTTPException(status_code=404, detail="Medicine not found")

    rows = list(
        db.scalars(
            select(AlternativeSuggestion)
            .where(
                AlternativeSuggestion.session_id == session_id,
                AlternativeSuggestion.medicine_id == medicine_id,
            )
            .order_by(AlternativeSuggestion.rank)
        )
    )
    if rows:
        return rows

    # Lazy generate if pipeline ran before Milestone 4 migration data
    for item in suggest_for_medicine(medicine):
        row = AlternativeSuggestion(
            session_id=session_id,
            medicine_id=medicine.id,
            rank=item["rank"],
            source_medicine=item["source_medicine"],
            alternative_medicine_name=item["alternative_medicine_name"],
            strength=item["strength"],
            form=item["form"],
            route=item["route"],
            relationship=item["relationship"],
            rationale=item["rationale"],
            contraindications_note=item["contraindications_note"],
            confidence=item["confidence"],
            explanation=item["explanation"],
            citations_json=json.dumps(item["citations"]),
            knowledge_source=item["knowledge_source"],
            is_mock_knowledge=item["is_mock_knowledge"],
        )
        db.add(row)
        rows.append(row)
    if rows:
        db.commit()
        for row in rows:
            db.refresh(row)
    return rows


def record_feedback(
    db: Session,
    pharmacist: User,
    session_id: str,
    suggestion_id: str,
    *,
    decision: str,
    note: str | None = None,
) -> AlternativeFeedback:
    prescription_service.get_owned_session(db, pharmacist, session_id)
    suggestion = db.get(AlternativeSuggestion, suggestion_id)
    if not suggestion or suggestion.session_id != session_id:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    allowed = {"noted", "accepted_for_discussion", "rejected", "needs_more_evidence"}
    if decision not in allowed:
        raise HTTPException(status_code=422, detail="Invalid feedback decision")

    # One feedback row per pharmacist+suggestion (upsert-style)
    existing = db.scalar(
        select(AlternativeFeedback).where(
            AlternativeFeedback.suggestion_id == suggestion_id,
            AlternativeFeedback.pharmacist_user_id == pharmacist.id,
        )
    )
    if existing:
        existing.decision = decision
        existing.note = note
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    row = AlternativeFeedback(
        suggestion_id=suggestion_id,
        session_id=session_id,
        pharmacist_user_id=pharmacist.id,
        decision=decision,
        note=note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def evaluation_snapshot(db: Session) -> dict:
    """Research metrics for reviewer role — aggregate, no patient identifiers."""
    sessions_total = db.scalar(select(func.count()).select_from(ReviewSession)) or 0
    ocr_jobs = db.scalar(select(func.count()).select_from(OcrJob)) or 0
    medicines_total = db.scalar(select(func.count()).select_from(PrescriptionMedicine)) or 0

    status_rows = db.execute(
        select(PrescriptionMedicine.pharmacist_status, func.count())
        .group_by(PrescriptionMedicine.pharmacist_status)
    ).all()
    verification_by_status = {status: count for status, count in status_rows}

    formulary_matched = (
        db.scalar(
            select(func.count())
            .select_from(PrescriptionMedicine)
            .where(PrescriptionMedicine.formulary_matched.is_(True))
        )
        or 0
    )
    suggestions_total = db.scalar(select(func.count()).select_from(AlternativeSuggestion)) or 0
    feedback_rows = db.execute(
        select(AlternativeFeedback.decision, func.count()).group_by(AlternativeFeedback.decision)
    ).all()
    alternative_feedback_by_decision = {decision: count for decision, count in feedback_rows}

    avg_ocr = db.scalar(select(func.avg(OcrJob.confidence)))
    avg_parser = db.scalar(select(func.avg(PrescriptionMedicine.parser_confidence)))

    confirmed = verification_by_status.get("confirmed", 0)
    corrected = verification_by_status.get("corrected", 0)
    reviewed = confirmed + corrected + verification_by_status.get("unidentified", 0) + verification_by_status.get(
        "manual_review_required", 0
    )

    return {
        "phase": "5-therapeutic",
        "disclaimer": DISCLAIMER,
        "sessions_total": sessions_total,
        "ocr_jobs_total": ocr_jobs,
        "medicines_extracted_total": medicines_total,
        "formulary_matched_total": formulary_matched,
        "formulary_match_rate": (formulary_matched / medicines_total) if medicines_total else None,
        "verification_by_status": verification_by_status,
        "pharmacist_reviewed_total": reviewed,
        "override_or_correction_rate": (corrected / reviewed) if reviewed else None,
        "avg_ocr_confidence": float(avg_ocr) if avg_ocr is not None else None,
        "avg_parser_confidence": float(avg_parser) if avg_parser is not None else None,
        "alternative_suggestions_total": suggestions_total,
        "alternative_feedback_by_decision": alternative_feedback_by_decision,
        "knowledge_mode": "synthetic_drugbank_fda_seed",
    }
