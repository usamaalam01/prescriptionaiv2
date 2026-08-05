"""Sprint 1 — clinical safety, candidate types, salt/base, mandatory filters."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.therapeutic.candidate_types import (
    FORBIDDEN_EQUIVALENCE_PHRASES,
    INSUFFICIENT_EVIDENCE_MESSAGE,
    MCS_LIMITATION,
    CandidateType,
)
from app.services.therapeutic.canonical_envelope import build_canonical_envelope
from app.services.therapeutic.evaluate import evaluate_prescription
from app.services.therapeutic.mandatory_filters import apply_mandatory_filters
from app.services.therapeutic.rag_evidence import retrieve_label_excerpts
from app.services.therapeutic.salt_normalisation import (
    normalize_medicine_suggestion,
    resolve_moiety,
    same_active_moiety,
)


def test_candidate_type_enum_values():
    assert CandidateType.SAME_ACTIVE_MOIETY_PRODUCT.value == "SAME_ACTIVE_MOIETY_PRODUCT"
    assert CandidateType.DIFFERENT_ACTIVE_INGREDIENT.value == "DIFFERENT_ACTIVE_INGREDIENT"


def test_cetirizine_dihydrochloride_same_moiety():
    ok, reason = same_active_moiety("Cetirizine", "Cetirizine dihydrochloride")
    assert ok is True
    assert reason == "OK"
    a = resolve_moiety("cetirizine hydrochloride")
    b = resolve_moiety("cetirizine dihydrochloride")
    assert a["base_ingredient"] == "cetirizine"
    assert b["base_ingredient"] == "cetirizine"


def test_amlodipine_besylate_same_moiety():
    ok, _ = same_active_moiety("Amlodipine", "Amlodipine besylate")
    assert ok is True


def test_diclofenac_sodium_same_moiety():
    ok, _ = same_active_moiety("Diclofenac", "Diclofenac sodium")
    assert ok is True


def test_different_ingredient_classification():
    ok, reason = same_active_moiety("Ibuprofen", "Naproxen")
    assert ok is False
    assert reason == "ACTIVE_INGREDIENT_MISMATCH"


def test_normalisation_suggestion_does_not_silent_replace():
    sug = normalize_medicine_suggestion(input_value="cetirizine dihydrochloride")
    assert sug["input_value"] == "cetirizine dihydrochloride"
    assert sug["base_ingredient"] == "cetirizine"
    assert "pharmacist confirmation" in sug["ui_label"].lower()


def test_route_mismatch_rejection():
    src = build_canonical_envelope(
        medicine_name="Cetirizine",
        strength="10 mg",
        dosage_form="TABLET",
        route="ORAL",
        product_ndc="12345-678",
        drugbank_id="DB00341",
        source_provenance=["FDA_NDC", "DrugBank"],
    )
    cand = build_canonical_envelope(
        medicine_name="Cetirizine hydrochloride",
        strength="10 mg",
        dosage_form="TABLET",
        route="INTRAVENOUS",
        product_ndc="12345-999",
        drugbank_id="DB00341",
        source_provenance=["FDA_NDC"],
    )
    result = apply_mandatory_filters(
        source_envelope=src,
        candidate_envelope=cand,
        source_name="Cetirizine",
        candidate_name="Cetirizine hydrochloride",
    )
    assert result["eligible"] is False
    codes = [f["code"] for f in result["failed_filters"]]
    assert "ROUTE_MISMATCH" in codes


def test_release_type_mismatch_rejection():
    src = build_canonical_envelope(
        medicine_name="Metformin",
        strength="500 mg",
        dosage_form="TABLET IMMEDIATE RELEASE",
        route="ORAL",
        product_ndc="1-1",
        drugbank_id="DB00331",
        source_provenance=["DrugBank"],
    )
    cand = build_canonical_envelope(
        medicine_name="Metformin hydrochloride",
        strength="500 mg",
        dosage_form="TABLET EXTENDED RELEASE",
        route="ORAL",
        product_ndc="1-2",
        drugbank_id="DB00331",
        source_provenance=["DrugBank"],
    )
    assert src["release_type"] == "immediate_release"
    assert cand["release_type"] == "modified_release"
    result = apply_mandatory_filters(
        source_envelope=src,
        candidate_envelope=cand,
        source_name="Metformin",
        candidate_name="Metformin hydrochloride",
    )
    assert result["eligible"] is False
    assert any(f["code"] == "RELEASE_TYPE_MISMATCH" for f in result["failed_filters"])


def test_comparable_strength_passes():
    src = build_canonical_envelope(
        medicine_name="Ibuprofen",
        strength="200 mg",
        dosage_form="TABLET",
        route="ORAL",
        product_ndc="1-1",
        drugbank_id="DB01050",
        source_provenance=["FDA_NDC"],
    )
    cand = build_canonical_envelope(
        medicine_name="Ibuprofen",
        strength="200 mg",
        dosage_form="TABLET",
        route="ORAL",
        product_ndc="1-2",
        drugbank_id="DB01050",
        source_provenance=["FDA_NDC"],
    )
    # Names equal — product path usually skips identical name; filters should still be eligible
    result = apply_mandatory_filters(
        source_envelope=src,
        candidate_envelope=cand,
        source_name="Ibuprofen",
        candidate_name="Ibuprofen",
    )
    assert result["eligible"] is True


def test_non_comparable_strength():
    src = build_canonical_envelope(
        medicine_name="Ibuprofen",
        strength="200 mg",
        dosage_form="TABLET",
        route="ORAL",
        product_ndc="1-1",
        drugbank_id="DB01050",
        source_provenance=["FDA_NDC"],
    )
    cand = build_canonical_envelope(
        medicine_name="Ibuprofen",
        strength="5 ml",
        dosage_form="TABLET",
        route="ORAL",
        product_ndc="1-2",
        drugbank_id="DB01050",
        source_provenance=["FDA_NDC"],
    )
    result = apply_mandatory_filters(
        source_envelope=src,
        candidate_envelope=cand,
        source_name="Ibuprofen",
        candidate_name="Ibuprofen",
    )
    assert result["eligible"] is False
    assert any(f["code"] == "STRENGTH_NOT_COMPARABLE" for f in result["failed_filters"])


def test_missing_provenance():
    src = build_canonical_envelope(
        medicine_name="Ibuprofen",
        strength="200 mg",
        dosage_form="TABLET",
        route="ORAL",
        product_ndc="1-1",
        drugbank_id="DB01050",
        source_provenance=["FDA_NDC"],
    )
    cand = build_canonical_envelope(
        medicine_name="Ibuprofen",
        strength="200 mg",
        dosage_form="TABLET",
        route="ORAL",
        source_provenance=[],
    )
    result = apply_mandatory_filters(
        source_envelope=src,
        candidate_envelope=cand,
        source_name="Ibuprofen",
        candidate_name="Ibuprofen",
    )
    assert result["eligible"] is False
    assert any(f["code"] == "PROVENANCE_MISSING" for f in result["failed_filters"])


def test_hitl_confirmation_before_candidate_retrieval():
    result = evaluate_prescription(
        prescription_id="rx-test",
        patient_context={"allergy_status": "none_known"},
        prescribed_medicines=[
            {
                "prescription_item_id": "m1",
                "medicine_name": "Ibuprofen",
                "pharmacist_verified": False,
                "verified_indication": "pain",
            }
        ],
    )
    mr = result["medicine_results"][0]
    assert mr["evaluation_status"] == "hitl_confirmation_required"
    assert mr["product_candidates"] == []
    assert mr["therapeutic_candidates"] == []


def test_insufficient_evidence_constant():
    assert INSUFFICIENT_EVIDENCE_MESSAGE == "Insufficient evidence — pharmacist review required."
    out = retrieve_label_excerpts(medicine_name="___no_such_drug_xyz___", indication=None)
    if out.get("status") in {"empty", "catalog_unavailable", "ok"}:
        if not out.get("excerpts"):
            assert (
                out.get("evidence_message") == INSUFFICIENT_EVIDENCE_MESSAGE
                or out.get("disclaimer") == INSUFFICIENT_EVIDENCE_MESSAGE
                or out.get("status") == "catalog_unavailable"
            )


def test_mcs_limitation_wording():
    assert "does not establish clinical interchangeability" in MCS_LIMITATION.lower()


def test_forbidden_equivalence_phrases_absent_from_active_modules():
    root = Path(__file__).resolve().parents[1] / "app"
    allow_files = {"candidate_types.py"}
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name in allow_files:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in FORBIDDEN_EQUIVALENCE_PHRASES:
            if phrase in text:
                # Allow educational "is not therapeutic equivalence" negations
                if "not therapeutic equivalence" in text or "not an" in text and "equivalence" in phrase:
                    if f"not {phrase}" in text or "not therapeutic equivalence" in text:
                        continue
                if "not" in text and phrase in text:
                    # Skip lines that negate the phrase
                    lines = [ln for ln in text.splitlines() if phrase in ln]
                    if lines and all("not " in ln or "never " in ln or "is not" in ln for ln in lines):
                        continue
                offenders.append(f"{path.name}:{phrase}")
    assert offenders == [], offenders


def test_frontend_warning_banner_string_present():
    panel = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "components"
        / "TherapeuticAlternativesPanel.tsx"
    )
    text = panel.read_text(encoding="utf-8")
    assert "Different active ingredient — pharmacist assessment required" in text
    assert "Product Candidates" in text
    assert "Therapeutic Candidates" in text
    for phrase in ("therapeutically equivalent", "automatic substitute", "safe substitute"):
        assert phrase not in text.lower()


def test_evaluate_separates_candidate_lists_when_possible():
    # Without catalog may still return structure
    result = evaluate_prescription(
        prescription_id="rx-test-2",
        patient_context={"allergy_status": "none_known"},
        prescribed_medicines=[
            {
                "prescription_item_id": "m2",
                "medicine_name": "Ibuprofen",
                "strength": "200 mg",
                "form": "TABLET",
                "route": "ORAL",
                "pharmacist_verified": True,
                "identity_confirmed_by_pharmacist": True,
                "verified_indication": "pain",
            }
        ],
        top_n=3,
    )
    mr = result["medicine_results"][0]
    assert "product_candidates" in mr
    assert "therapeutic_candidates" in mr
    assert "dq2_alignment" in mr
    # Serialisable
    json.dumps(result, default=str)
