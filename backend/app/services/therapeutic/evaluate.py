"""Therapeutic alternatives evaluation orchestrator (Sprint 1 dual candidate types)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.services.datasets.catalog_store import catalog_available
from app.services.therapeutic.candidate_types import (
    DIFFERENT_INGREDIENT_BANNER,
    INSUFFICIENT_EVIDENCE_MESSAGE,
    MCS_LIMITATION,
    CandidateType,
)
from app.services.therapeutic.canonical_envelope import build_canonical_envelope
from app.services.therapeutic.feature_xai import explain_score_features
from app.services.therapeutic.identity import resolve_identity
from app.services.therapeutic.mandatory_filters import apply_mandatory_filters
from app.services.therapeutic.mcs import compute_mcs_similarity, mcs_score_points
from app.services.therapeutic.product_candidates import retrieve_same_moiety_product_candidates
from app.services.therapeutic.rag_evidence import maybe_groq_summarise, retrieve_label_excerpts
from app.services.therapeutic.retriever import retrieve_candidates
from app.services.therapeutic.safety import screen_candidate
from app.services.therapeutic.scoring import WEIGHTS, calculate_evidence_match_score
from app.services.therapeutic.seed_data import DATASET_VERSION, DEMO_LABEL, RULES_ENGINE_VERSION
from app.services.therapeutic.xai import DISCLAIMER, build_source_claims, explain_candidate


def _te_block_for_candidate(cand: dict, cand_env: dict | None, *, same_ingredient: bool) -> dict:
    """U-TE — FDA Orange Book therapeutic-equivalence evidence for a candidate.

    Decision-support evidence only; does NOT re-rank or gate. Never raises. The
    returned block describes the CANDIDATE'S OWN Orange Book status (i.e. whether
    *its* generics are interchangeable with each other), NOT equivalence to the
    prescribed medicine — `applies_to` makes that explicit so a different-ingredient
    candidate's `substitutable=True` is never misread as "substitutable for the Rx".
    """
    try:
        from app.services.therapeutic.orange_book import te_status_for

        env = cand_env or {}
        block = te_status_for(
            ingredient=cand.get("active_ingredient") or cand.get("candidate_name"),
            dosage_form=env.get("dosage_form") or env.get("canonical_form"),
            route=env.get("route"),
            strength=env.get("normalised_strength") or env.get("strength"),
        )
        block["applies_to"] = (
            "candidate_vs_prescribed_same_ingredient"
            if same_ingredient
            else "candidate_own_generics_only"
        )
        if not same_ingredient:
            block["cross_ingredient_note"] = (
                "This candidate has a DIFFERENT active ingredient from the prescribed medicine, so it is "
                "NOT therapeutically equivalent to the prescription under the Orange Book. The TE fields "
                "below describe substitutability among the candidate's OWN generics only."
            )
        return block
    except Exception:  # noqa: BLE001 - TE evidence must never break a recommendation
        return {"available": False, "source": "FDA Orange Book", "note": "TE lookup error."}


def _real_xai_for_score(score: dict) -> dict:
    """U10 — build the SHAP/LIME XAI payload from an Evidence Match Score result.

    Reconstructs the additive feature vector from the score's components
    (matched → 1.0, else 0.0) and runs the real SHAP/LIME explainers (flag-gated,
    analytical fallback). Never raises — returns a minimal block on any failure.
    """
    try:
        from app.services.research_eval.xai_real import explain_candidate_xai

        feature_values = {
            c["component"]: (1.0 if c.get("status") == "matched" else 0.0)
            for c in (score.get("components") or [])
        }
        # Cover any weight not represented in components.
        for k in WEIGHTS:
            feature_values.setdefault(k, 0.0)
        weights = dict(WEIGHTS)
        # Include the MCS structural bonus as an explicit feature so the SHAP/LIME
        # bars sum to the DISPLAYED total_score, not just the base. The displayed
        # score is min(100, base + bonus), so CLAMP the bonus weight to the headroom
        # (100 - base) — otherwise, when base + bonus > 100, the bars would sum past
        # the capped headline and re-introduce an explanation↔score mismatch.
        base = float(sum(w for k, w in WEIGHTS.items() if feature_values.get(k, 0.0) > 0))
        mcs_bonus = float(score.get("mcs_bonus_points") or 0)
        effective_bonus = max(0.0, min(mcs_bonus, 100.0 - base))
        if effective_bonus:
            feature_values["mcs_structural_bonus"] = 1.0
            weights["mcs_structural_bonus"] = effective_bonus
        return explain_candidate_xai(feature_values=feature_values, weights=weights, baseline=0.0)
    except Exception:  # noqa: BLE001 - XAI must never break a recommendation
        return {"score": score.get("total_score"), "real_shap": None, "real_lime": None,
                "reconciliation": {"status": "error"}, "flags": {}}


INSUFFICIENT_CONTEXT = "Insufficient clinical context to rank therapeutic alternatives safely."
IDENTITY_FAILED = (
    "Medicine identity could not be confirmed across the connected FDA/DrugBank catalog "
    "or DEMO enrichment seed."
)
HITL_REQUIRED = (
    "Pharmacist confirmation is required before candidate search. "
    "Complete HITL verification first."
)


def _provenance_label(identity: dict | None = None, candidate: dict | None = None) -> str:
    if candidate and candidate.get("provenance_label"):
        return candidate["provenance_label"]
    if identity and identity.get("provenance_label"):
        return identity["provenance_label"]
    if catalog_available():
        try:
            from app.services.therapeutic.catalog_therapeutic import CATALOG_LABEL

            return CATALOG_LABEL
        except Exception:
            pass
    return DEMO_LABEL


def _dataset_version(identity: dict | None = None) -> str:
    if identity and identity.get("data_source") == "catalog":
        try:
            from app.services.therapeutic.catalog_therapeutic import catalog_dataset_version

            return catalog_dataset_version()
        except Exception:
            return DATASET_VERSION
    if catalog_available():
        try:
            from app.services.therapeutic.catalog_therapeutic import catalog_dataset_version

            return catalog_dataset_version()
        except Exception:
            pass
    return DATASET_VERSION


def _enrich_mcs_payload(mcs: dict) -> dict:
    return {
        **mcs,
        "mcs_similarity": mcs.get("atom_coverage"),
        "atom_coverage": mcs.get("atom_coverage"),
        "structure_source": "smiles_seed+rdkit" if mcs.get("status") == "ok" else None,
        "calculation_status": mcs.get("status"),
        "limitations": MCS_LIMITATION,
    }


def _rule_based_explanation(
    *,
    rank: int,
    score: dict,
    candidate_type: str,
    filter_result: dict | None,
    mcs: dict | None,
    feature_xai: dict,
) -> dict:
    return {
        "title": "Rule-based score explanation",
        "candidate_type": candidate_type,
        "mandatory_filter_results": filter_result,
        "component_contribution": score.get("components") or [],
        "component_weights_note": "Deterministic Evidence Match components (not ML explainability).",
        "final_score": score.get("total_score"),
        "mcs_supporting_evidence": mcs,
        "experimental_attribution": {
            **feature_xai,
            "primary": False,
            "label": "Experimental / surrogate attribution (not primary explanation)",
        },
        "why_ranked": (
            f"Rank {rank} using rule-based Evidence Match Score "
            f"{score.get('total_score')}/100 for pharmacist review only."
        ),
        "disclaimer": DISCLAIMER,
    }


def evaluate_prescription(
    *,
    prescription_id: str,
    patient_context: dict,
    prescribed_medicines: list[dict],
    top_n: int = 5,
) -> dict:
    evaluation_id = str(uuid.uuid4())
    medicine_results = []
    for item in prescribed_medicines:
        medicine_results.append(
            _evaluate_one(
                evaluation_id=evaluation_id,
                prescription_id=prescription_id,
                patient_context=patient_context,
                item=item,
                top_n=top_n,
            )
        )

    used_catalog = any(
        (m.get("identity") or {}).get("data_source") == "catalog" for m in medicine_results
    )
    label = DEMO_LABEL
    if used_catalog or catalog_available():
        try:
            from app.services.therapeutic.catalog_therapeutic import CATALOG_LABEL

            label = CATALOG_LABEL
        except Exception:
            label = DEMO_LABEL

    return {
        "evaluation_id": evaluation_id,
        "prescription_id": prescription_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": _dataset_version(
            (medicine_results[0].get("identity") if medicine_results else None)
        ),
        "rules_engine_version": RULES_ENGINE_VERSION,
        "demo_label": label,
        "provenance_label": label,
        "disclaimer": DISCLAIMER,
        "candidate_type_legend": {
            CandidateType.SAME_ACTIVE_MOIETY_PRODUCT.value: (
                "Same-active-moiety product candidate for pharmacist review"
            ),
            CandidateType.DIFFERENT_ACTIVE_INGREDIENT.value: (
                "Different-active-ingredient therapeutic candidate for pharmacist review"
            ),
        },
        "medicine_results": medicine_results,
    }


def _evaluate_one(
    *,
    evaluation_id: str,
    prescription_id: str,
    patient_context: dict,
    item: dict,
    top_n: int,
) -> dict:
    item_id = item.get("prescription_item_id") or str(uuid.uuid4())
    name = item.get("medicine_name") or ""
    verified = bool(item.get("pharmacist_verified"))
    indication = (
        item.get("verified_indication") or patient_context.get("verified_indication") or ""
    ).strip()
    allergy_status = patient_context.get("allergy_status")

    identity = resolve_identity(
        name,
        drugbank_id=item.get("drugbank_id"),
        unii=item.get("unii"),
    )

    source_envelope = build_canonical_envelope(
        medicine_name=identity.get("canonical_name") or name,
        strength=item.get("strength"),
        dosage_form=item.get("form"),
        route=item.get("route"),
        product_ndc=(identity.get("matched_product_ndcs") or [None])[0],
        drugbank_id=identity.get("drugbank_id"),
        catalog_medicine_id=identity.get("catalog_medicine_id"),
        source_provenance=identity.get("catalog_sources") or identity.get("sources"),
    )

    base = {
        "prescription_item_id": item_id,
        "source_medicine": {
            "medicine_name": name,
            "strength": item.get("strength"),
            "form": item.get("form"),
            "route": item.get("route"),
            "dose": item.get("dose"),
            "frequency": item.get("frequency"),
            "pharmacist_verified": verified,
            "ocr_value": item.get("ocr_medicine_name") or item.get("ai_medicine_name"),
            "pharmacist_confirmed_value": name if verified else None,
            "normalisation_suggestion": source_envelope.get("normalisation_suggestion"),
            "normalisation_ui_label": "Suggested normalisation — pharmacist confirmation required",
        },
        "canonical_envelope": source_envelope,
        "identity": identity,
        "evaluation_status": "",
        "product_candidates": [],
        "therapeutic_candidates": [],
        "eligible_alternatives": [],  # legacy alias = therapeutic_candidates
        "blocked_candidates": [],
        "withdrawn_candidates": [],
        "insufficient_candidates": [],
        "rejected_same_moiety_candidates": [],
        "missing_information": [],
        "product_matches": {
            "matched_spl_ids": identity.get("matched_spl_ids") or [],
            "matched_product_ndcs": identity.get("matched_product_ndcs") or [],
            "note": (
                "FDA NDC supports product/formulation information only and is not "
                "therapeutic equivalence evidence."
            ),
        },
        "provenance_label": _provenance_label(identity),
    }

    if not verified and not item.get("identity_confirmed_by_pharmacist"):
        base["evaluation_status"] = "hitl_confirmation_required"
        base["missing_information"].append(HITL_REQUIRED)
        return base

    if not identity.get("drugbank_id") and not identity.get("catalog_medicine_id"):
        base["evaluation_status"] = "identity_not_confirmed"
        base["missing_information"].append(IDENTITY_FAILED)
        return base

    identity_ok = bool(identity.get("identity_confirmed"))
    if verified and identity.get("data_source") == "catalog":
        identity_ok = True
        identity["identity_confirmed"] = True
        identity["manual_confirmation_required"] = False
    if item.get("identity_confirmed_by_pharmacist"):
        identity_ok = True
        identity["identity_confirmed"] = True
        identity["manual_confirmation_required"] = False

    if identity.get("manual_confirmation_required") and not identity_ok:
        base["evaluation_status"] = "identity_not_confirmed"
        base["missing_information"].append(
            "Controlled fuzzy identity match requires pharmacist confirmation before ranking alternatives."
        )
        return base

    missing_ctx = []
    if not verified and not item.get("identity_confirmed_by_pharmacist"):
        missing_ctx.append("verified_source_medicine")
    if not identity.get("active_ingredient"):
        missing_ctx.append("verified_active_ingredient")
    if not indication:
        missing_ctx.append("verified_indication")
    if allergy_status in (None, "", "unknown", "not assessed", "not_available"):
        missing_ctx.append("allergy_status")

    if missing_ctx:
        base["evaluation_status"] = "insufficient_clinical_context"
        base["missing_information"] = [INSUFFICIENT_CONTEXT, *missing_ctx]
        return base

    # --- Path A: SAME_ACTIVE_MOIETY_PRODUCT ---
    product_raw = retrieve_same_moiety_product_candidates(
        source_identity=identity,
        source_envelope=source_envelope,
        source_route=item.get("route"),
        source_form=item.get("form"),
        source_strength=item.get("strength"),
    )
    product_eligible = []
    rejected_same = []

    for cand in product_raw:
        cand_env = cand.get("canonical_envelope") or build_canonical_envelope(
            medicine_name=cand.get("candidate_name"),
            dosage_form=(cand.get("spl") or {}).get("dosage_form"),
            route=(cand.get("spl") or {}).get("route"),
            drugbank_id=cand.get("candidate_drug_id"),
            source_provenance=(cand.get("record") or {}).get("sources"),
        )
        filters = apply_mandatory_filters(
            source_envelope=source_envelope,
            candidate_envelope=cand_env,
            source_name=identity.get("canonical_name") or name,
            candidate_name=cand.get("candidate_name"),
        )
        if not filters["eligible"]:
            rejected_same.append(
                {
                    "candidate_drug_id": cand["candidate_drug_id"],
                    "candidate_name": cand["candidate_name"],
                    "candidate_type": CandidateType.SAME_ACTIVE_MOIETY_PRODUCT.value,
                    "display_label": "Same-active-moiety product candidate",
                    "status": "rejected_by_mandatory_filter",
                    "mandatory_filter_results": filters,
                    "failed_filters": filters["failed_filters"],
                    "canonical_envelope": cand_env,
                    "warnings": [f["message"] for f in filters["failed_filters"]],
                }
            )
            continue

        # MCS only AFTER mandatory filters
        mcs = _enrich_mcs_payload(
            compute_mcs_similarity(
                source_drugbank_id=identity.get("drugbank_id"),
                source_name=identity.get("canonical_name") or name,
                candidate_drugbank_id=cand.get("candidate_drug_id")
                if not str(cand.get("candidate_drug_id") or "").startswith("CATALOG:")
                else None,
                candidate_name=cand.get("candidate_name"),
            )
        )
        # MCS must never override filters (already passed); no score from MCS alone for eligibility
        mcs_pts = mcs_score_points(mcs)
        safety = screen_candidate(
            source_route=item.get("route"),
            source_form=item.get("form"),
            candidate_record=cand["record"],
            candidate_spl=cand.get("spl"),
            patient_context=patient_context,
            identity_confirmed=True,
        )
        if safety["status"] != "eligible_for_pharmacist_review":
            rejected_same.append(
                {
                    "candidate_drug_id": cand["candidate_drug_id"],
                    "candidate_name": cand["candidate_name"],
                    "candidate_type": CandidateType.SAME_ACTIVE_MOIETY_PRODUCT.value,
                    "status": safety["status"],
                    "mandatory_filter_results": filters,
                    "safety_findings": safety.get("safety_findings"),
                }
            )
            continue

        score = calculate_evidence_match_score(
            indication_related=False,
            class_related=True,  # same moiety treated as related class signal
            mechanism_related=False,
            target_related=False,
            route_comparison=safety.get("route_comparison") or {"status": "matched"},
            form_comparison=safety.get("dosage_form_comparison") or {"status": "matched"},
            population_ok=True,
            contra_assessed=bool(cand.get("spl")),
            interaction_assessed=True,
        )
        adjusted = min(100, int(score["total_score"]) + mcs_pts)
        score = {
            **score,
            "total_score": adjusted,
            "mcs_bonus_points": mcs_pts,
            "base_score_before_mcs": score["total_score"],
            "score_label": "Rule-based Evidence Match Score",
        }
        feature_xai = explain_score_features(evidence_match=score, mcs=mcs, mcs_points=mcs_pts)
        claims = build_source_claims(identity, cand, safety)
        rag = retrieve_label_excerpts(
            medicine_name=cand.get("candidate_name") or "",
            indication=indication,
            catalog_medicine_id=(cand.get("record") or {}).get("catalog_medicine_id"),
            top_k=3,
        )
        evidence_sufficiency = "sufficient" if rag.get("excerpts") else "insufficient"
        evidence_message = None if rag.get("excerpts") else INSUFFICIENT_EVIDENCE_MESSAGE
        if evidence_sufficiency == "insufficient":
            groq = {
                "enabled": False,
                "status": "refused_no_evidence",
                "summary": None,
                "note": INSUFFICIENT_EVIDENCE_MESSAGE,
            }
        else:
            groq = maybe_groq_summarise(rag.get("excerpts") or [], medicine_name=cand["candidate_name"])

        payload = {
            "candidate_drug_id": cand["candidate_drug_id"],
            "candidate_name": cand["candidate_name"],
            "active_ingredient": cand["active_ingredient"],
            "candidate_type": CandidateType.SAME_ACTIVE_MOIETY_PRODUCT.value,
            "display_label": "Same-active-moiety product candidate",
            "classification": "same_active_moiety_product",
            "status": safety["status"],
            "rank": None,
            "evidence_match_score": score["total_score"],
            "evidence_match": score,
            "evidence_coverage": score["evidence_coverage"],
            "mandatory_filter_results": filters,
            "passed_filters": filters["passed_filters"],
            "failed_filters": [],
            "canonical_envelope": cand_env,
            "therapeutic_equivalence": _te_block_for_candidate(cand, cand_env, same_ingredient=True),  # U-TE
            "ingredient_relationship": "same_active_moiety",
            "salt_base_relationship": {
                "source": source_envelope.get("salt_or_ester"),
                "candidate": cand_env.get("salt_or_ester"),
            },
            "strength_comparison": {
                "source": source_envelope.get("normalised_strength"),
                "candidate": cand_env.get("normalised_strength"),
            },
            "route_comparison": safety.get("route_comparison"),
            "dosage_form_comparison": safety.get("dosage_form_comparison"),
            "release_type_comparison": {
                "source": source_envelope.get("release_type"),
                "candidate": cand_env.get("release_type"),
            },
            "mcs": mcs,
            "rule_based_explanation": None,
            "feature_attribution": feature_xai,
            "why_retrieved": cand["why_retrieved"],
            "indication_relationship": cand["indication_relationship"],
            "class_relationship": cand["class_relationship"],
            "mechanism_relationship": cand["mechanism_relationship"],
            "target_relationship": cand["target_relationship"],
            "important_differences": [],
            "safety_findings": safety.get("safety_findings"),
            "missing_information": safety.get("missing_information") or [],
            "warnings": [MCS_LIMITATION],
            "source_claims": claims,
            "rag_evidence": rag,
            "evidence_sufficiency": evidence_sufficiency,
            "evidence_message": evidence_message,
            "rag_summary": groq,
            "demo_label": _provenance_label(identity, cand),
            "provenance_label": _provenance_label(identity, cand),
            "interchangeability_claim": False,
            "pharmacist_action_required": True,
        }
        product_eligible.append((payload, cand, safety, score, claims, filters, mcs, feature_xai))

    product_eligible.sort(key=lambda row: -row[3]["total_score"])
    product_ranked = []
    for idx, (payload, cand, safety, score, claims, filters, mcs, feature_xai) in enumerate(
        product_eligible[:top_n], start=1
    ):
        payload["rank"] = idx
        explanation = explain_candidate(
            rank=idx, score=score, candidate=cand, safety=safety, source_claims=claims
        )
        explanation["title"] = "Rule-based score explanation"
        explanation["primary_explanation_type"] = "rule_based"
        explanation["mcs_note"] = MCS_LIMITATION
        payload["important_differences"] = explanation["important_differences"]
        payload["explanation"] = explanation
        payload["real_xai"] = _real_xai_for_score(score)  # U10: SHAP/LIME dashboard data
        payload["rule_based_explanation"] = _rule_based_explanation(
            rank=idx,
            score=score,
            candidate_type=CandidateType.SAME_ACTIVE_MOIETY_PRODUCT.value,
            filter_result=filters,
            mcs=mcs,
            feature_xai=feature_xai,
        )
        product_ranked.append(payload)

    # --- Path B: DIFFERENT_ACTIVE_INGREDIENT (existing indication retrieve) ---
    raw_candidates = retrieve_candidates(identity, indication)
    therapeutic_eligible = []
    blocked = []
    withdrawn = []
    insufficient = []

    for cand in raw_candidates:
        safety = screen_candidate(
            source_route=item.get("route"),
            source_form=item.get("form"),
            candidate_record=cand["record"],
            candidate_spl=cand.get("spl"),
            patient_context=patient_context,
            identity_confirmed=True,
        )
        score = calculate_evidence_match_score(
            indication_related=True,
            class_related=bool(cand["class_relationship"].get("related")),
            mechanism_related=bool(cand["mechanism_relationship"].get("related")),
            target_related=bool(cand["target_relationship"].get("related")),
            route_comparison=safety.get("route_comparison") or {},
            form_comparison=safety.get("dosage_form_comparison") or {},
            population_ok=True
            if not any(
                f.get("code") in {"age_restriction", "pregnancy_restriction"}
                for f in safety["safety_findings"]
            )
            else False,
            contra_assessed=bool(cand.get("spl")),
            interaction_assessed=bool(cand["record"].get("drug_interactions") is not None),
        )
        # MCS must NOT convert different ingredient into equivalence — compute for display only, no eligibility
        mcs = _enrich_mcs_payload(
            compute_mcs_similarity(
                source_drugbank_id=identity.get("drugbank_id"),
                source_name=identity.get("canonical_name") or name,
                candidate_drugbank_id=cand.get("candidate_drug_id")
                if not str(cand.get("candidate_drug_id") or "").startswith("CATALOG:")
                else cand["record"].get("drugbank_id"),
                candidate_name=cand.get("candidate_name"),
            )
        )
        # Do not add MCS bonus for different-ingredient path (prevents TE implication)
        score = {**score, "mcs_bonus_points": 0, "score_label": "Rule-based Evidence Match Score"}
        feature_xai = explain_score_features(evidence_match=score, mcs=mcs, mcs_points=0)
        claims = build_source_claims(identity, cand, safety)
        prov = _provenance_label(identity, cand)
        payload = {
            "candidate_drug_id": cand["candidate_drug_id"],
            "candidate_name": cand["candidate_name"],
            "active_ingredient": cand["active_ingredient"],
            "candidate_type": CandidateType.DIFFERENT_ACTIVE_INGREDIENT.value,
            "display_label": "Different-active-ingredient therapeutic candidate",
            "warning_banner": DIFFERENT_INGREDIENT_BANNER,
            "classification": "different_active_ingredient_candidate",
            "status": safety["status"],
            "rank": None,
            "evidence_match_score": score["total_score"],
            "evidence_match": score,
            "evidence_coverage": score["evidence_coverage"],
            "mcs": mcs,
            "feature_attribution": feature_xai,
            "why_retrieved": cand["why_retrieved"],
            "indication_relationship": cand["indication_relationship"],
            "class_relationship": cand["class_relationship"],
            "mechanism_relationship": cand["mechanism_relationship"],
            "target_relationship": cand["target_relationship"],
            "route_comparison": safety.get("route_comparison"),
            "dosage_form_comparison": safety.get("dosage_form_comparison"),
            "important_differences": [],
            "safety_findings": safety.get("safety_findings"),
            "missing_information": safety.get("missing_information"),
            "warnings": [DIFFERENT_INGREDIENT_BANNER, MCS_LIMITATION],
            "source_claims": claims,
            "demo_label": prov,
            "provenance_label": prov,
            "interchangeability_claim": False,
            "pharmacist_action_required": True,
            # U-TE: the candidate's own FDA Orange Book status. For a *different*-ingredient
            # candidate this reflects its own ingredient's TE — it is never therapeutically
            # equivalent to the source under Orange Book (different pharmaceutical-equivalence group).
            "therapeutic_equivalence": _te_block_for_candidate(
                cand,
                {
                    "route": (safety.get("route_comparison") or {}).get("candidate"),
                    "dosage_form": (safety.get("dosage_form_comparison") or {}).get("candidate"),
                },
                same_ingredient=False,
            ),
        }

        if safety["status"] == "withdrawn_or_discontinued":
            payload["explanation"] = explain_candidate(
                rank=0, score=score, candidate=cand, safety=safety, source_claims=claims
            )
            withdrawn.append(payload)
        elif safety["status"] == "blocked_by_safety_rule":
            payload["explanation"] = explain_candidate(
                rank=0, score=score, candidate=cand, safety=safety, source_claims=claims
            )
            blocked.append(payload)
        elif safety["status"] == "insufficient_information":
            payload["explanation"] = explain_candidate(
                rank=0, score=score, candidate=cand, safety=safety, source_claims=claims
            )
            insufficient.append(payload)
        else:
            therapeutic_eligible.append((payload, cand, safety, score, claims, feature_xai, mcs))

    therapeutic_eligible.sort(
        key=lambda row: (
            -int(bool(row[1]["indication_relationship"].get("overlap"))),
            -row[3]["evidence_coverage"]["coverage_percentage"],
            -row[3]["total_score"],
        )
    )

    rag_source = retrieve_label_excerpts(
        medicine_name=identity.get("canonical_name") or name,
        indication=indication,
        catalog_medicine_id=identity.get("catalog_medicine_id"),
        top_k=5,
    )
    if not rag_source.get("excerpts"):
        groq_source = {
            "enabled": False,
            "status": "refused_no_evidence",
            "summary": None,
            "note": INSUFFICIENT_EVIDENCE_MESSAGE,
        }
        source_evidence_message = INSUFFICIENT_EVIDENCE_MESSAGE
    else:
        groq_source = maybe_groq_summarise(rag_source.get("excerpts") or [], medicine_name=name)
        source_evidence_message = None

    therapeutic_ranked = []
    for idx, (payload, cand, safety, score, claims, feature_xai, mcs) in enumerate(
        therapeutic_eligible[:top_n], start=1
    ):
        payload["rank"] = idx
        explanation = explain_candidate(
            rank=idx, score=score, candidate=cand, safety=safety, source_claims=claims
        )
        explanation["title"] = "Rule-based score explanation"
        explanation["primary_explanation_type"] = "rule_based"
        explanation["warning_banner"] = DIFFERENT_INGREDIENT_BANNER
        explanation["mcs_note"] = MCS_LIMITATION
        payload["important_differences"] = explanation["important_differences"]
        payload["explanation"] = explanation
        payload["real_xai"] = _real_xai_for_score(score)  # U10: SHAP/LIME dashboard data
        payload["rule_based_explanation"] = _rule_based_explanation(
            rank=idx,
            score=score,
            candidate_type=CandidateType.DIFFERENT_ACTIVE_INGREDIENT.value,
            filter_result=None,
            mcs=mcs,
            feature_xai=feature_xai,
        )
        rag = retrieve_label_excerpts(
            medicine_name=payload.get("candidate_name") or "",
            indication=indication,
            catalog_medicine_id=(cand.get("record") or {}).get("catalog_medicine_id"),
            top_k=3,
        )
        payload["rag_evidence"] = rag
        if not rag.get("excerpts"):
            payload["evidence_sufficiency"] = "insufficient"
            payload["evidence_message"] = INSUFFICIENT_EVIDENCE_MESSAGE
        else:
            payload["evidence_sufficiency"] = "sufficient"
            payload["evidence_message"] = None
        therapeutic_ranked.append(payload)

    base["evaluation_status"] = "completed"
    if not product_ranked and not therapeutic_ranked and not raw_candidates and not product_raw:
        base["missing_information"].append(
            "No product or therapeutic candidates were retrieved for this verified indication."
        )
    if source_evidence_message:
        base["missing_information"].append(source_evidence_message)

    base["product_candidates"] = product_ranked
    base["therapeutic_candidates"] = therapeutic_ranked
    base["eligible_alternatives"] = therapeutic_ranked  # backward compatible
    base["blocked_candidates"] = blocked
    base["withdrawn_candidates"] = withdrawn
    base["insufficient_candidates"] = insufficient
    base["rejected_same_moiety_candidates"] = rejected_same[:25]
    base["source_rag_evidence"] = rag_source
    base["source_rag_summary"] = groq_source
    base["source_evidence_message"] = source_evidence_message
    base["dq2_alignment"] = {
        "definition": (
            "DQ2 operationalised as ranking of same-active-moiety product candidates "
            "after mandatory filters, plus separate different-active-ingredient "
            "therapeutic candidates for pharmacist review — not therapeutic equivalence."
        ),
        "mcs_role": MCS_LIMITATION,
    }
    base["spec_research_layers"] = {
        "O3_MCS": "after_mandatory_filters_supporting_only",
        "O4_RAG": rag_source.get("status"),
        "O5_explanation": "rule_based_primary",
        "note": "Research layers run only after HITL confirmation; never auto-prescribe.",
    }
    base["audit"] = {
        "evaluation_id": evaluation_id,
        "prescription_id": prescription_id,
        "prescription_item_id": item_id,
        "rules_engine_version": RULES_ENGINE_VERSION,
        "dataset_version": _dataset_version(identity),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_source": identity.get("data_source"),
        "product_candidate_count": len(product_ranked),
        "therapeutic_candidate_count": len(therapeutic_ranked),
    }
    return base
