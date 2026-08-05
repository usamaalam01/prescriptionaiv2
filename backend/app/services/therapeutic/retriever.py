"""Therapeutic candidate retrieval (different active ingredient only)."""

from __future__ import annotations

from app.services.therapeutic.identity import normalize_name
from app.services.therapeutic.indication import (
    indications_overlap,
    mechanism_related,
    normalize_indication_text,
    normalize_mechanism,
)
from app.services.therapeutic.seed_data import DRUGBANK_RECORDS, FDA_SPL_RECORDS, get_drugbank, get_spl


def retrieve_candidates(source_identity: dict, verified_indication: str) -> list[dict]:
    """Return raw candidate envelopes with retrieval reasons (not yet safety-screened).

    Uses the local FDA/DrugBank catalog when available, and merges DEMO seed
    candidates when seed enrichment exists (richer ATC/mechanism evidence).
    """
    catalog_cands: list[dict] = []
    seed_cands: list[dict] = []

    try:
        from app.services.therapeutic.catalog_therapeutic import retrieve_catalog_candidates

        if source_identity.get("data_source") == "catalog" or source_identity.get("catalog_medicine_id"):
            catalog_cands = retrieve_catalog_candidates(source_identity, verified_indication)
        elif source_identity.get("canonical_name"):
            # Catalog available but identity came from seed — still try catalog by name
            catalog_cands = retrieve_catalog_candidates(source_identity, verified_indication)
    except Exception:
        catalog_cands = []

    seed_id = source_identity.get("seed_enrichment_id") or (
        source_identity.get("drugbank_id") if source_identity.get("data_source") == "demo_seed" else None
    )
    if seed_id and seed_id in DRUGBANK_RECORDS:
        seed_identity = {
            **source_identity,
            "drugbank_id": seed_id,
            "canonical_drug_id": seed_id,
        }
        seed_cands = _retrieve_seed_candidates(seed_identity, verified_indication)

    return _merge_candidates(catalog_cands, seed_cands)


def _merge_candidates(catalog_cands: list[dict], seed_cands: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for cand in catalog_cands:
        key = normalize_name(cand.get("candidate_name"))
        if key:
            by_key[key] = cand
    for cand in seed_cands:
        key = normalize_name(cand.get("candidate_name"))
        if not key:
            continue
        if key not in by_key:
            by_key[key] = cand
            continue
        # Prefer seed enrichment for class/mechanism when catalog already found the name
        existing = by_key[key]
        if not existing.get("class_relationship", {}).get("related") and cand.get("class_relationship", {}).get(
            "related"
        ):
            existing["class_relationship"] = cand["class_relationship"]
            existing["mechanism_relationship"] = cand["mechanism_relationship"]
            existing["target_relationship"] = cand["target_relationship"]
            existing["record"] = {**(existing.get("record") or {}), **(cand.get("record") or {})}
            why = list(existing.get("why_retrieved") or [])
            for w in cand.get("why_retrieved") or []:
                if w not in why:
                    why.append(w)
            existing["why_retrieved"] = why
    return list(by_key.values())


def _retrieve_seed_candidates(source_identity: dict, verified_indication: str) -> list[dict]:
    """Original DEMO seed retrieval (ATC / mechanism / indication gated)."""
    source = get_drugbank(source_identity["drugbank_id"])
    if not source:
        return []

    source_ingredient = normalize_name(source["generic_name"])
    indication = normalize_indication_text(verified_indication, source_section="pharmacist_verified_indication")
    source_mech = normalize_mechanism(
        source.get("mechanism_of_action"),
        source_record_id=source["drugbank_id"],
        source_field="mechanism_of_action",
    )

    candidates: list[dict] = []
    for row in DRUGBANK_RECORDS.values():
        if normalize_name(row["generic_name"]) == source_ingredient:
            continue  # same ingredient — not a therapeutic alternative

        why: list[str] = []
        has_indication = indications_overlap(indication["condition"], row.get("indications", []))
        # Also check SPL indication text
        spl_hit = False
        for spl in FDA_SPL_RECORDS.values():
            if spl.get("linked_drugbank_id") != row["drugbank_id"]:
                continue
            spl_ind = normalize_indication_text(
                spl.get("indications_and_usage"),
                source_record_id=spl["spl_id"],
                source_section="indications_and_usage",
            )
            if indications_overlap(indication["condition"], [spl_ind["condition"], *(row.get("indications") or [])]):
                spl_hit = True
                why.append("FDA SPL indication overlap")
                break
        if has_indication and "FDA SPL indication overlap" not in why:
            why.append("DrugBank indication overlap")

        atc_related = bool(
            source.get("atc_classification")
            and row.get("atc_classification")
            and source["atc_classification"][:4] == row["atc_classification"][:4]
        )
        class_related = normalize_name(source.get("drug_class")) == normalize_name(row.get("drug_class")) or (
            "penicillin" in normalize_name(source.get("drug_class"))
            and "antibiotic" in normalize_name(row.get("drug_class"))
        )
        cand_mech = normalize_mechanism(
            row.get("mechanism_of_action"),
            source_record_id=row["drugbank_id"],
            source_field="mechanism_of_action",
        )
        mech_rel = mechanism_related(source_mech, cand_mech)
        target_rel = bool(set(source.get("targets") or []) & set(row.get("targets") or []))

        structured_rel = False
        if atc_related:
            why.append("Closely related DrugBank ATC class")
            structured_rel = True
        if class_related:
            why.append("Related DrugBank therapeutic class")
            structured_rel = True
        if mech_rel:
            why.append("Related mechanism of action")
            structured_rel = True
        if target_rel:
            why.append("Shared target or pathway")
            structured_rel = True

        # Must have indication relationship AND one structured relationship
        indication_ok = has_indication or spl_hit
        if not indication_ok or not structured_rel:
            continue

        candidates.append(
            {
                "candidate_drug_id": row["drugbank_id"],
                "candidate_name": row["generic_name"],
                "active_ingredient": row["generic_name"],
                "classification": "therapeutic_alternative",
                "why_retrieved": why,
                "indication_relationship": {
                    "source_condition": indication["condition"],
                    "candidate_indications": row.get("indications", []),
                    "overlap": True,
                    "source_section": "indications",
                },
                "class_relationship": {
                    "source_class": source.get("drug_class"),
                    "candidate_class": row.get("drug_class"),
                    "source_atc": source.get("atc_classification"),
                    "candidate_atc": row.get("atc_classification"),
                    "related": atc_related or class_related,
                },
                "mechanism_relationship": {
                    "source": source_mech,
                    "candidate": cand_mech,
                    "related": mech_rel,
                },
                "target_relationship": {
                    "shared_targets": sorted(set(source.get("targets") or []) & set(row.get("targets") or [])),
                    "related": target_rel,
                },
                "record": row,
                "spl": next(
                    (get_spl(sid) for sid in row.get("linked_reference_ids", []) if get_spl(sid)),
                    None,
                ),
                "data_source": "demo_seed",
                "provenance_label": "DEMO DATA",
            }
        )
    return candidates
