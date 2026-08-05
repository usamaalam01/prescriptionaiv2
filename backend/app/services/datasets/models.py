"""Unified medicine catalog records (FDA NDC + DrugBank + optional SPL)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CatalogHit:
    """Top candidate returned by pharmaceutical validation."""

    canonical_name: str
    score: float
    source: str
    brand_names: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    dosage_forms: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)
    drugbank_id: str | None = None
    product_ndc: str | None = None
    matched_alias: str | None = None
    reason: str = ""


DISCLAIMER = (
    "PharmaAssist is a pharmacist decision-support prototype using curated datasets. "
    "It is not a clinical care system and must not be used as the sole basis for "
    "prescribing, dispensing, or patient treatment decisions."
)
