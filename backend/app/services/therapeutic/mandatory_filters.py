"""Mandatory eligibility filters for SAME_ACTIVE_MOIETY_PRODUCT candidates."""

from __future__ import annotations

from typing import Any

from app.services.therapeutic.candidate_types import (
    FilterRejectReason,
    pharmacist_message,
)
from app.services.therapeutic.salt_normalisation import (
    infer_combination,
    infer_release_type,
    normalize_key,
    same_active_moiety,
)


def _routes_compatible(a: str | None, b: str | None) -> bool:
    na, nb = normalize_key(a), normalize_key(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Mild synonymy
    synonyms = [
        {"oral", "po", "by mouth"},
        {"intravenous", "iv"},
        {"intramuscular", "im"},
        {"subcutaneous", "sc", "sq"},
        {"topical", "cutaneous"},
    ]
    for group in synonyms:
        if na in group and nb in group:
            return True
    return False


def _forms_compatible(a: str | None, b: str | None) -> bool:
    na, nb = normalize_key(a), normalize_key(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Tablet variants
    if "tablet" in na and "tablet" in nb:
        return True
    if "capsule" in na and "capsule" in nb:
        return True
    if "injection" in na and "injection" in nb:
        return True
    if "solution" in na and "solution" in nb:
        return True
    return False


def _strengths_comparable(src: dict[str, Any], cand: dict[str, Any]) -> bool:
    sv, su = src.get("strength_value"), src.get("strength_unit")
    cv, cu = cand.get("strength_value"), cand.get("strength_unit")
    if sv is None or cv is None or not su or not cu:
        # Allow missing strength only if both missing normalised — still not comparable for product match
        return False
    if normalize_key(su) != normalize_key(cu):
        return False
    # Same unit: comparable if within 5% or exact
    if sv == 0:
        return cv == 0
    return abs(sv - cv) / max(abs(sv), abs(cv)) <= 0.05 or abs(sv - cv) < 1e-6


def apply_mandatory_filters(
    *,
    source_envelope: dict[str, Any],
    candidate_envelope: dict[str, Any],
    source_name: str | None,
    candidate_name: str | None,
) -> dict[str, Any]:
    """Return eligibility for SAME_ACTIVE_MOIETY_PRODUCT path."""
    passed: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []

    def fail(code: FilterRejectReason) -> None:
        failed.append({"code": code.value, "message": pharmacist_message(code.value)})

    def ok(code: str, message: str) -> None:
        passed.append({"code": code, "message": message})

    compatible, reason = same_active_moiety(source_name, candidate_name)
    if not compatible:
        fail(FilterRejectReason(reason) if reason in FilterRejectReason._value2member_map_ else FilterRejectReason.ACTIVE_MOIETY_UNVERIFIED)
    else:
        ok("ACTIVE_MOIETY", "Active moiety relationship verified from the DrugBank-derived salt/base map (with curated overrides).")
        ok("SALT_RELATIONSHIP", "Salt/base/ester relationship compatible or both base forms.")

    if not _routes_compatible(source_envelope.get("route"), candidate_envelope.get("route")):
        fail(FilterRejectReason.ROUTE_MISMATCH)
    else:
        ok("ROUTE", "Route compatible with pharmacist-confirmed medicine.")

    if not _forms_compatible(source_envelope.get("dosage_form"), candidate_envelope.get("dosage_form")):
        fail(FilterRejectReason.DOSAGE_FORM_MISMATCH)
    else:
        ok("DOSAGE_FORM", "Dosage form compatible.")

    src_rel = source_envelope.get("release_type") or infer_release_type(
        source_envelope.get("dosage_form"), source_name
    )
    cand_rel = candidate_envelope.get("release_type") or infer_release_type(
        candidate_envelope.get("dosage_form"), candidate_name
    )
    if src_rel != "unspecified" and cand_rel != "unspecified" and src_rel != cand_rel:
        fail(FilterRejectReason.RELEASE_TYPE_MISMATCH)
    else:
        ok("RELEASE_TYPE", "Release type compatible or unspecified.")

    src_combo = source_envelope.get("combination_product")
    cand_combo = candidate_envelope.get("combination_product")
    if src_combo is None:
        src_combo = infer_combination(source_name)
    if cand_combo is None:
        cand_combo = infer_combination(candidate_name)
    if src_combo is not None and cand_combo is not None and bool(src_combo) != bool(cand_combo):
        fail(FilterRejectReason.COMBINATION_PRODUCT_MISMATCH)
    else:
        ok("COMBINATION", "Single/combination status compatible or undetermined.")

    if not _strengths_comparable(source_envelope, candidate_envelope):
        fail(FilterRejectReason.STRENGTH_NOT_COMPARABLE)
    else:
        ok("STRENGTH", "Strengths comparable.")

    src_prov = source_envelope.get("source_provenance") or []
    cand_prov = candidate_envelope.get("source_provenance") or []
    trusted = {"FDA_NDC", "FDA_SPL", "DrugBank"}
    if not (set(cand_prov) & trusted):
        # Also accept if drugbank_id / product_ndc present on envelope
        if not candidate_envelope.get("product_ndc") and not (
            candidate_envelope.get("drugbank_id")
            and not str(candidate_envelope.get("drugbank_id")).startswith("CATALOG:")
        ):
            fail(FilterRejectReason.PROVENANCE_MISSING)
        else:
            ok("PROVENANCE", "Trusted identifier present on candidate.")
    else:
        ok("PROVENANCE", "Trusted FDA/DrugBank provenance present.")

    if source_envelope.get("normalisation_confidence", 1) < 0.5 or candidate_envelope.get(
        "normalisation_confidence", 1
    ) < 0.5:
        if not any(f["code"] == FilterRejectReason.ACTIVE_MOIETY_UNVERIFIED.value for f in failed):
            # already covered often
            if not compatible:
                pass
            elif source_envelope.get("normalisation_confidence", 1) < 0.5:
                fail(FilterRejectReason.ACTIVE_MOIETY_UNVERIFIED)

    eligible = len(failed) == 0
    return {
        "eligible": eligible,
        "passed_filters": passed,
        "failed_filters": failed,
        "candidate_type_if_eligible": "SAME_ACTIVE_MOIETY_PRODUCT",
    }
