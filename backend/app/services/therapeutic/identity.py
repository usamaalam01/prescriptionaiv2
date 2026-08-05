"""Drug identity resolution across local FDA/DrugBank catalog + DEMO seed enrichment."""

from __future__ import annotations

from difflib import SequenceMatcher

from app.services.therapeutic.seed_data import DRUGBANK_RECORDS, FDA_NDC_RECORDS, FDA_SPL_RECORDS


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.lower().replace("-", " ").split())


def resolve_identity(medicine_name: str, *, drugbank_id: str | None = None, unii: str | None = None) -> dict:
    """Map a prescribed medicine to a canonical identity.

    Preference order:
    1. Explicit DrugBank id / UNII against DEMO seed (tests + enrichment)
    2. Local FDA NDC + DrugBank catalog (production path)
    3. DEMO seed name/synonym matching (offline fallback)
    """
    empty = {
        "canonical_drug_id": "",
        "canonical_name": "",
        "active_ingredient": "",
        "drugbank_id": "",
        "unii": "",
        "matched_spl_ids": [],
        "matched_product_ndcs": [],
        "match_method": "",
        "identity_confidence": 0.0,
        "manual_confirmation_required": False,
        "identity_confirmed": False,
        "message": "Medicine identity could not be confirmed across the connected datasets.",
        "data_source": None,
        "provenance_label": None,
    }

    if drugbank_id and drugbank_id in DRUGBANK_RECORDS:
        return _finalize_seed(DRUGBANK_RECORDS[drugbank_id], "exact_drugbank_id", 1.0, False)

    if unii:
        for row in DRUGBANK_RECORDS.values():
            if normalize_name(row.get("unii")) == normalize_name(unii):
                return _finalize_seed(row, "exact_unii", 0.98, False)

    key = normalize_name(medicine_name)
    if not key:
        return empty

    # Production catalog first for named lookup
    try:
        from app.services.therapeutic.catalog_therapeutic import resolve_catalog_identity

        catalog_hit = resolve_catalog_identity(medicine_name)
    except Exception:
        catalog_hit = None

    seed_hit = _resolve_seed_by_name(key)

    if catalog_hit and seed_hit:
        # Prefer catalog IDs; attach seed enrichment for ATC/mechanism ranking
        merged = dict(catalog_hit)
        merged["seed_enrichment_id"] = seed_hit["drugbank_id"]
        seed_row = DRUGBANK_RECORDS.get(seed_hit["drugbank_id"]) or {}
        merged["drug_class"] = seed_row.get("drug_class") or ""
        # Pharmacist-facing: catalog is primary provenance
        merged["provenance_label"] = catalog_hit.get("provenance_label")
        merged["identity_confirmed"] = bool(
            catalog_hit.get("identity_confirmed") or seed_hit.get("identity_confirmed")
        )
        merged["manual_confirmation_required"] = bool(
            catalog_hit.get("manual_confirmation_required")
            and not catalog_hit.get("identity_confirmed")
        )
        merged["message"] = None
        return merged

    if catalog_hit:
        catalog_hit["message"] = None
        return catalog_hit

    if seed_hit:
        return seed_hit

    empty["message"] = "Medicine identity could not be confirmed across the connected datasets."
    return empty


def _resolve_seed_by_name(key: str) -> dict | None:
    # Exact generic name / normalized active ingredient
    for row in DRUGBANK_RECORDS.values():
        if normalize_name(row["generic_name"]) == key:
            return _finalize_seed(row, "exact_generic_name", 0.95, False)
        active = normalize_name(row.get("active_ingredient") or row["generic_name"])
        if active == key:
            return _finalize_seed(row, "exact_normalized_active_ingredient", 0.95, False)

    # Synonym match
    for row in DRUGBANK_RECORDS.values():
        for syn in row.get("synonyms", []):
            if normalize_name(syn) == key:
                return _finalize_seed(row, "synonym_match", 0.9, False)

    # Salt/base style: strip common suffixes
    base = key.replace(" sodium", "").replace(" potassium", "").replace(" hydrochloride", "").strip()
    if base != key:
        for row in DRUGBANK_RECORDS.values():
            if normalize_name(row["generic_name"]) == base:
                return _finalize_seed(row, "salt_base_normalization", 0.85, True)

    # Controlled fuzzy match
    best = None
    best_score = 0.0
    for row in DRUGBANK_RECORDS.values():
        names = [row["generic_name"], *row.get("synonyms", [])]
        for name in names:
            score = SequenceMatcher(None, key, normalize_name(name)).ratio()
            if score > best_score:
                best_score = score
                best = row
    if best and best_score >= 0.72:
        return _finalize_seed(best, "controlled_fuzzy_match", round(best_score, 3), True)
    return None


def _finalize_seed(row: dict, method: str, confidence: float, manual: bool) -> dict:
    spl_ids = [
        spl_id
        for spl_id, spl in FDA_SPL_RECORDS.items()
        if spl.get("linked_drugbank_id") == row["drugbank_id"]
        or normalize_name(spl.get("active_ingredient")) == normalize_name(row["generic_name"])
    ]
    ndcs = [
        ndc_id
        for ndc_id, ndc in FDA_NDC_RECORDS.items()
        if ndc.get("linked_drugbank_id") == row["drugbank_id"]
        or normalize_name(ndc.get("active_ingredient")) == normalize_name(row["generic_name"])
    ]
    return {
        "canonical_drug_id": row["drugbank_id"],
        "canonical_name": row["generic_name"],
        "active_ingredient": row["generic_name"],
        "drugbank_id": row["drugbank_id"],
        "unii": row.get("unii") or "",
        "matched_spl_ids": spl_ids,
        "matched_product_ndcs": ndcs,
        "match_method": method,
        "identity_confidence": confidence,
        "manual_confirmation_required": manual,
        "identity_confirmed": not manual and confidence >= 0.85,
        "message": None,
        "data_source": "demo_seed",
        "provenance_label": "DEMO DATA",
        "seed_enrichment_id": row["drugbank_id"],
        "drug_class": row.get("drug_class") or "",
    }
