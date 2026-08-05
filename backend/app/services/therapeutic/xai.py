"""Template-based XAI explanations (no LLM required)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.therapeutic.seed_data import DATASET_VERSION, DEMO_LABEL, make_claim


DISCLAIMER = (
    "Decision-support only. Candidates are for pharmacist review and are not "
    "automatic substitution, prescribing recommendations, or proof of clinical "
    "interchangeability. A licensed pharmacist must verify the indication, "
    "patient context, dose, contraindications, interactions and applicable "
    "clinical guidance."
)


def _claim_provenance(identity: dict, candidate: dict) -> tuple[str, str, bool]:
    """Return (label, dataset_version, is_demo)."""
    label = (
        candidate.get("provenance_label")
        or identity.get("provenance_label")
        or DEMO_LABEL
    )
    is_demo = label == DEMO_LABEL or candidate.get("data_source") == "demo_seed"
    version = DATASET_VERSION
    if not is_demo:
        try:
            from app.services.therapeutic.catalog_therapeutic import catalog_dataset_version

            version = catalog_dataset_version()
        except Exception:
            version = "catalog-local"
    return label, version, is_demo


def build_source_claims(source_identity: dict, candidate: dict, safety: dict) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    label, version, is_demo = _claim_provenance(source_identity, candidate)
    source_dataset = "DrugBank"
    if candidate.get("data_source") == "catalog" or source_identity.get("data_source") == "catalog":
        srcs = (candidate.get("record") or {}).get("sources") or source_identity.get("catalog_sources") or []
        # Provenance asserts accept only DrugBank / FDA_SPL / FDA_NDC (and combinations)
        allowed = {"DrugBank", "FDA_SPL", "FDA_NDC"}
        clean = [s for s in srcs if s in allowed]
        if clean:
            source_dataset = "+".join(clean)
        else:
            source_dataset = "DrugBank+FDA_NDC"

    record_id = (
        source_identity.get("drugbank_id")
        or source_identity.get("canonical_drug_id")
        or "unknown"
    )
    claims = []
    claims.append(
        make_claim(
            claim_id=f"id-{record_id}",
            claim=f"Source medicine resolved as {source_identity.get('canonical_name')}.",
            claim_type="identity",
            source_dataset=source_dataset,
            source_record_id=str(record_id),
            source_field_or_section="canonical_name",
            raw_evidence=str(source_identity.get("canonical_name") or ""),
            demo_data=is_demo,
        )
    )
    claims.append(
        make_claim(
            claim_id=f"ind-{candidate['candidate_drug_id']}",
            claim="Candidate shares a relevant indication relationship with the prescribed medicine.",
            claim_type="indication",
            source_dataset=source_dataset,
            source_record_id=candidate["candidate_drug_id"],
            source_field_or_section="indications",
            raw_evidence=", ".join(candidate["indication_relationship"].get("candidate_indications") or []),
            demo_data=is_demo,
        )
    )
    if candidate["class_relationship"].get("related"):
        claims.append(
            make_claim(
                claim_id=f"class-{candidate['candidate_drug_id']}",
                claim="Therapeutic class / ATC relationship identified.",
                claim_type="class",
                source_dataset=source_dataset,
                source_record_id=candidate["candidate_drug_id"],
                source_field_or_section="drug_class",
                raw_evidence=str(candidate["class_relationship"]),
                demo_data=is_demo,
            )
        )
    if candidate["mechanism_relationship"].get("related"):
        claims.append(
            make_claim(
                claim_id=f"mech-{candidate['candidate_drug_id']}",
                claim="Mechanism relationship identified.",
                claim_type="mechanism",
                source_dataset=source_dataset,
                source_record_id=candidate["candidate_drug_id"],
                source_field_or_section="mechanism_of_action",
                raw_evidence=str(candidate["mechanism_relationship"].get("candidate")),
                demo_data=is_demo,
            )
        )
    for finding in safety.get("safety_findings") or []:
        claims.append(
            make_claim(
                claim_id=f"safe-{candidate['candidate_drug_id']}-{finding.get('code')}",
                claim=finding.get("message") or "Safety finding",
                claim_type="safety",
                source_dataset=source_dataset,
                source_record_id=candidate["candidate_drug_id"],
                source_field_or_section=finding.get("code") or "safety",
                raw_evidence=str(finding),
                demo_data=is_demo,
            )
        )
    for claim in claims:
        claim["retrieved_at"] = now
        claim["demo_label"] = label
        claim["demo_data"] = is_demo
        claim["dataset_version"] = version
    return claims


def explain_candidate(*, rank: int, score: dict, candidate: dict, safety: dict, source_claims: list[dict]) -> dict:
    important_differences = []
    if candidate["active_ingredient"]:
        important_differences.append("Different active ingredient from the prescribed medicine.")
    if candidate["class_relationship"].get("source_class") != candidate["class_relationship"].get("candidate_class"):
        important_differences.append(
            f"Class differs: {candidate['class_relationship'].get('source_class') or 'not indexed'} → "
            f"{candidate['class_relationship'].get('candidate_class') or 'not indexed'}."
        )
    if safety.get("route_comparison", {}).get("status") == "matched":
        important_differences.append("Route appears compatible based on connected label/product data.")
    else:
        important_differences.append("Route/dosage-form differences must be reviewed by the pharmacist.")

    is_demo = candidate.get("data_source") == "demo_seed" or (
        (source_claims[0].get("demo_label") if source_claims else "") == DEMO_LABEL
    )

    return {
        "why_identified": candidate.get("why_retrieved") or [],
        "indication_relationship": candidate.get("indication_relationship"),
        "class_or_mechanism_relationship": {
            "class": candidate.get("class_relationship"),
            "mechanism": candidate.get("mechanism_relationship"),
            "target": candidate.get("target_relationship"),
        },
        "route_and_dosage_form_comparison": {
            "route": safety.get("route_comparison"),
            "dosage_form": safety.get("dosage_form_comparison"),
        },
        "important_differences": important_differences,
        "safety_findings": safety.get("safety_findings") or [],
        "missing_information": safety.get("missing_information") or [],
        "why_ranked": (
            f"Rank {rank} among eligible candidates based on indication match, safety eligibility, "
            f"evidence coverage ({score['evidence_coverage']['coverage_percentage']}%), "
            f"class/mechanism relationships, and rule-based Evidence Match Score "
            f"{score['total_score']}/100. Candidate alternative for pharmacist review only."
        ),
        "source_claims": source_claims,
        "disclaimer": DISCLAIMER,
        "explanation_mode": "rule_based_score_explanation",
        "primary_explanation_type": "rule_based",
        "title": "Rule-based score explanation",
        "demo_data": is_demo,
        "provenance_label": candidate.get("provenance_label")
        or (source_claims[0].get("demo_label") if source_claims else DEMO_LABEL),
    }
