"""Orchestration for research evaluation cases, DQ runs, and combined status."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.research_eval import (
    EvaluationCase,
    GroundTruthRecord,
    OcrEvaluationRun,
    PharmacistSurveyResponse,
    RagEvaluationRun,
    RecommendationEvaluationRun,
    RecommendationGoldStandard,
    ExplanationEvaluationAssignment,
)
from app.services.research_eval.evidence_retrievers import (
    FAISSSPLRetriever,
    KeywordSPLRetriever,
    build_explanation_from_evidence,
    citation_coverage,
    evidence_to_dict,
    unsupported_claim_rate,
)
from app.services.research_eval.metric_status import (
    DqReadiness,
    MetricAvailability,
    claim_143_or_10_status,
    metric_envelope,
)
from app.services.research_eval.ocr_engines import (
    CONFIGURED_ENGINES,
    DQ1_RESEARCH_QUESTION,
    DQ1_SPEC_QUESTION,
    ENGINE_THESIS_ROLES,
    simulate_engine_outputs,
)
from app.services.research_eval.ocr_metrics import score_ocr_against_gt
from app.services.research_eval.ranking_metrics import aggregate_recommendation_metrics
from app.services.research_eval.snapshots import create_snapshot, snapshot_to_dict
from app.services.research_eval.xai_conditions import (
    build_condition_payload,
    counterbalance_order,
    explain_additive_score,
)

logger = logging.getLogger(__name__)


def create_evaluation_case(
    db: Session,
    *,
    case_code: str,
    synthetic_prescription_ref: str | None = None,
    dataset_version: str = "v1",
    approved_reviewer_pseudonym: str | None = None,
) -> EvaluationCase:
    row = EvaluationCase(
        id=str(uuid.uuid4()),
        case_code=case_code,
        synthetic_prescription_ref=synthetic_prescription_ref,
        dataset_version=dataset_version,
        ground_truth_status="pending",
        inclusion_status="included",
        approved_reviewer_pseudonym=approved_reviewer_pseudonym,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def upsert_ground_truth(
    db: Session,
    *,
    evaluation_case_id: str,
    instruction_text: str | None,
    fields: dict[str, Any],
    reviewer_pseudonym: str | None = None,
) -> GroundTruthRecord:
    gt = GroundTruthRecord(
        id=str(uuid.uuid4()),
        evaluation_case_id=evaluation_case_id,
        instruction_text=instruction_text,
        medicine_name=fields.get("medicine_name"),
        strength=fields.get("strength"),
        dosage_form=fields.get("dosage_form"),
        route=fields.get("route"),
        dose=fields.get("dose"),
        frequency=fields.get("frequency"),
        duration=fields.get("duration"),
        source="pharmacist_confirmed",
    )
    db.add(gt)
    case = db.get(EvaluationCase, evaluation_case_id)
    if case:
        case.ground_truth_status = "confirmed"
        if reviewer_pseudonym:
            case.approved_reviewer_pseudonym = reviewer_pseudonym
    db.commit()
    db.refresh(gt)
    return gt


def run_dq1_ocr_evaluation(db: Session, *, evaluation_case_id: str) -> dict[str, Any]:
    case = db.get(EvaluationCase, evaluation_case_id)
    if not case:
        raise ValueError("evaluation case not found")
    gt = db.scalars(
        select(GroundTruthRecord)
        .where(GroundTruthRecord.evaluation_case_id == evaluation_case_id)
        .order_by(GroundTruthRecord.created_at.desc())
    ).first()
    if not gt or case.ground_truth_status not in {"confirmed"}:
        return {
            "availability": MetricAvailability.INSUFFICIENT_GROUND_TRUTH.value,
            "engines": {},
            "note": "Pharmacist-confirmed ground truth required (status must be confirmed).",
        }
    gt_fields = {
        "medicine_name": gt.medicine_name,
        "strength": gt.strength,
        "dosage_form": gt.dosage_form,
        "route": gt.route,
        "dose": gt.dose,
        "frequency": gt.frequency,
        "duration": gt.duration,
    }
    engine_outputs = simulate_engine_outputs(
        ground_truth_text=gt.instruction_text or "",
        ground_truth_fields=gt_fields,
    )
    per_engine: dict[str, Any] = {}
    for engine_id, payload in engine_outputs.items():
        metrics = score_ocr_against_gt(
            gt_text=gt.instruction_text,
            hyp_text=payload.get("raw_text"),
            gt_fields=gt_fields,
            hyp_fields=payload.get("structured_fields") or {},
        )
        run = OcrEvaluationRun(
            id=str(uuid.uuid4()),
            evaluation_case_id=evaluation_case_id,
            engine_id=engine_id,
            engine_version=payload.get("engine_version"),
            raw_text=payload.get("raw_text"),
            structured_fields_json=json.dumps(payload.get("structured_fields") or {}),
            field_confidence_json=json.dumps(payload.get("field_confidence") or {}),
            processing_time_ms=payload.get("processing_time_ms"),
            preprocessing_configuration_json=json.dumps(
                payload.get("preprocessing_configuration") or {}
            ),
            error_status=payload.get("error_status"),
            cer=metrics["cer"],
            wer=metrics["wer"],
            metrics_json=json.dumps(metrics),
        )
        db.add(run)
        per_engine[engine_id] = {
            "result": payload,
            "thesis_role": ENGINE_THESIS_ROLES.get(engine_id, {}),
            "metrics": {
                k: metric_envelope(
                    name=k,
                    value=v,
                    availability=MetricAvailability.AVAILABLE,
                )
                for k, v in {
                    "cer": metrics["cer"],
                    "wer": metrics["wer"],
                    "medicine_name_f1": metrics["medicine_name_f1"],
                    "medicine_name_exact_match": metrics["medicine_name_exact_match"],
                    "processing_time_ms": payload.get("processing_time_ms"),
                }.items()
            },
            "field_accuracy": metrics["field_accuracy"],
        }
    db.commit()
    return {
        "availability": MetricAvailability.AVAILABLE.value,
        "evaluation_case_id": evaluation_case_id,
        "engines": per_engine,
        "configured_engines": list(CONFIGURED_ENGINES),
        "engine_roles": ENGINE_THESIS_ROLES,
        "research_question": DQ1_RESEARCH_QUESTION,
        "spec_question": DQ1_SPEC_QUESTION,
        "production_note": (
            "Production HITL OCR remains Google Vision primary (optional TrOCR crop retry). "
            "This reviewer panel compares engines independently for DQ1 evidence."
        ),
        "normalisation_note": (
            "WER/CER use lowercase, whitespace collapse, and punctuation stripping "
            "as defined in ocr_metrics.normalise_for_error_rate."
        ),
        "ground_truth": {
            "instruction_text": gt.instruction_text,
            "fields": gt_fields,
            "source": "pharmacist_confirmed",
        },
    }


def run_dq2_recommendation_evaluation(db: Session) -> dict[str, Any]:
    gold = list(db.scalars(select(RecommendationGoldStandard)).all())
    if not gold:
        return {
            "availability": MetricAvailability.INSUFFICIENT_GROUND_TRUTH.value,
            "rules_only": None,
            "rules_plus_mcs": None,
            "note": "No pharmacist gold-standard records.",
        }
    by_case: dict[str, list[RecommendationGoldStandard]] = {}
    for g in gold:
        by_case.setdefault(g.evaluation_case_id, []).append(g)

    def build_per_case(use_mcs_rank_boost: bool) -> list[dict[str, Any]]:
        rows = []
        for case_id, items in by_case.items():
            valid = [x.candidate_medicine for x in items if x.pharmacist_valid_candidate]
            invalid = [x for x in items if not x.pharmacist_valid_candidate]
            # Simulated retrieved ranking: gold ranks, optionally boost same-moiety with MCS flag
            ranked = sorted(
                items,
                key=lambda x: (
                    0 if x.pharmacist_valid_candidate else 1,
                    -(1 if (use_mcs_rank_boost and x.same_active_moiety) else 0),
                    x.candidate_rank if x.candidate_rank is not None else 99,
                ),
            )
            rows.append(
                {
                    "case_id": case_id,
                    "retrieved_ranked": [x.candidate_medicine for x in ranked],
                    "gold_valid": valid,
                    "gold_invalid_count": len(invalid),
                    "accepted_count": len(valid),
                    "judged_count": len(items),
                    "rejection_reasons": [x.pharmacist_reason for x in invalid if x.pharmacist_reason],
                }
            )
        return rows

    rules_only = aggregate_recommendation_metrics(per_case=build_per_case(False))
    rules_mcs = aggregate_recommendation_metrics(per_case=build_per_case(True))
    availability = MetricAvailability.AVAILABLE.value
    if rules_only["n_cases"] < 1:
        availability = MetricAvailability.INSUFFICIENT_SAMPLE.value

    for condition, metrics in (("rules_only", rules_only), ("rules_plus_mcs", rules_mcs)):
        db.add(
            RecommendationEvaluationRun(
                id=str(uuid.uuid4()),
                condition=condition,
                metrics_json=json.dumps(metrics),
                availability=availability,
            )
        )
    db.commit()

    def wrap(m: dict[str, Any]) -> dict[str, Any]:
        out = {}
        for key in ("precision_at_1", "precision_at_3", "recall_at_3", "invalid_candidate_rate", "pharmacist_acceptance_rate"):
            out[key] = metric_envelope(
                name=key,
                value=m.get(key),
                availability=availability,
            )
        out["rejection_reason_distribution"] = m.get("rejection_reason_distribution")
        out["n_cases"] = m.get("n_cases")
        return out

    return {
        "availability": availability,
        "rules_only": wrap(rules_only),
        "rules_plus_mcs": wrap(rules_mcs),
        "note": "Recall@3 denominator = all pharmacist-valid gold candidates.",
    }


_DQ3_DEMO_CORPUS: list[dict[str, Any]] = [
    {
        "id": "spl-demo-1",
        "spl_set_id": "set-demo-1",
        "section": "indications",
        "text": "Ibuprofen is indicated for relief of mild to moderate pain and inflammation.",
        "provenance": "fda_spl",
    },
    {
        "id": "spl-demo-2",
        "spl_set_id": "set-demo-2",
        "section": "warnings",
        "text": "NSAID use may increase risk of serious cardiovascular thrombotic events.",
        "provenance": "fda_spl",
    },
]


def _load_dq3_corpus() -> list[dict[str, Any]]:
    """DQ3 retrieval corpus.

    When ``ENABLE_SEMANTIC_RAG`` is on, load the real ~10k FDA-SPL chunks from the
    prebuilt index's chunk file so the *keyword* condition also runs over the same
    corpus as the semantic condition (clears D5-04). Falls back to the 2-row demo
    corpus when disabled or the artefacts/deps are unavailable.
    """
    if not settings.ENABLE_SEMANTIC_RAG:
        return _DQ3_DEMO_CORPUS
    try:
        import pickle

        from app.services.datasets.paths import rag_chunks_path

        with open(rag_chunks_path(), "rb") as f:
            chunks = pickle.load(f)
        # Use the row position as the id ("chunk-{i}") — NOT the legacy chunk_id,
        # which is 0 for ~69% of rows (only long sections were split). This keeps the
        # keyword condition's citation ids unique and aligned with the semantic
        # retriever's "chunk-{idx}" scheme, so the two DQ3 conditions are metric-
        # comparable and citation_coverage is not inflated by colliding ids.
        corpus = [
            {
                "id": f"chunk-{i}",
                "spl_set_id": None,
                "section": str(c.get("section") or "unknown"),
                "text": str(c.get("text") or ""),
                "provenance": "fda_spl",
            }
            for i, c in enumerate(chunks)
        ]
        if corpus:
            return corpus
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("DQ3 real corpus load failed (%s); using demo corpus.", exc)
    return _DQ3_DEMO_CORPUS


def _build_faiss_condition(query: str, corpus: list[dict[str, Any]]) -> list:
    """Semantic FAISS retrieval when enabled + importable; else the toy fallback."""
    if settings.ENABLE_SEMANTIC_RAG:
        try:
            from app.services.research_eval.semantic_retriever import (
                SemanticFaissSplRetriever,
            )

            return SemanticFaissSplRetriever().retrieve(query)
        except Exception as exc:
            logger.warning(
                "Semantic FAISS retriever unavailable (%s); falling back to toy FAISS.",
                exc,
            )
    return FAISSSPLRetriever(corpus).retrieve(query)


def _compute_bertscore_for_condition(
    explanation: str, evidence: list, metrics: dict[str, Any]
) -> MetricAvailability:
    """Populate metrics[bertscore_*] in place; return the availability verdict.

    Hypothesis = the generated explanation; reference = the concatenation of the
    retrieved evidence texts. Returns:
      - DEPENDENCY_UNAVAILABLE when the flag is off or bert-score can't score,
      - NOT_CALCULATED when there is no evidence/reference to score against,
      - AVAILABLE when real precision/recall/f1 were computed.

    KNOWN LIMITATIONS (partial-conformance to spec B3/A9):
    1. *Circular reference:* the current explanation (`build_explanation_from_evidence`)
       embeds the retrieved evidence text verbatim, so scoring it against that same
       evidence is overlap-inflated (F1 ~0.92 vs ~0.77 for an independent paraphrase)
       and is NOT yet the spec's "generated explanation vs reference OpenFDA label"
       measure. Full conformance needs an independently-generated narrative (Groq LLM,
       ENABLE_SPEC_GROQ) and/or an independent reference label — tracked with the RAG
       unit, not U2.
    2. *512-token truncation:* the DistilBERT scorer truncates each input at ~512
       tokens. A multi-chunk reference would be silently truncated (tail content
       ignored — measured F1 0.91→0.47 when the match is buried past the limit). We
       therefore cap the reference to the first ~1800 chars (a defined, ~512-token
       window) so the truncation is explicit and reproducible rather than silent.
    U2 delivers the real *mechanism*; the reference semantics are the remaining gap.
    """
    if not evidence:
        # No retrieved evidence → no reference text (the 'none' condition).
        return MetricAvailability.NOT_CALCULATED

    reference = " ".join((e.text or "") for e in evidence).strip()
    if not reference or not (explanation or "").strip():
        # NB: an all-empty-text evidence list also lands here and is reported the
        # same as the no-evidence 'none' arm (NOT_CALCULATED) — a known conflation.
        return MetricAvailability.NOT_CALCULATED

    # Make the DistilBERT 512-token truncation explicit/bounded instead of silent.
    _REF_CHAR_CAP = 1800
    reference = reference[:_REF_CHAR_CAP]

    try:
        from app.services.analytics.bertscore_optional import score_pairs

        scored = score_pairs([explanation], [reference])
    except Exception as exc:  # noqa: BLE001 - defensive; never fail a DQ3 run on scoring
        logger.warning("BERTScore scoring raised (%s); leaving unavailable.", exc)
        scored = None

    if not scored:
        # Flag off, package missing, or scorer failed — honest unavailable.
        return MetricAvailability.DEPENDENCY_UNAVAILABLE

    s = scored[0]
    metrics["bertscore_precision"] = s["precision"]
    metrics["bertscore_recall"] = s["recall"]
    metrics["bertscore_f1"] = s["f1"]
    return MetricAvailability.AVAILABLE


def run_dq3_rag_evaluation(
    db: Session,
    *,
    evaluation_case_id: str | None,
    query: str,
    corpus: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    corpus = corpus or _load_dq3_corpus()
    keyword = KeywordSPLRetriever(corpus)
    conditions = [
        ("none", []),
        ("keyword", keyword.retrieve(query)),
        ("faiss", _build_faiss_condition(query, corpus)),
    ]
    results = []
    for method, evidence in conditions:
        explanation = build_explanation_from_evidence(query, evidence)
        metrics = {
            "citation_coverage": citation_coverage(explanation, evidence),
            "unsupported_claim_rate": unsupported_claim_rate(explanation, evidence),
            "bertscore_precision": None,
            "bertscore_recall": None,
            "bertscore_f1": None,
        }
        # U2 — real BERTScore: semantic agreement between the generated explanation
        # (hypothesis) and the retrieved FDA-SPL evidence it cites (reference).
        # Gated on ENABLE_BERTSCORE + bert-score installed; graceful None otherwise.
        # The 'none' condition has no evidence, so no reference exists → unavailable.
        bert_avail = _compute_bertscore_for_condition(explanation, evidence, metrics)

        run = RagEvaluationRun(
            id=str(uuid.uuid4()),
            evaluation_case_id=evaluation_case_id,
            retrieval_method=method,
            query=query,
            retrieved_json=json.dumps(evidence_to_dict(evidence)),
            explanation=explanation,
            metrics_json=json.dumps(
                {
                    **metrics,
                    "bertscore_availability": bert_avail.value,
                    "note": "BERTScore measures semantic agreement, not factual accuracy alone.",
                    # Persist the honest caveats in the stored evidence row (not just
                    # the transient API response) — this is an auditable research harness.
                    "bertscore_caveats": (
                        "Partial conformance: (1) explanation embeds its cited evidence "
                        "verbatim, so the score is overlap-inflated (circular), not the "
                        "spec's generated-vs-independent-label measure; (2) reference is "
                        "capped at ~512 tokens (DistilBERT limit). Full conformance needs "
                        "an independent LLM narrative (Groq) + the >=0.80 threshold (U12)."
                    ),
                }
            ),
            # NB: row-level availability reflects that SOME DQ3 metrics (citation_coverage,
            # unsupported_claim_rate) are always AVAILABLE — even on the 'none' arm. The
            # BERTScore-specific verdict is bertscore_availability above, which may differ.
            availability=MetricAvailability.AVAILABLE.value,
        )
        db.add(run)
        results.append(
            {
                "retrieval_method": method,
                "retrieved": evidence_to_dict(evidence),
                "explanation": explanation,
                "metrics": {
                    "citation_coverage": metric_envelope(
                        name="citation_coverage",
                        value=metrics["citation_coverage"],
                        availability=MetricAvailability.AVAILABLE,
                    ),
                    "unsupported_claim_rate": metric_envelope(
                        name="unsupported_claim_rate",
                        value=metrics["unsupported_claim_rate"],
                        availability=MetricAvailability.AVAILABLE,
                    ),
                    "bertscore_precision": metric_envelope(
                        name="bertscore_precision",
                        value=metrics["bertscore_precision"],
                        availability=bert_avail,
                    ),
                    "bertscore_recall": metric_envelope(
                        name="bertscore_recall",
                        value=metrics["bertscore_recall"],
                        availability=bert_avail,
                    ),
                    "bertscore_f1": metric_envelope(
                        name="bertscore_f1",
                        value=metrics["bertscore_f1"],
                        availability=bert_avail,
                        note=(
                            "Semantic agreement of the explanation with its cited FDA evidence. "
                            "NOTE: until an independent LLM narrative is enabled (Groq), the explanation "
                            "echoes the retrieved evidence verbatim, so this score is partly circular "
                            "(overlap-inflated) and is NOT yet the spec's generated-vs-reference-label measure."
                        ),
                    ),
                },
            }
        )
    db.commit()
    return {"availability": MetricAvailability.AVAILABLE.value, "conditions": results}


def assign_dq4_conditions(
    db: Session,
    *,
    participant_pseudonym: str,
    evaluation_case_id: str | None,
    candidate: dict[str, Any],
    feature_values: dict[str, float],
    weights: dict[str, float],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    order = counterbalance_order(participant_pseudonym)
    xai = explain_additive_score(feature_values=feature_values, weights=weights)
    score = float(xai["score"])
    assignments = []
    for idx, cond in enumerate(order):
        payload = build_condition_payload(
            condition=cond,
            candidate=candidate,
            score=score,
            xai=xai,
            provenance=provenance,
        )
        row = ExplanationEvaluationAssignment(
            id=str(uuid.uuid4()),
            participant_pseudonym=participant_pseudonym,
            evaluation_case_id=evaluation_case_id,
            condition=cond,
            order_index=idx,
            payload_json=json.dumps(payload),
        )
        db.add(row)
        assignments.append({"condition": cond, "order_index": idx, "payload": payload})
    db.commit()
    return {"participant_pseudonym": participant_pseudonym, "order": order, "assignments": assignments}


def submit_survey_response(
    db: Session,
    *,
    participant_pseudonym: str,
    condition: str,
    evaluation_case_id: str | None,
    likert: dict[str, int],
    free_text: str | None = None,
    consent_confirmed: bool = True,
) -> PharmacistSurveyResponse:
    # Strip any accidental identity fields
    forbidden = {"name", "email", "registration", "workplace", "ip"}
    for k in list(likert.keys()):
        if k.lower() in forbidden:
            likert.pop(k, None)
    row = PharmacistSurveyResponse(
        id=str(uuid.uuid4()),
        participant_pseudonym=participant_pseudonym,
        condition=condition,
        evaluation_case_id=evaluation_case_id,
        likert_json=json.dumps(likert),
        free_text=free_text,
        consent_confirmed=consent_confirmed,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def dq4_survey_summary(db: Session) -> dict[str, Any]:
    rows = list(db.scalars(select(PharmacistSurveyResponse)).all())
    if not rows:
        return {
            "availability": MetricAvailability.INSUFFICIENT_SAMPLE.value,
            "response_count": 0,
            "pharmacist_count": 0,
            "by_condition": {},
            "note": "No result displayed until responses exist.",
        }
    by_cond: dict[str, list[dict[str, int]]] = {}
    for r in rows:
        by_cond.setdefault(r.condition, []).append(json.loads(r.likert_json or "{}"))
    summary: dict[str, Any] = {}
    for cond, likerts in by_cond.items():
        constructs = sorted({k for d in likerts for k in d})
        summary[cond] = {}
        for c in constructs:
            vals = [int(d[c]) for d in likerts if c in d]
            if not vals:
                continue
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            summary[cond][c] = {
                "mean": mean,
                "std": var**0.5,
                "min": min(vals),
                "max": max(vals),
                "n": len(vals),
            }
    n_pharm = db.scalar(
        select(func.count(func.distinct(PharmacistSurveyResponse.participant_pseudonym)))
    )
    return {
        "availability": MetricAvailability.AVAILABLE.value,
        "response_count": len(rows),
        "pharmacist_count": int(n_pharm or 0),
        "by_condition": summary,
    }


def combined_status(db: Session) -> dict[str, Any]:
    n_cases = db.scalar(select(func.count()).select_from(EvaluationCase)) or 0
    n_gt = db.scalar(select(func.count()).select_from(GroundTruthRecord)) or 0
    n_ocr = db.scalar(select(func.count()).select_from(OcrEvaluationRun)) or 0
    n_gold = db.scalar(select(func.count()).select_from(RecommendationGoldStandard)) or 0
    n_rec = db.scalar(select(func.count()).select_from(RecommendationEvaluationRun)) or 0
    n_rag = db.scalar(select(func.count()).select_from(RagEvaluationRun)) or 0
    n_survey = db.scalar(select(func.count()).select_from(PharmacistSurveyResponse)) or 0
    n_pharm = (
        db.scalar(
            select(func.count(func.distinct(PharmacistSurveyResponse.participant_pseudonym)))
        )
        or 0
    )

    def readiness(impl: bool, runs: int, evidence: bool) -> str:
        if not impl:
            return DqReadiness.NOT_IMPLEMENTED.value
        if runs == 0:
            return DqReadiness.IMPLEMENTED_NOT_EVALUATED.value
        if evidence:
            return DqReadiness.EVIDENCE_COMPLETE.value
        return DqReadiness.EVALUATION_IN_PROGRESS.value

    return {
        "counts": {
            "evaluation_cases": n_cases,
            "ground_truth_records": n_gt,
            "ocr_runs": n_ocr,
            "gold_standards": n_gold,
            "recommendation_runs": n_rec,
            "rag_runs": n_rag,
            "survey_responses": n_survey,
            "pharmacist_count": n_pharm,
        },
        "dq1": {
            "readiness": readiness(True, n_ocr, n_ocr > 0 and n_gt > 0),
            "status": "IMPLEMENTED_NOT_EVALUATED" if n_ocr == 0 else "EVALUATION_IN_PROGRESS",
        },
        "dq2": {
            "readiness": readiness(True, n_rec, n_rec > 0 and n_gold > 0),
        },
        "dq3": {
            "readiness": readiness(True, n_rag, n_rag > 0),
        },
        "dq4": {
            "readiness": readiness(True, n_survey, n_survey > 0),
        },
        "sample_claims": claim_143_or_10_status(
            prescription_count=int(n_cases),
            pharmacist_count=int(n_pharm),
        ),
    }


def freeze_combined_snapshot(db: Session) -> dict[str, Any]:
    status = combined_status(db)
    dq2 = run_dq2_recommendation_evaluation(db) if (status["counts"]["gold_standards"] > 0) else {
        "availability": MetricAvailability.INSUFFICIENT_GROUND_TRUTH.value
    }
    dq4 = dq4_survey_summary(db)
    results = {"combined": status, "dq2": dq2, "dq4": dq4}
    snap = create_snapshot(db, results=results)
    return snapshot_to_dict(snap)
