"""Immutable evaluation snapshots for reproducible dissertation metrics."""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.research_eval import (
    EvaluationCase,
    EvaluationSnapshot,
    PharmacistSurveyResponse,
)


def _git_hash() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        return out.strip() or None
    except Exception:
        return None


def create_snapshot(
    db: Session,
    *,
    results: dict[str, Any] | None = None,
    ocr_config: dict | None = None,
    retrieval_config: dict | None = None,
    explanation_config: dict | None = None,
    matching_algorithm_version: str = "sprint1-1.0",
    catalogue_version: str | None = None,
    ground_truth_version: str = "1",
) -> EvaluationSnapshot:
    included = list(
        db.scalars(
            select(EvaluationCase).where(EvaluationCase.inclusion_status == "included")
        ).all()
    )
    excluded = list(
        db.scalars(
            select(EvaluationCase).where(EvaluationCase.inclusion_status != "included")
        ).all()
    )
    pharmacist_count = (
        db.scalar(
            select(func.count(func.distinct(PharmacistSurveyResponse.participant_pseudonym)))
        )
        or 0
    )
    snap = EvaluationSnapshot(
        id=str(uuid.uuid4()),
        snapshot_code=f"SNAP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}",
        included_case_ids_json=json.dumps([c.id for c in included]),
        excluded_cases_json=json.dumps(
            [{"id": c.id, "reason": c.exclusion_reason} for c in excluded]
        ),
        ground_truth_version=ground_truth_version,
        catalogue_version=catalogue_version,
        ocr_config_json=json.dumps(ocr_config or {}),
        matching_algorithm_version=matching_algorithm_version,
        retrieval_config_json=json.dumps(retrieval_config or {}),
        explanation_config_json=json.dumps(explanation_config or {}),
        metric_implementation_version="1.0.0",
        git_commit_hash=_git_hash(),
        prescription_count=len(included),
        pharmacist_count=int(pharmacist_count),
        results_json=json.dumps(results or {}, default=str),
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


def snapshot_to_dict(snap: EvaluationSnapshot) -> dict[str, Any]:
    return {
        "id": snap.id,
        "snapshot_code": snap.snapshot_code,
        "included_case_ids": json.loads(snap.included_case_ids_json or "[]"),
        "excluded_cases": json.loads(snap.excluded_cases_json or "[]"),
        "ground_truth_version": snap.ground_truth_version,
        "catalogue_version": snap.catalogue_version,
        "ocr_config": json.loads(snap.ocr_config_json or "{}"),
        "matching_algorithm_version": snap.matching_algorithm_version,
        "retrieval_config": json.loads(snap.retrieval_config_json or "{}"),
        "explanation_config": json.loads(snap.explanation_config_json or "{}"),
        "metric_implementation_version": snap.metric_implementation_version,
        "git_commit_hash": snap.git_commit_hash,
        "prescription_count": snap.prescription_count,
        "pharmacist_count": snap.pharmacist_count,
        "results": json.loads(snap.results_json or "{}"),
        "created_at": snap.created_at.isoformat() if snap.created_at else None,
    }
