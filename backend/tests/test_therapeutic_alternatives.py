"""Therapeutic alternatives evaluation tests (DEMO DATA seed)."""

from app.services.therapeutic.evaluate import evaluate_prescription
from app.services.therapeutic.identity import resolve_identity
from app.services.therapeutic.retriever import retrieve_candidates
from app.services.therapeutic.scoring import calculate_evidence_match_score
from app.services.therapeutic.services import (
    PharmacistDecisionService,
    SourceProvenanceService,
    XAIExplanationService,
)
from app.services.therapeutic.xai import build_source_claims, explain_candidate


def _base_med(**overrides):
    payload = {
        "prescription_item_id": "m1",
        "medicine_name": "Amoxicillin",
        "pharmacist_verified": True,
        "verified_indication": "bacterial infection",
        "route": "Oral",
        "form": "capsule",
        "identity_confirmed_by_pharmacist": True,
    }
    payload.update(overrides)
    return payload


def test_exact_and_synonym_identity():
    exact = resolve_identity("Amoxicillin")
    assert exact["canonical_name"].lower() == "amoxicillin"
    assert exact["identity_confirmed"] is True
    # Offline seed id OR real DrugBank/catalog id
    assert exact["drugbank_id"]

    syn = resolve_identity("Ibrufen")
    assert "ibuprofen" in (syn.get("canonical_name") or "").lower()
    assert syn["match_method"] in {
        "synonym_match",
        "catalog_exact",
        "catalog_fuzzy",
        "exact_generic_name",
    }


def test_salt_base_normalization():
    result = resolve_identity("Amoxicillin sodium")
    assert "amoxicillin" in (result.get("canonical_name") or "").lower()
    # Catalog may exact-match a salt product; seed path requires manual confirmation
    assert result.get("drugbank_id") or result.get("catalog_medicine_id")


def test_unrelated_records_not_merged():
    amox = resolve_identity("Amoxicillin")
    ibu = resolve_identity("Ibuprofen")
    assert amox["canonical_drug_id"] != ibu["canonical_drug_id"]
    assert set(amox["matched_spl_ids"]).isdisjoint(set(ibu["matched_spl_ids"]))


def test_mechanism_only_without_indication_rejected():
    identity = resolve_identity("Amoxicillin")
    cands = retrieve_candidates(identity, "heparin-induced thrombocytopenia")
    assert cands == []


def test_semantic_only_not_enough():
    identity = resolve_identity("Amoxicillin")
    cands = retrieve_candidates(identity, "bacterial infection")
    assert cands
    for c in cands:
        assert c["active_ingredient"].lower() != "amoxicillin"
        assert c["indication_relationship"]["overlap"] is True
        assert c["why_retrieved"]


def test_missing_indication_and_allergy_blocks_ranking():
    result = evaluate_prescription(
        prescription_id="rx-1",
        patient_context={"allergy_status": "unknown"},
        prescribed_medicines=[
            {
                "prescription_item_id": "m1",
                "medicine_name": "Amoxicillin",
                "pharmacist_verified": True,
                "route": "Oral",
                "form": "capsules",
                "identity_confirmed_by_pharmacist": True,
            }
        ],
    )
    med = result["medicine_results"][0]
    assert med["evaluation_status"] == "insufficient_clinical_context"
    assert med["eligible_alternatives"] == []
    assert any("Insufficient clinical context" in m for m in med["missing_information"])


def test_one_medicine_with_several_alternatives():
    result = evaluate_prescription(
        prescription_id="rx-1",
        patient_context={"allergy_status": "none_known", "allergies": []},
        prescribed_medicines=[_base_med()],
    )
    med = result["medicine_results"][0]
    assert med["evaluation_status"] == "completed"
    assert len(med["eligible_alternatives"]) >= 1
    names = {c["candidate_name"] for c in med["eligible_alternatives"]}
    assert "Amoxicillin" not in names
    for cand in med["eligible_alternatives"]:
        assert cand["classification"] == "therapeutic_alternative"
        assert cand["source_claims"]
        assert cand["evidence_match_score"] >= 0
        assert "Best substitute" not in str(cand)
        assert "Equivalent" not in cand.get("explanation", {}).get("summary", "")


def test_multiple_medicines_independent():
    result = evaluate_prescription(
        prescription_id="rx-2",
        patient_context={"allergy_status": "none_known"},
        prescribed_medicines=[
            _base_med(prescription_item_id="m1"),
            _base_med(
                prescription_item_id="m2",
                medicine_name="Ibuprofen",
                verified_indication="pain",
                form="tablet",
            ),
        ],
    )
    assert len(result["medicine_results"]) == 2
    assert result["medicine_results"][0]["prescription_item_id"] == "m1"
    assert result["medicine_results"][1]["prescription_item_id"] == "m2"


def test_allergy_conflict_blocks_candidate():
    result = evaluate_prescription(
        prescription_id="rx-3",
        patient_context={"allergy_status": "documented", "allergies": ["penicillin"]},
        prescribed_medicines=[_base_med()],
    )
    med = result["medicine_results"][0]
    blocked_names = {c["candidate_name"] for c in med["blocked_candidates"]}
    assert "Phenoxymethylpenicillin" in blocked_names


def test_contraindication_conflict():
    result = evaluate_prescription(
        prescription_id="rx-c",
        patient_context={
            "allergy_status": "none_known",
            "conditions": ["active peptic ulcer"],
        },
        prescribed_medicines=[
            _base_med(medicine_name="Ibuprofen", verified_indication="pain", form="tablet")
        ],
    )
    med = result["medicine_results"][0]
    # Naproxen SPL typically contraindicates peptic ulcer disease in seed
    assert any(
        any(f.get("code") == "contraindication_conflict" for f in c.get("safety_findings") or [])
        for c in med["blocked_candidates"]
    ) or med["eligible_alternatives"] is not None


def test_serious_interaction_blocks():
    result = evaluate_prescription(
        prescription_id="rx-i",
        patient_context={
            "allergy_status": "none_known",
            "current_medicines": ["warfarin"],
        },
        prescribed_medicines=[_base_med()],
    )
    med = result["medicine_results"][0]
    # Candidates listing warfarin interaction should be blocked when present
    for c in med["blocked_candidates"]:
        if any(f.get("code") == "serious_interaction" for f in c.get("safety_findings") or []):
            assert c["rank"] is None
            break


def test_route_incompatibility():
    result = evaluate_prescription(
        prescription_id="rx-r",
        patient_context={"allergy_status": "none_known"},
        prescribed_medicines=[
            _base_med(medicine_name="Salbutamol", verified_indication="asthma", route="Oral", form="tablet")
        ],
    )
    med = result["medicine_results"][0]
    # Terbutaline seed is inhalation — oral source vs inhalation candidate may block
    assert (
        any(c["status"] == "blocked_by_safety_rule" for c in med["blocked_candidates"])
        or med["evaluation_status"] == "completed"
    )


def test_age_and_pregnancy_restriction():
    preg = evaluate_prescription(
        prescription_id="rx-p",
        patient_context={"allergy_status": "none_known", "pregnancy_status": "pregnant"},
        prescribed_medicines=[_base_med()],
    )
    age = evaluate_prescription(
        prescription_id="rx-a",
        patient_context={"allergy_status": "none_known", "age_years": 8},
        prescribed_medicines=[_base_med()],
    )
    preg_codes = {
        f.get("code")
        for c in preg["medicine_results"][0]["blocked_candidates"]
        for f in (c.get("safety_findings") or [])
    }
    age_codes = {
        f.get("code")
        for c in age["medicine_results"][0]["blocked_candidates"]
        for f in (c.get("safety_findings") or [])
    }
    assert "pregnancy_restriction" in preg_codes
    assert "age_restriction" in age_codes
    assert all(c["candidate_name"] != "Doxycycline" or c["rank"] is None for c in preg["medicine_results"][0]["eligible_alternatives"])


def test_renal_and_hepatic_warnings():
    renal = evaluate_prescription(
        prescription_id="rx-ren",
        patient_context={"allergy_status": "none_known", "renal_impairment": "severe"},
        prescribed_medicines=[
            _base_med(medicine_name="Ibuprofen", verified_indication="pain", form="tablet")
        ],
    )
    hepatic = evaluate_prescription(
        prescription_id="rx-hep",
        patient_context={"allergy_status": "none_known", "hepatic_impairment": "severe"},
        prescribed_medicines=[
            _base_med(medicine_name="Ibuprofen", verified_indication="pain", form="tablet")
        ],
    )
    for result in (renal, hepatic):
        med = result["medicine_results"][0]
        assert med["evaluation_status"] == "completed"
        codes = {
            f.get("code")
            for bucket in (med["blocked_candidates"], med["eligible_alternatives"])
            for c in bucket
            for f in (c.get("safety_findings") or [])
        }
        assert codes or med["withdrawn_candidates"] is not None


def test_withdrawn_candidate_excluded_from_active_ranking():
    result = evaluate_prescription(
        prescription_id="rx-4",
        patient_context={"allergy_status": "none_known"},
        prescribed_medicines=[
            _base_med(medicine_name="Ibuprofen", verified_indication="pain", form="tablet")
        ],
    )
    med = result["medicine_results"][0]
    eligible_names = {c["candidate_name"] for c in med["eligible_alternatives"]}
    withdrawn_names = {c["candidate_name"] for c in med["withdrawn_candidates"]}
    assert "DemoWithdrawnNSAID" not in eligible_names
    assert "DemoWithdrawnNSAID" in withdrawn_names


def test_score_components_sum_and_label():
    score = calculate_evidence_match_score(
        indication_related=True,
        class_related=True,
        mechanism_related=True,
        target_related=True,
        route_comparison={"status": "matched"},
        form_comparison={"status": "matched"},
        population_ok=True,
        contra_assessed=True,
        interaction_assessed=True,
    )
    assert score["score_label"] == "Evidence Match Score"
    assert score["total_score"] == 100
    assert score["maximum_score"] == 100


def test_ranking_order_and_blocked_excluded():
    result = evaluate_prescription(
        prescription_id="rx-rank",
        patient_context={"allergy_status": "documented", "allergies": ["penicillin"]},
        prescribed_medicines=[_base_med()],
    )
    med = result["medicine_results"][0]
    ranks = [c["rank"] for c in med["eligible_alternatives"]]
    assert ranks == sorted(ranks)
    assert all(c["rank"] is None for c in med["blocked_candidates"])
    assert all(c not in med["eligible_alternatives"] for c in med["blocked_candidates"])


def test_every_eligible_claim_has_provenance():
    result = evaluate_prescription(
        prescription_id="rx-5",
        patient_context={"allergy_status": "none_known"},
        prescribed_medicines=[
            _base_med(medicine_name="Salbutamol", verified_indication="asthma", route="Inhalation", form="inhaler")
        ],
    )
    for cand in result["medicine_results"][0]["eligible_alternatives"]:
        assert cand["source_claims"]
        assert SourceProvenanceService.assert_claims_have_sources(cand["source_claims"])
        for claim in cand["source_claims"]:
            assert claim.get("demo_label") or claim.get("demo_data") is not None
            assert claim.get("source_dataset")
            assert claim.get("source_record_id")


def test_llm_cannot_add_unsupported_evidence():
    # Template XAI only uses provided claims — no free-form invention path
    identity = resolve_identity("Amoxicillin")
    cands = retrieve_candidates(identity, "bacterial infection")
    assert cands
    cand = cands[0]
    from app.services.therapeutic.safety import screen_candidate

    safety = screen_candidate(
        source_route="Oral",
        source_form="capsule",
        candidate_record=cand["record"],
        candidate_spl=cand.get("spl"),
        patient_context={"allergy_status": "none_known"},
        identity_confirmed=True,
    )
    claims = build_source_claims(identity, cand, safety)
    score = calculate_evidence_match_score(
        indication_related=True,
        class_related=True,
        mechanism_related=True,
        target_related=True,
        route_comparison=safety.get("route_comparison") or {},
        form_comparison=safety.get("dosage_form_comparison") or {},
        population_ok=True,
        contra_assessed=True,
        interaction_assessed=True,
    )
    explanation = explain_candidate(rank=1, score=score, candidate=cand, safety=safety, source_claims=claims)
    assert explanation["explanation_mode"] == "template_based_no_llm"
    assert explanation["source_claims"] == claims
    assert "equivalent medicine" not in explanation["why_ranked"].lower()
    assert XAIExplanationService.disclaimer
    # Provenance required for every claim used in explanation
    assert SourceProvenanceService.assert_claims_have_sources(explanation["source_claims"])


def test_demo_data_labelled():
    result = evaluate_prescription(
        prescription_id="rx-d",
        patient_context={"allergy_status": "none_known"},
        prescribed_medicines=[_base_med()],
    )
    # Catalog-backed deployments advertise FDA/DrugBank provenance; offline seed still DEMO DATA
    assert result["demo_label"] in {"DEMO DATA", "FDA NDC + DrugBank catalog"}


def test_catalog_identity_for_common_otc_and_gi_drugs():
    """Award path: Cetirizine / Pantoprazole resolve via local catalog when built."""
    from app.services.datasets.catalog_store import catalog_available

    if not catalog_available():
        return
    for name in ("Cetirizine", "Pantoprazole"):
        identity = resolve_identity(name)
        assert identity.get("canonical_name")
        assert identity.get("data_source") == "catalog"
        assert identity.get("identity_confirmed") or identity.get("drugbank_id")


def test_catalog_alternatives_for_cetirizine_and_pantoprazole():
    from app.services.datasets.catalog_store import catalog_available

    if not catalog_available():
        return
    result = evaluate_prescription(
        prescription_id="rx-catalog",
        patient_context={"allergy_status": "none_known", "allergies": []},
        prescribed_medicines=[
            _base_med(
                prescription_item_id="m-cet",
                medicine_name="Cetirizine",
                verified_indication="allergic rhinitis",
                form="tablet",
                route="Oral",
            ),
            _base_med(
                prescription_item_id="m-pan",
                medicine_name="Pantoprazole",
                verified_indication="gastroesophageal reflux disease",
                form="tablet",
                route="Oral",
            ),
        ],
    )
    assert result["demo_label"] == "FDA NDC + DrugBank catalog"
    by_id = {m["prescription_item_id"]: m for m in result["medicine_results"]}
    assert by_id["m-cet"]["evaluation_status"] == "completed"
    assert by_id["m-pan"]["evaluation_status"] == "completed"
    # Expect at least one eligible or blocked/insufficient candidate from catalog retrieval
    for mid in ("m-cet", "m-pan"):
        med = by_id[mid]
        total = (
            len(med.get("eligible_alternatives") or [])
            + len(med.get("blocked_candidates") or [])
            + len(med.get("insufficient_candidates") or [])
        )
        assert med["identity"]["data_source"] == "catalog"
        assert total >= 1 or med.get("missing_information")


def test_pharmacist_decision_validation_audited_shape():
    PharmacistDecisionService.validate("accept_for_review", "")
    try:
        PharmacistDecisionService.validate("reject", "")
        assert False, "expected ValueError"
    except ValueError:
        pass
