"""Safety screening for therapeutic alternative candidates."""

from __future__ import annotations

from app.services.therapeutic.identity import normalize_name


HARD_BLOCK_STATUSES = {
    "blocked_by_safety_rule",
    "withdrawn_or_discontinued",
    "identity_not_confirmed",
}


def screen_candidate(
    *,
    source_route: str | None,
    source_form: str | None,
    candidate_record: dict,
    candidate_spl: dict | None,
    patient_context: dict,
    identity_confirmed: bool,
) -> dict:
    findings: list[dict] = []
    missing: list[str] = []
    status = "eligible_for_pharmacist_review"

    if not identity_confirmed:
        return {
            "status": "identity_not_confirmed",
            "safety_findings": [
                {
                    "severity": "hard",
                    "code": "identity_not_confirmed",
                    "message": "Candidate identity is not confirmed across connected datasets.",
                }
            ],
            "missing_information": [],
            "route_comparison": {},
            "dosage_form_comparison": {},
        }

    market = candidate_record.get("market_status")
    withdrawn = candidate_record.get("withdrawal_status")
    if market == "withdrawn" or withdrawn:
        return {
            "status": "withdrawn_or_discontinued",
            "safety_findings": [
                {
                    "severity": "hard",
                    "code": "withdrawn_or_discontinued",
                    "message": f"Candidate marked withdrawn/discontinued (market_status={market}).",
                    "source_record_id": candidate_record.get("drugbank_id"),
                }
            ],
            "missing_information": [],
            "route_comparison": {},
            "dosage_form_comparison": {},
        }

    allergies = [normalize_name(a) for a in (patient_context.get("allergies") or [])]
    allergy_status = patient_context.get("allergy_status")
    if allergy_status in (None, "", "unknown", "not assessed"):
        missing.append("allergy_status_detail_not_assessed")

    # Allergy hard blocks
    class_name = normalize_name(candidate_record.get("drug_class"))
    name = normalize_name(candidate_record.get("generic_name"))
    for allergy in allergies:
        if not allergy:
            continue
        if allergy in name or allergy in class_name or (
            "penicillin" in allergy and "penicillin" in class_name
        ) or ("nsaid" in allergy and "nsaid" in class_name):
            findings.append(
                {
                    "severity": "hard",
                    "code": "allergy_conflict",
                    "message": f"Documented allergy conflict with '{allergy}'.",
                }
            )
            status = "blocked_by_safety_rule"

    contraindications = []
    if candidate_spl:
        contraindications = [normalize_name(c) for c in (candidate_spl.get("contraindications") or [])]
    patient_conditions = [normalize_name(c) for c in (patient_context.get("conditions") or [])]
    for cond in patient_conditions:
        for contra in contraindications:
            if cond and contra and (cond in contra or contra in cond):
                findings.append(
                    {
                        "severity": "hard",
                        "code": "contraindication_conflict",
                        "message": f"Explicit contraindication matching patient context '{cond}'.",
                    }
                )
                status = "blocked_by_safety_rule"

    # Pregnancy restriction
    pregnancy = normalize_name(str(patient_context.get("pregnancy_status") or ""))
    if pregnancy in {"pregnant", "pregnancy", "yes"}:
        restrictions = candidate_record.get("population_restrictions") or []
        spl_preg = normalize_name((candidate_spl or {}).get("pregnancy") or "")
        if "pregnancy" in restrictions or "contraindicated" in spl_preg or "avoid" in spl_preg:
            findings.append(
                {
                    "severity": "hard",
                    "code": "pregnancy_restriction",
                    "message": "Known pregnancy restriction for this candidate.",
                }
            )
            status = "blocked_by_safety_rule"

    # Age restriction
    age = patient_context.get("age_years")
    restrictions = candidate_record.get("population_restrictions") or []
    if age is not None and age < 12 and "children_under_12" in restrictions:
        findings.append(
            {
                "severity": "hard",
                "code": "age_restriction",
                "message": "Candidate restricted in children under 12.",
            }
        )
        status = "blocked_by_safety_rule"

    # Current medicines interactions
    current = [normalize_name(m) for m in (patient_context.get("current_medicines") or [])]
    interactions = [normalize_name(i) for i in (candidate_record.get("drug_interactions") or [])]
    for med in current:
        for inter in interactions:
            if med and inter and (med == inter or med in inter or inter in med):
                findings.append(
                    {
                        "severity": "hard",
                        "code": "serious_interaction",
                        "message": f"Serious interaction risk with current medicine '{med}'.",
                    }
                )
                status = "blocked_by_safety_rule"

    # Route compatibility (SPL single route and/or catalog routes list)
    catalog_routes = [normalize_name(r) for r in (candidate_record.get("routes") or []) if r]
    cand_route = normalize_name((candidate_spl or {}).get("route") or "")
    if not cand_route and catalog_routes:
        cand_route = catalog_routes[0]
    src_route = normalize_name(source_route)
    route_compatible = bool(
        src_route
        and (
            (cand_route and src_route == cand_route)
            or any(src_route == r or src_route in r or r in src_route for r in catalog_routes)
        )
    )
    displayed_route = (candidate_spl or {}).get("route") or (
        (candidate_record.get("routes") or [None])[0]
    )
    route_comparison = {
        "source_route": source_route,
        "candidate_route": displayed_route,
        "compatible": route_compatible,
        "status": "matched"
        if route_compatible
        else ("unknown" if not src_route or (not cand_route and not catalog_routes) else "unmatched"),
    }
    # Only hard-block when both sides are known and clearly incompatible
    if src_route and (cand_route or catalog_routes) and not route_compatible:
        findings.append(
            {
                "severity": "hard",
                "code": "route_incompatibility",
                "message": f"Route incompatibility ({source_route} vs {displayed_route}).",
            }
        )
        status = "blocked_by_safety_rule"

    catalog_forms = [normalize_name(f) for f in (candidate_record.get("dosage_forms") or []) if f]
    cand_form = normalize_name((candidate_spl or {}).get("dosage_form") or "")
    if not cand_form and catalog_forms:
        cand_form = catalog_forms[0]
    src_form = normalize_name(source_form)
    form_compatible = bool(
        src_form
        and (
            (cand_form and (src_form in cand_form or cand_form in src_form))
            or any(src_form in f or f in src_form for f in catalog_forms)
        )
    )
    displayed_form = (candidate_spl or {}).get("dosage_form") or (
        (candidate_record.get("dosage_forms") or [None])[0]
    )
    form_comparison = {
        "source_dosage_form": source_form,
        "candidate_dosage_form": displayed_form,
        "compatible": form_compatible,
        "status": "matched"
        if form_compatible
        else ("unknown" if not src_form or (not cand_form and not catalog_forms) else "partial"),
    }

    # Renal / hepatic warnings — informational unless severe flags set
    renal = normalize_name(str(patient_context.get("renal_impairment") or ""))
    hepatic = normalize_name(str(patient_context.get("hepatic_impairment") or ""))
    if renal in {"severe", "yes"} and candidate_spl and "avoid" in normalize_name(candidate_spl.get("renal_impairment") or ""):
        findings.append(
            {
                "severity": "hard",
                "code": "renal_warning",
                "message": "Avoid in severe renal impairment per SPL caution.",
            }
        )
        status = "blocked_by_safety_rule"
    if hepatic in {"severe", "yes"} and (
        candidate_record.get("hepatic_warning")
        or (candidate_spl and "avoid" in normalize_name(candidate_spl.get("hepatic_impairment") or ""))
    ):
        findings.append(
            {
                "severity": "hard",
                "code": "hepatic_warning",
                "message": "Avoid in severe hepatic impairment per connected source.",
            }
        )
        status = "blocked_by_safety_rule"

    # Missing safety domains
    if not candidate_spl:
        missing.append("FDA_SPL_label_not_linked")
    for field in ("contraindications", "warnings_and_precautions", "drug_interactions"):
        if candidate_spl and not candidate_spl.get(field):
            missing.append(f"{field}_not_available_in_connected_source")

    if status == "eligible_for_pharmacist_review" and missing and not findings:
        # still eligible but note insufficient coverage areas
        pass

    if status == "eligible_for_pharmacist_review" and any(f["severity"] == "hard" for f in findings):
        status = "blocked_by_safety_rule"

    return {
        "status": status,
        "safety_findings": findings,
        "missing_information": missing,
        "route_comparison": route_comparison,
        "dosage_form_comparison": form_comparison,
    }
