"""Candidate classification and clinical-safety constants (Sprint 1)."""

from __future__ import annotations

from enum import StrEnum


class CandidateType(StrEnum):
    SAME_ACTIVE_MOIETY_PRODUCT = "SAME_ACTIVE_MOIETY_PRODUCT"
    DIFFERENT_ACTIVE_INGREDIENT = "DIFFERENT_ACTIVE_INGREDIENT"


INSUFFICIENT_EVIDENCE_MESSAGE = "Insufficient evidence — pharmacist review required."

MCS_LIMITATION = (
    "Structural similarity is supporting evidence only and does not establish "
    "clinical interchangeability."
)

DIFFERENT_INGREDIENT_BANNER = (
    "Different active ingredient — pharmacist assessment required"
)

# Rejected / discouraged user-facing phrases (active UI/API)
FORBIDDEN_EQUIVALENCE_PHRASES = (
    "therapeutically equivalent",
    "equivalent medicine",
    "equivalent alternative",
    "safe substitute",
    "recommended replacement",
    "automatic substitute",
    "auto-substitute",
    "clinically interchangeable",
)


class FilterRejectReason(StrEnum):
    ACTIVE_INGREDIENT_MISMATCH = "ACTIVE_INGREDIENT_MISMATCH"
    ACTIVE_MOIETY_UNVERIFIED = "ACTIVE_MOIETY_UNVERIFIED"
    SALT_RELATIONSHIP_UNVERIFIED = "SALT_RELATIONSHIP_UNVERIFIED"
    ROUTE_MISMATCH = "ROUTE_MISMATCH"
    DOSAGE_FORM_MISMATCH = "DOSAGE_FORM_MISMATCH"
    RELEASE_TYPE_MISMATCH = "RELEASE_TYPE_MISMATCH"
    COMBINATION_PRODUCT_MISMATCH = "COMBINATION_PRODUCT_MISMATCH"
    STRENGTH_NOT_COMPARABLE = "STRENGTH_NOT_COMPARABLE"
    PROVENANCE_MISSING = "PROVENANCE_MISSING"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"


FILTER_MESSAGES_EN_GB: dict[str, str] = {
    FilterRejectReason.ACTIVE_INGREDIENT_MISMATCH: (
        "Active ingredient differs from the pharmacist-confirmed medicine."
    ),
    FilterRejectReason.ACTIVE_MOIETY_UNVERIFIED: (
        "Active-moiety relationship could not be verified from the available data."
    ),
    FilterRejectReason.SALT_RELATIONSHIP_UNVERIFIED: (
        "Salt/base/ester relationship could not be verified from the available data."
    ),
    FilterRejectReason.ROUTE_MISMATCH: (
        "Route differs from the pharmacist-confirmed medicine."
    ),
    FilterRejectReason.DOSAGE_FORM_MISMATCH: (
        "Dosage form is not compatible with the pharmacist-confirmed medicine."
    ),
    FilterRejectReason.RELEASE_TYPE_MISMATCH: (
        "Modified-release status is not compatible."
    ),
    FilterRejectReason.COMBINATION_PRODUCT_MISMATCH: (
        "Single-ingredient versus combination-product status is not compatible."
    ),
    FilterRejectReason.STRENGTH_NOT_COMPARABLE: (
        "Strengths could not be compared reliably."
    ),
    FilterRejectReason.PROVENANCE_MISSING: (
        "Trusted FDA NDC, FDA SPL or DrugBank provenance is missing."
    ),
    FilterRejectReason.EVIDENCE_INSUFFICIENT: INSUFFICIENT_EVIDENCE_MESSAGE,
}


def pharmacist_message(reason: str) -> str:
    return FILTER_MESSAGES_EN_GB.get(reason, reason)
