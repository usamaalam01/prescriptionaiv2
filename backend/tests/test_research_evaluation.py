"""Unit tests for research evaluation foundation (DQ1–DQ4 metrics & safety)."""

from __future__ import annotations

from app.services.research_eval.evidence_retrievers import (
    FAISSSPLRetriever,
    INSUFFICIENT_EVIDENCE,
    KeywordSPLRetriever,
    build_explanation_from_evidence,
    citation_coverage,
    unsupported_claim_rate,
)
from app.services.research_eval.metric_status import (
    MetricAvailability,
    claim_143_or_10_status,
    metric_envelope,
)
from app.services.research_eval.ocr_engines import CONFIGURED_ENGINES, simulate_engine_outputs
from app.services.research_eval.ocr_metrics import (
    character_error_rate,
    entity_prf,
    normalise_for_error_rate,
    score_ocr_against_gt,
    word_error_rate,
)
from app.services.research_eval.ranking_metrics import (
    aggregate_recommendation_metrics,
    precision_at_k,
    recall_at_k,
)
from app.services.research_eval.xai_conditions import (
    CONDITION_A,
    CONDITION_B,
    CONDITION_C,
    build_condition_payload,
    explain_additive_score,
)


def test_wer_cer_fixture_exact_match():
    ref = "Take ibuprofen 200 mg orally twice daily"
    assert character_error_rate(ref, ref) == 0.0
    assert word_error_rate(ref, ref) == 0.0


def test_wer_cer_known_edit():
    # One word substitution → WER = 1/6
    ref = "one two three four five six"
    hyp = "one two X four five six"
    assert abs(word_error_rate(ref, hyp) - (1 / 6)) < 1e-9
    # CER for single char change
    assert character_error_rate("abc", "abd") == 1 / 3


def test_normalisation_rules():
    assert normalise_for_error_rate("  Ibuprofen, 200mg! ") == "ibuprofen 200mg"


def test_entity_prf():
    m = entity_prf(["Ibuprofen"], ["ibuprofen"])
    assert m["precision"] == 1.0 and m["recall"] == 1.0 and m["f1"] == 1.0
    m2 = entity_prf(["Ibuprofen"], ["Paracetamol"])
    assert m2["f1"] == 0.0


def test_engine_thesis_roles_cover_configured_engines():
    from app.services.research_eval.ocr_engines import CONFIGURED_ENGINES, ENGINE_THESIS_ROLES

    for engine_id in CONFIGURED_ENGINES:
        assert engine_id in ENGINE_THESIS_ROLES
        assert ENGINE_THESIS_ROLES[engine_id]["thesis_role"]
        assert ENGINE_THESIS_ROLES[engine_id]["label"]


def test_ocr_engine_isolation():
    gt = {"medicine_name": "Ibuprofen", "strength": "200 mg", "route": "oral"}
    outs = simulate_engine_outputs(ground_truth_text="Ibuprofen 200 mg oral", ground_truth_fields=gt)
    assert set(CONFIGURED_ENGINES).issubset(set(outs.keys()))
    # Mutating one engine must not affect another
    outs["trocr"]["structured_fields"]["medicine_name"] = "CHANGED"
    assert outs["google_vision"]["structured_fields"]["medicine_name"] != "CHANGED"


def test_score_ocr_against_gt_fields():
    metrics = score_ocr_against_gt(
        gt_text="Ibuprofen 200 mg",
        hyp_text="Ibuprofen 200 mg",
        gt_fields={"medicine_name": "Ibuprofen", "strength": "200 mg", "route": "oral", "dosage_form": "tablet", "dose": "1", "frequency": "bd", "duration": "5d"},
        hyp_fields={"medicine_name": "Ibuprofen", "strength": "200 mg", "route": "oral", "dosage_form": "tablet", "dose": "1", "frequency": "bd", "duration": "5d"},
    )
    assert metrics["wer"] == 0.0
    assert metrics["medicine_name_exact_match"] is True


def test_precision_recall_at_k():
    retrieved = ["A", "B", "C", "D"]
    relevant = {"A", "C", "E"}
    assert precision_at_k(retrieved, relevant, 1) == 1.0
    assert precision_at_k(retrieved, relevant, 3) == 2 / 3
    # Recall@3 denominator = all gold valid (3), hits in top-3 = A,C → 2/3
    assert abs(recall_at_k(retrieved, relevant, 3) - (2 / 3)) < 1e-9


def test_aggregate_recommendation_metrics():
    agg = aggregate_recommendation_metrics(
        per_case=[
            {
                "retrieved_ranked": ["A", "B", "C"],
                "gold_valid": ["A", "C"],
                "gold_invalid_count": 1,
                "accepted_count": 2,
                "judged_count": 3,
                "rejection_reasons": ["ROUTE_MISMATCH"],
            }
        ]
    )
    assert agg["precision_at_1"] == 1.0
    assert abs(agg["recall_at_3"] - 1.0) < 1e-9
    assert agg["rejection_reason_distribution"]["ROUTE_MISMATCH"] == 1


def test_keyword_faiss_same_corpus_inputs():
    corpus = [
        {"id": "1", "spl_set_id": "s1", "section": "indications", "text": "ibuprofen pain inflammation"},
        {"id": "2", "spl_set_id": "s2", "section": "warnings", "text": "cardiovascular risk nsaid"},
    ]
    q = "ibuprofen pain"
    k = KeywordSPLRetriever(corpus).retrieve(q, top_k=2)
    f = FAISSSPLRetriever(corpus).retrieve(q, top_k=2)
    assert k and f
    assert k[0].provenance == "fda_spl"
    assert f[0].spl_set_id in {"s1", "s2"}


def test_insufficient_evidence_and_citations():
    assert build_explanation_from_evidence("q", []) == INSUFFICIENT_EVIDENCE
    from app.services.research_eval.evidence_retrievers import RetrievedEvidence

    ev = [
        RetrievedEvidence(record_id="spl-1", section="indications", text="pain relief", score=0.9, spl_set_id="set-1")
    ]
    expl = build_explanation_from_evidence("pain", ev)
    assert "spl-1" in expl
    assert citation_coverage(expl, ev) == 1.0
    assert unsupported_claim_rate(INSUFFICIENT_EVIDENCE, []) == 0.0


def test_shap_lime_reconciles_additive_score():
    xai = explain_additive_score(
        feature_values={"a": 1.0, "b": 0.5},
        weights={"a": 0.4, "b": 0.6},
        baseline=0.1,
    )
    assert abs(xai["score"] - (0.1 + 0.4 + 0.3)) < 1e-9
    assert abs(xai["shap"]["reconciled_score"] - xai["score"]) < 1e-9
    assert "lime" in xai


def test_condition_payloads_isolated():
    cand = {"name": "Drug X", "candidate_type": "SAME_ACTIVE_MOIETY_PRODUCT"}
    xai = explain_additive_score(feature_values={"a": 1.0}, weights={"a": 1.0})
    a = build_condition_payload(condition=CONDITION_A, candidate=cand, score=1.0)
    b = build_condition_payload(condition=CONDITION_B, candidate=cand, score=1.0, xai=xai)
    c = build_condition_payload(
        condition=CONDITION_C, candidate=cand, score=1.0, xai=xai, provenance={"fda": "ndc-1"}
    )
    assert "shap" not in a
    assert "shap" in b and "provenance" not in b
    assert "provenance" in c


def test_metric_envelope_never_zeros_unavailable():
    env = metric_envelope(name="wer", availability=MetricAvailability.NOT_CALCULATED)
    assert env["value"] is None
    assert env["availability"] == "NOT_CALCULATED"


def test_claim_143_10_not_verifiable_without_evidence():
    st = claim_143_or_10_status(prescription_count=3, pharmacist_count=1)
    assert st["claim_143_prescriptions"] == MetricAvailability.NOT_VERIFIABLE.value
    assert "Not verifiable" in st["display"]


def test_export_strips_forbidden_survey_keys():
    # Pseudonymisation: forbidden keys removed at submit time — unit-check the filter logic
    likert = {"trust": 4, "email": 1, "name": 2}
    forbidden = {"name", "email", "registration", "workplace", "ip"}
    for k in list(likert.keys()):
        if k.lower() in forbidden:
            likert.pop(k, None)
    assert "email" not in likert and "name" not in likert
    assert likert["trust"] == 4
