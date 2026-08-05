"""Import research evaluation datasets from JSON files (no fabricated metrics)."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.research_eval import (
    EvaluationCase,
    GroundTruthRecord,
    PharmacistSurveyResponse,
    RecommendationGoldStandard,
)

DEFAULT_ROOT = Path(__file__).resolve().parents[4] / "data" / "research_evaluation"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def import_cases(
    db: Session,
    payload: dict[str, Any],
    *,
    confirm_marked: bool = True,
    reviewer_pseudonym: str = "REV-IMPORT",
) -> dict[str, int]:
    dataset_version = str(payload.get("dataset_version") or "synthetic_v1")
    created = updated = gt_written = skipped_gt = 0
    for row in payload.get("cases") or []:
        code = str(row["case_code"]).strip()
        existing = db.scalar(select(EvaluationCase).where(EvaluationCase.case_code == code))
        if existing:
            case = existing
            case.synthetic_prescription_ref = row.get("synthetic_prescription_ref")
            case.dataset_version = dataset_version
            case.inclusion_status = row.get("inclusion_status") or "included"
            case.exclusion_reason = row.get("exclusion_reason")
            updated += 1
        else:
            case = EvaluationCase(
                id=str(uuid.uuid4()),
                case_code=code,
                synthetic_prescription_ref=row.get("synthetic_prescription_ref"),
                dataset_version=dataset_version,
                ground_truth_status="pending",
                inclusion_status=row.get("inclusion_status") or "included",
                exclusion_reason=row.get("exclusion_reason"),
                approved_reviewer_pseudonym=reviewer_pseudonym,
            )
            db.add(case)
            db.flush()
            created += 1

        confirmed = bool(row.get("pharmacist_confirmed"))
        if confirm_marked and not confirmed:
            skipped_gt += 1
            continue

        fields = row.get("fields") or {}
        gt = GroundTruthRecord(
            id=str(uuid.uuid4()),
            evaluation_case_id=case.id,
            instruction_text=row.get("instruction_text"),
            medicine_name=fields.get("medicine_name"),
            strength=fields.get("strength"),
            dosage_form=fields.get("dosage_form"),
            route=fields.get("route"),
            dose=fields.get("dose"),
            frequency=fields.get("frequency"),
            duration=fields.get("duration"),
            source="pharmacist_confirmed" if confirmed else "draft_import",
            version="1",
        )
        db.add(gt)
        case.ground_truth_status = "confirmed" if confirmed else "draft"
        if confirmed:
            case.approved_reviewer_pseudonym = reviewer_pseudonym
        gt_written += 1

    db.commit()
    return {
        "cases_created": created,
        "cases_updated": updated,
        "ground_truth_written": gt_written,
        "ground_truth_skipped_unconfirmed": skipped_gt,
    }


def import_gold(
    db: Session,
    payload: dict[str, Any],
    *,
    import_examples: bool = False,
) -> dict[str, int]:
    inserted = skipped = 0
    for row in payload.get("records") or []:
        if row.get("_example_only") and not import_examples:
            skipped += 1
            continue
        code = str(row["case_code"]).strip()
        case = db.scalar(select(EvaluationCase).where(EvaluationCase.case_code == code))
        if not case:
            skipped += 1
            continue
        db.add(
            RecommendationGoldStandard(
                id=str(uuid.uuid4()),
                evaluation_case_id=case.id,
                reference_medicine=row["reference_medicine"],
                candidate_medicine=row["candidate_medicine"],
                candidate_type=row["candidate_type"],
                candidate_rank=row.get("candidate_rank"),
                same_active_ingredient=row.get("same_active_ingredient"),
                same_active_moiety=row.get("same_active_moiety"),
                pharmacist_valid_candidate=bool(row["pharmacist_valid_candidate"]),
                pharmacist_reason=row.get("pharmacist_reason"),
                evidence_source=row.get("evidence_source"),
                reviewer_pseudonym=row["reviewer_pseudonym"],
            )
        )
        inserted += 1
    db.commit()
    return {"gold_inserted": inserted, "gold_skipped": skipped}


def import_survey(
    db: Session,
    payload: dict[str, Any],
) -> dict[str, int]:
    inserted = 0
    for row in payload.get("responses") or []:
        case_id = None
        if row.get("case_code"):
            case = db.scalar(
                select(EvaluationCase).where(EvaluationCase.case_code == str(row["case_code"]))
            )
            case_id = case.id if case else None
        likert = dict(row.get("likert") or {})
        for forbidden in ("name", "email", "registration", "workplace", "ip"):
            likert.pop(forbidden, None)
        db.add(
            PharmacistSurveyResponse(
                id=str(uuid.uuid4()),
                participant_pseudonym=str(row["participant_pseudonym"]),
                condition=str(row["condition"]),
                evaluation_case_id=case_id,
                likert_json=json.dumps(likert),
                free_text=row.get("free_text"),
                questionnaire_version=str(
                    payload.get("questionnaire_version") or row.get("questionnaire_version") or "1.2"
                ),
                consent_confirmed=bool(row.get("consent_confirmed", True)),
            )
        )
        inserted += 1
    db.commit()
    return {"survey_inserted": inserted}


def import_dataset(
    db: Session,
    *,
    cases_path: Path | None = None,
    gold_path: Path | None = None,
    survey_path: Path | None = None,
    confirm_marked: bool = True,
    import_examples: bool = False,
    reviewer_pseudonym: str = "REV-IMPORT",
) -> dict[str, Any]:
    root = DEFAULT_ROOT
    summary: dict[str, Any] = {"dataset_root": str(root)}
    if cases_path or (root / "cases_v1.json").exists():
        path = cases_path or (root / "cases_v1.json")
        summary["cases"] = import_cases(
            db,
            _load_json(path),
            confirm_marked=confirm_marked,
            reviewer_pseudonym=reviewer_pseudonym,
        )
        summary["cases_file"] = str(path)
    if gold_path or (root / "gold_standards_v1.json").exists():
        path = gold_path or (root / "gold_standards_v1.json")
        summary["gold"] = import_gold(db, _load_json(path), import_examples=import_examples)
        summary["gold_file"] = str(path)
    if survey_path or (root / "survey_responses_v1.json").exists():
        path = survey_path or (root / "survey_responses_v1.json")
        summary["survey"] = import_survey(db, _load_json(path))
        summary["survey_file"] = str(path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Import PharmaAssist research evaluation dataset")
    parser.add_argument("--cases", type=Path, default=None)
    parser.add_argument("--gold", type=Path, default=None)
    parser.add_argument("--survey", type=Path, default=None)
    parser.add_argument(
        "--import-examples",
        action="store_true",
        help="Import _example_only gold rows (smoke test only — not dissertation evidence)",
    )
    parser.add_argument(
        "--write-draft-gt",
        action="store_true",
        help="Also write draft ground truth for unconfirmed cases (status=draft)",
    )
    parser.add_argument("--reviewer-pseudonym", default="REV-IMPORT")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # Default: create/update cases; write GT only when pharmacist_confirmed=true.
        if args.write_draft_gt:
            summary = _import_with_drafts(
                db,
                cases_path=args.cases,
                gold_path=args.gold,
                survey_path=args.survey,
                import_examples=args.import_examples,
                reviewer_pseudonym=args.reviewer_pseudonym,
            )
        else:
            summary = import_dataset(
                db,
                cases_path=args.cases,
                gold_path=args.gold,
                survey_path=args.survey,
                confirm_marked=True,
                import_examples=args.import_examples,
                reviewer_pseudonym=args.reviewer_pseudonym,
            )
        print(json.dumps(summary, indent=2))
        print(
            "\nNext: set pharmacist_confirmed=true in cases_v1.json after HITL review, "
            "re-import, then run DQ evaluations. Do not invent metrics."
        )
    finally:
        db.close()


def _import_with_drafts(
    db: Session,
    *,
    cases_path: Path | None,
    gold_path: Path | None,
    survey_path: Path | None,
    import_examples: bool,
    reviewer_pseudonym: str,
) -> dict[str, Any]:
    """Write GT for every case; mark confirmed only when pharmacist_confirmed=true."""
    root = DEFAULT_ROOT
    path = cases_path or (root / "cases_v1.json")
    payload = _load_json(path)
    # Force write all by treating confirm_marked=False path via temporary flags
    for row in payload.get("cases") or []:
        # ensure import_cases writes: when confirm_marked=False it writes all
        pass
    summary: dict[str, Any] = {
        "cases": import_cases(
            db,
            payload,
            confirm_marked=False,
            reviewer_pseudonym=reviewer_pseudonym,
        ),
        "cases_file": str(path),
        "note": "Draft GT written for unconfirmed cases; DQ1 should prefer confirmed only.",
    }
    if gold_path or (root / "gold_standards_v1.json").exists():
        gpath = gold_path or (root / "gold_standards_v1.json")
        summary["gold"] = import_gold(db, _load_json(gpath), import_examples=import_examples)
    if survey_path or (root / "survey_responses_v1.json").exists():
        spath = survey_path or (root / "survey_responses_v1.json")
        summary["survey"] = import_survey(db, _load_json(spath))
    return summary


if __name__ == "__main__":
    main()
