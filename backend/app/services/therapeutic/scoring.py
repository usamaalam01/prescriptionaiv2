"""Evidence Match Score calculation (coverage/similarity only — not clinical confidence)."""

from __future__ import annotations


WEIGHTS = {
    "indication_relationship": 35,
    "atc_or_therapeutic_class": 15,
    "mechanism_relationship": 10,
    "target_or_pathway": 5,
    "route_compatibility": 10,
    "dosage_form_compatibility": 5,
    "patient_population_compatibility": 10,
    "contraindication_warning_assessment": 5,
    "interaction_assessment_coverage": 5,
}


def calculate_evidence_match_score(
    *,
    indication_related: bool,
    class_related: bool,
    mechanism_related: bool,
    target_related: bool,
    route_comparison: dict,
    form_comparison: dict,
    population_ok: bool | None,
    contra_assessed: bool,
    interaction_assessed: bool,
    source_claim_ids: dict[str, list[str]] | None = None,
) -> dict:
    source_claim_ids = source_claim_ids or {}
    components = []

    def add(component: str, matched: bool | None, explanation: str):
        weight = WEIGHTS[component]
        if matched is True:
            status, awarded = "matched", weight
        elif matched is False:
            status, awarded = "unmatched", 0
        else:
            status, awarded = "unknown", 0
        components.append(
            {
                "component": component,
                "weight": weight,
                "awarded": awarded,
                "status": status,
                "explanation": explanation,
                "source_claim_ids": source_claim_ids.get(component, []),
            }
        )

    add(
        "indication_relationship",
        indication_related,
        "Confirmed overlapping indication concept between source and candidate.",
    )
    add(
        "atc_or_therapeutic_class",
        class_related,
        "ATC prefix or therapeutic class relationship present.",
    )
    add(
        "mechanism_relationship",
        mechanism_related,
        "Mechanism fields share action/target/pathway/effect.",
    )
    add(
        "target_or_pathway",
        target_related,
        "Shared DrugBank target identifiers.",
    )
    route_status = route_comparison.get("status")
    add(
        "route_compatibility",
        True if route_status == "matched" else False if route_status == "unmatched" else None,
        f"Route comparison status={route_status}.",
    )
    form_status = form_comparison.get("status")
    add(
        "dosage_form_compatibility",
        True if form_status == "matched" else False if form_status == "unmatched" else None,
        f"Dosage-form comparison status={form_status}.",
    )
    add(
        "patient_population_compatibility",
        population_ok,
        "Population restrictions assessed against patient context.",
    )
    add(
        "contraindication_warning_assessment",
        True if contra_assessed else None,
        "Contraindication/warning fields reviewed from connected SPL/DrugBank.",
    )
    add(
        "interaction_assessment_coverage",
        True if interaction_assessed else None,
        "Interaction list present in connected DrugBank/SPL sources.",
    )

    total = sum(c["awarded"] for c in components)
    available = sum(1 for c in components if c["status"] != "unknown")
    return {
        "score_label": "Evidence Match Score",
        "total_score": total,
        "maximum_score": 100,
        "components": components,
        "evidence_coverage": {
            "available_domains": available,
            "required_domains": 9,
            "coverage_percentage": round(100 * available / 9, 1),
        },
    }
