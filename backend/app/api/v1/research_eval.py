"""Reviewer-only research evaluation API (DQ1–DQ4)."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.models.research_eval import (
    EvaluationCase,
    EvaluationSnapshot,
    RecommendationGoldStandard,
)
from app.security.rbac import require_reviewer
from app.services.research_eval import service as eval_service
from app.services.research_eval.import_dataset import import_dataset
from app.services.research_eval.snapshots import snapshot_to_dict

router = APIRouter(prefix="/research/eval", tags=["research-evaluation"])


class CreateCaseIn(BaseModel):
    case_code: str
    synthetic_prescription_ref: str | None = None
    dataset_version: str = "v1"
    approved_reviewer_pseudonym: str | None = None


class ImportDatasetIn(BaseModel):
    write_draft_gt: bool = False
    import_examples: bool = False
    reviewer_pseudonym: str = "REV-IMPORT"


class GroundTruthIn(BaseModel):
    evaluation_case_id: str
    instruction_text: str | None = None
    medicine_name: str | None = None
    strength: str | None = None
    dosage_form: str | None = None
    route: str | None = None
    dose: str | None = None
    frequency: str | None = None
    duration: str | None = None
    reviewer_pseudonym: str | None = None


class GoldStandardIn(BaseModel):
    evaluation_case_id: str
    reference_medicine: str
    candidate_medicine: str
    candidate_type: str
    candidate_rank: int | None = None
    same_active_ingredient: bool | None = None
    same_active_moiety: bool | None = None
    pharmacist_valid_candidate: bool
    pharmacist_reason: str | None = None
    evidence_source: str | None = None
    reviewer_pseudonym: str


class RagEvalIn(BaseModel):
    evaluation_case_id: str | None = None
    query: str


class XaiAssignIn(BaseModel):
    participant_pseudonym: str
    evaluation_case_id: str | None = None
    candidate_name: str
    candidate_type: str = "SAME_ACTIVE_MOIETY_PRODUCT"
    feature_values: dict[str, float] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)
    provenance: dict[str, Any] | None = None


class SurveyIn(BaseModel):
    participant_pseudonym: str
    condition: str
    evaluation_case_id: str | None = None
    likert: dict[str, int]
    free_text: str | None = None
    consent_confirmed: bool = True


@router.get("/status")
def research_eval_status(
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    return eval_service.combined_status(db)


@router.get("/cases")
def list_cases(
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    rows = list(db.scalars(select(EvaluationCase).order_by(EvaluationCase.created_at.desc())).all())
    return [
        {
            "id": r.id,
            "case_code": r.case_code,
            "synthetic_prescription_ref": r.synthetic_prescription_ref,
            "dataset_version": r.dataset_version,
            "ground_truth_status": r.ground_truth_status,
            "inclusion_status": r.inclusion_status,
            "exclusion_reason": r.exclusion_reason,
            "approved_reviewer_pseudonym": r.approved_reviewer_pseudonym,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/cases")
def create_case(
    body: CreateCaseIn,
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    row = eval_service.create_evaluation_case(
        db,
        case_code=body.case_code,
        synthetic_prescription_ref=body.synthetic_prescription_ref,
        dataset_version=body.dataset_version,
        approved_reviewer_pseudonym=body.approved_reviewer_pseudonym,
    )
    return {"id": row.id, "case_code": row.case_code}


@router.post("/import")
def import_eval_dataset(
    body: ImportDatasetIn,
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """
    Load cases/gold/survey from data/research_evaluation/*.json.
    By default only confirmed ground truth is written (pharmacist_confirmed=true).
    Set write_draft_gt=true to store draft fields for pharmacist confirmation in-app.
    import_examples=true imports example gold rows — smoke test only, not study evidence.
    """
    from app.services.research_eval import import_dataset as import_mod

    if body.write_draft_gt:
        summary = import_mod._import_with_drafts(
            db,
            cases_path=None,
            gold_path=None,
            survey_path=None,
            import_examples=body.import_examples,
            reviewer_pseudonym=body.reviewer_pseudonym,
        )
    else:
        summary = import_dataset(
            db,
            confirm_marked=True,
            import_examples=body.import_examples,
            reviewer_pseudonym=body.reviewer_pseudonym,
        )
    summary["status"] = eval_service.combined_status(db)
    return summary


@router.get("/cases/{evaluation_case_id}/ground-truth")
def get_ground_truth(
    evaluation_case_id: str,
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    from app.models.research_eval import GroundTruthRecord

    case = db.get(EvaluationCase, evaluation_case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    gt = db.scalars(
        select(GroundTruthRecord)
        .where(GroundTruthRecord.evaluation_case_id == evaluation_case_id)
        .order_by(GroundTruthRecord.created_at.desc())
    ).first()
    return {
        "case": {
            "id": case.id,
            "case_code": case.case_code,
            "ground_truth_status": case.ground_truth_status,
        },
        "ground_truth": None
        if not gt
        else {
            "id": gt.id,
            "instruction_text": gt.instruction_text,
            "medicine_name": gt.medicine_name,
            "strength": gt.strength,
            "dosage_form": gt.dosage_form,
            "route": gt.route,
            "dose": gt.dose,
            "frequency": gt.frequency,
            "duration": gt.duration,
            "source": gt.source,
        },
    }


@router.post("/ground-truth")
def upsert_gt(
    body: GroundTruthIn,
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    fields = body.model_dump(
        exclude={"evaluation_case_id", "instruction_text", "reviewer_pseudonym"}
    )
    gt = eval_service.upsert_ground_truth(
        db,
        evaluation_case_id=body.evaluation_case_id,
        instruction_text=body.instruction_text,
        fields=fields,
        reviewer_pseudonym=body.reviewer_pseudonym,
    )
    return {"id": gt.id, "evaluation_case_id": gt.evaluation_case_id}


@router.get("/dq1/framework")
def dq1_framework(_reviewer: User = Depends(require_reviewer)):
    """Reviewer DQ1 framing: Spec question, reframed research question, engine thesis roles."""
    from app.services.research_eval.ocr_engines import (
        CONFIGURED_ENGINES,
        DQ1_RESEARCH_QUESTION,
        DQ1_SPEC_QUESTION,
        ENGINE_THESIS_ROLES,
    )

    return {
        "research_question": DQ1_RESEARCH_QUESTION,
        "spec_question": DQ1_SPEC_QUESTION,
        "production_primary": "google_vision",
        "configured_engines": list(CONFIGURED_ENGINES),
        "engine_roles": ENGINE_THESIS_ROLES,
        "metrics": ["wer", "cer", "medicine_name_exact_match", "medicine_name_f1", "field_accuracy", "processing_time_ms"],
        "ground_truth_rule": "Pharmacist-confirmed instruction and fields only.",
    }


@router.post("/dq1/run/{evaluation_case_id}")
def run_dq1(
    evaluation_case_id: str,
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    try:
        return eval_service.run_dq1_ocr_evaluation(db, evaluation_case_id=evaluation_case_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/dq2/gold-standard")
def add_gold(
    body: GoldStandardIn,
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    import uuid

    row = RecommendationGoldStandard(
        id=str(uuid.uuid4()),
        **body.model_dump(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.post("/dq2/run")
def run_dq2(
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    return eval_service.run_dq2_recommendation_evaluation(db)


@router.post("/dq3/run")
def run_dq3(
    body: RagEvalIn,
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    return eval_service.run_dq3_rag_evaluation(
        db,
        evaluation_case_id=body.evaluation_case_id,
        query=body.query,
    )


@router.post("/dq4/assign")
def assign_dq4(
    body: XaiAssignIn,
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    return eval_service.assign_dq4_conditions(
        db,
        participant_pseudonym=body.participant_pseudonym,
        evaluation_case_id=body.evaluation_case_id,
        candidate={"name": body.candidate_name, "candidate_type": body.candidate_type},
        feature_values=body.feature_values or {"mcs": 0.8, "route_match": 1.0, "strength": 0.9},
        weights=body.weights or {"mcs": 0.3, "route_match": 0.4, "strength": 0.3},
        provenance=body.provenance,
    )


@router.post("/dq4/survey")
def survey(
    body: SurveyIn,
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """
    Store one pseudonymised Likert row after export from an external questionnaire.
    The survey is not collected in the PharmaAssist UI — prefer JSON import for bulk loads.
    """
    row = eval_service.submit_survey_response(
        db,
        participant_pseudonym=body.participant_pseudonym,
        condition=body.condition,
        evaluation_case_id=body.evaluation_case_id,
        likert=body.likert,
        free_text=body.free_text,
        consent_confirmed=body.consent_confirmed,
    )
    return {"id": row.id, "note": "External questionnaire import row stored."}


@router.get("/dq4/summary")
def dq4_summary(
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    return eval_service.dq4_survey_summary(db)


@router.post("/snapshots/freeze")
def freeze_snapshot(
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    return eval_service.freeze_combined_snapshot(db)


@router.get("/snapshots")
def list_snapshots(
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    rows = list(
        db.scalars(select(EvaluationSnapshot).order_by(EvaluationSnapshot.created_at.desc())).all()
    )
    return [snapshot_to_dict(r) for r in rows]


@router.get("/export/csv")
def export_csv(
    kind: str = "status",
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """Export aggregate research metrics; no participant PII fields."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    if kind == "survey":
        summary = eval_service.dq4_survey_summary(db)
        writer.writerow(["condition", "construct", "mean", "std", "min", "max", "n"])
        for cond, constructs in (summary.get("by_condition") or {}).items():
            for construct, stats in constructs.items():
                writer.writerow(
                    [
                        cond,
                        construct,
                        stats.get("mean"),
                        stats.get("std"),
                        stats.get("min"),
                        stats.get("max"),
                        stats.get("n"),
                    ]
                )
    else:
        status = eval_service.combined_status(db)
        writer.writerow(["key", "value"])
        for k, v in status.get("counts", {}).items():
            writer.writerow([k, v])
        writer.writerow(["sample_claims", json.dumps(status.get("sample_claims"))])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=research_eval_{kind}.csv"},
    )


@router.get("/export/json")
def export_json(
    _reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    return {
        "status": eval_service.combined_status(db),
        "dq4": eval_service.dq4_survey_summary(db),
        "snapshots": [
            snapshot_to_dict(r)
            for r in db.scalars(
                select(EvaluationSnapshot).order_by(EvaluationSnapshot.created_at.desc()).limit(20)
            ).all()
        ],
    }
