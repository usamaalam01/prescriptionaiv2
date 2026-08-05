"""Canonical medicine envelope (nullable fields for legacy catalogue gaps)."""

from __future__ import annotations

from typing import Any

from app.services.therapeutic.salt_normalisation import (
    infer_combination,
    infer_release_type,
    normalize_medicine_suggestion,
    resolve_moiety,
)


def parse_strength(raw: str | None) -> tuple[float | None, str | None, str | None]:
    """Return (value, unit, normalised_display)."""
    import re

    if not raw:
        return None, None, None
    text = str(raw).strip()
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(mg|mcg|µg|ug|g|ml|mL|%)(?:\s*/\s*(\d+(?:\.\d+)?\s*(?:ml|mL)))?",
        text,
        re.I,
    )
    if not m:
        return None, None, text
    val = float(m.group(1))
    unit = m.group(2).lower().replace("µg", "mcg").replace("ug", "mcg")
    norm = f"{val} {unit}"
    return val, unit, norm


def build_canonical_envelope(
    *,
    medicine_name: str | None,
    strength: str | None = None,
    dosage_form: str | None = None,
    route: str | None = None,
    product_ndc: str | None = None,
    spl_set_id: str | None = None,
    drugbank_id: str | None = None,
    catalog_medicine_id: int | None = None,
    source_provenance: list[str] | None = None,
    normalisation_method: str | None = None,
) -> dict[str, Any]:
    suggestion = normalize_medicine_suggestion(input_value=medicine_name)
    moiety = resolve_moiety(medicine_name)
    sval, sunit, snorm = parse_strength(strength)
    release = infer_release_type(dosage_form, medicine_name)
    combo = infer_combination(medicine_name)

    provenance = list(source_provenance or [])
    if drugbank_id and not str(drugbank_id).startswith("CATALOG:"):
        if "DrugBank" not in provenance:
            provenance.append("DrugBank")
    if product_ndc and "FDA_NDC" not in provenance:
        provenance.append("FDA_NDC")
    if spl_set_id and "FDA_SPL" not in provenance:
        provenance.append("FDA_SPL")

    conf = float(moiety.get("confidence") or 0)
    method = normalisation_method or moiety.get("match_method") or "unknown"

    return {
        "canonical_ingredient_id": (
            f"MOIETY:{moiety.get('base_ingredient')}"
            if moiety.get("base_ingredient")
            else (drugbank_id or (f"CATALOG:{catalog_medicine_id}" if catalog_medicine_id else None))
        ),
        "canonical_ingredient_name": moiety.get("canonical_ingredient_name") or medicine_name,
        "base_ingredient": moiety.get("base_ingredient"),
        "salt_or_ester": moiety.get("salt_or_ester"),
        "variant_type": "salt" if moiety.get("salt_or_ester") else "base",
        "strength_value": sval,
        "strength_unit": sunit,
        "normalised_strength": snorm or strength,
        "dosage_form": dosage_form,
        "route": route,
        "release_type": release,
        "combination_product": combo,
        "product_ndc": product_ndc,
        "spl_set_id": spl_set_id,
        "drugbank_id": drugbank_id,
        "normalisation_confidence": conf,
        "normalisation_method": method,
        "source_provenance": provenance,
        "normalisation_suggestion": suggestion,
    }
