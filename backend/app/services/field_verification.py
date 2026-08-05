"""Field-by-field pharmacist verification (HITL cascade).

Workflow:
1. OCR extracts prescription text and populates AI field values.
2. Drug dropdown shows only similar matches from verified FDA/DrugBank catalog.
3. After drug is confirmed, route options come from that drug’s catalog routes.
4. After route is confirmed, strength options are filtered to that route.
5. After strength is confirmed, dosage options come from drug + route + strength.
6. Frequency follows dose + route.
7. Verified indication is OPTIONAL but, when shown, is dataset-only (FDA/DrugBank/SPL).

Confirm requires: drug + route + strength + dose + frequency (indication not required).
Decision-support prototype only — not clinical care.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.prescription import OcrJob, PrescriptionMedicine
from app.core.config import settings
from app.services import prescription_service
from app.services.formulary_catalog import (
    FORMULARY_DRUGS,
    catalog_display_name,
    find_by_canonical,
    normalize,
    resolve_drug,
    suggest_drugs,
    value_in_list,
)
from app.services.hitl_audit import record_hitl_event
from app.services.catalog_sig_options import (
    build_cascade_options,
    catalog_sources_list,
    routes_for_drug,
)
from app.services.therapeutic.seed_data import indication_options_for_drug
from sqlalchemy import select


def _latest_ocr_job(db: Session, session_id: str) -> OcrJob | None:
    return db.scalars(
        select(OcrJob)
        .where(OcrJob.session_id == session_id)
        .order_by(OcrJob.created_at.desc())
    ).first()


def session_ocr_is_mock(db: Session, session_id: str) -> bool:
    job = _latest_ocr_job(db, session_id)
    return bool(job and job.is_mock)


def _assert_confirm_allowed_for_ocr(db: Session, session_id: str) -> None:
    """Block Confirm when the session OCR is labelled mock unless explicitly allowed."""
    if settings.HITL_ALLOW_MOCK_CONFIRM:
        return
    if session_ocr_is_mock(db, session_id):
        raise HTTPException(
            status_code=422,
            detail=(
                "Cannot confirm medicines from MOCK OCR. Configure Google Vision credentials "
                "for a real extraction, or set HITL_ALLOW_MOCK_CONFIRM=true only for labelled demos."
            ),
        )


# Cascade: Drug → Route → Strength → Dosage → Frequency (indication optional)
FIELD_ORDER = ("drug", "route", "strength", "dose", "frequency", "indication")
REQUIRED_FOR_CONFIRM = ("drug", "route", "strength", "dose", "frequency")

# Never accepted as catalog HITL values (required fields cannot Confirm with these)
_FORBIDDEN_PLACEHOLDERS = frozenset(
    {
        "unknown",
        "n/a",
        "na",
        "n.a.",
        "none",
        "null",
        "not known",
        "not known.",
        "unspecified",
        "not specified",
        "unable to verify",
        "tbd",
        "?",
        "-",
        "--",
    }
)


def _is_forbidden_placeholder(value: str | None) -> bool:
    if value is None:
        return False
    key = " ".join(str(value).strip().lower().split())
    return key in _FORBIDDEN_PLACEHOLDERS


def _filter_option_labels(options: list) -> list:
    """Drop Unknown/N/A-style placeholders from catalog dropdowns."""
    out: list = []
    for opt in options or []:
        if isinstance(opt, dict):
            label = opt.get("value") or opt.get("label") or opt.get("canonical_name")
            if _is_forbidden_placeholder(label):
                continue
            out.append(opt)
        else:
            if _is_forbidden_placeholder(str(opt)):
                continue
            out.append(opt)
    return out


def _reject_if_placeholder(field: str, value: str) -> None:
    if _is_forbidden_placeholder(value):
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{value}' is not a catalog value for {field}. "
                "Required fields must be chosen from FDA_NDC / DrugBank / FDA_SPL options, "
                "or mark the row Unable to verify."
            ),
        )


def _indication_options_catalog(canonical_name: str) -> list[dict]:
    """Prefer indexed indication_options; fall back to live miner for older DBs.

    Seed formulary indications are only used when the catalog DB is absent.
    """
    opts: list[dict] = []
    catalog_db = False
    try:
        from app.services.datasets.catalog_store import catalog_available

        catalog_db = bool(catalog_available())
    except Exception:  # noqa: BLE001
        catalog_db = False
    try:
        from app.services.datasets.hitl_catalog_query import query_indications

        indexed, src = query_indications(canonical_name)
        if indexed:
            for o in indexed:
                opts.append(
                    {
                        "value": o["value"],
                        "sources": [o.get("source") or "FDA_SPL"],
                        "evidence_excerpt": o.get("evidence_excerpt"),
                        "option_source": src,
                    }
                )
    except Exception:  # noqa: BLE001
        opts = []
    if not opts:
        try:
            from app.services.datasets.indication_options import catalog_indication_options

            opts = catalog_indication_options(canonical_name) or []
        except Exception:  # noqa: BLE001
            opts = []
    # Seed invents options — never when a catalog DB is mounted.
    if not opts and not catalog_db:
        opts = indication_options_for_drug(canonical_name) or []
    # Normalize to {value, sources} shape used by UI
    normalized: list[dict] = []
    for o in opts:
        if isinstance(o, dict):
            val = o.get("value") or o.get("label")
            if not val or _is_forbidden_placeholder(val):
                continue
            sources = o.get("sources") or ["FDA_NDC", "DrugBank", "FDA_SPL"]
            normalized.append({"value": val, "sources": list(sources)})
        else:
            if _is_forbidden_placeholder(str(o)):
                continue
            normalized.append({"value": str(o), "sources": ["FDA_NDC", "DrugBank", "FDA_SPL"]})
    # de-dupe
    seen: set[str] = set()
    out: list[dict] = []
    for o in normalized:
        key = normalize(o["value"])
        if key in seen:
            continue
        seen.add(key)
        out.append(o)
    return out

def _evidence_panel(canonical_name: str | None) -> dict | None:
    """Evidence hover: FDA_NDC / DrugBank / FDA_SPL catalog only (no synthetic seed)."""
    if not canonical_name:
        return None
    try:
        from app.services.datasets.catalog_store import get_medicine_by_canonical
        from app.services.datasets.match import suggest_medicines
    except Exception:  # noqa: BLE001
        return None

    rec = get_medicine_by_canonical(canonical_name)
    if rec is None:
        hits = suggest_medicines(canonical_name, top_k=3)
        if hits:
            rec = get_medicine_by_canonical(hits[0].canonical_name)

    if rec is None:
        return {
            "drug_name": canonical_name,
            "therapeutic_class": "Catalog identity match",
            "why_used": (
                "No DrugBank/FDA indication narrative is stored for this catalog row yet. "
                "Confirm identity from FDA_NDC / DrugBank / FDA_SPL match lists only."
            ),
            "limitations": (
                "Use verified catalog fields (strength, form, route) and pharmacist clinical judgment."
            ),
            "citations": [],
            "knowledge_mode": "catalog_identity_only",
            "provenance_label": "FDA_NDC + DrugBank + FDA_SPL catalog",
            "catalog_sources": [],
            "routes": [],
            "dosage_forms": [],
            "strengths_sample": [],
            "label_sections": {},
        }

    from app.services.datasets.catalog_store import list_label_sections

    sections = list_label_sections(rec.id)
    sources = list(rec.sources or [])
    indication = (sections.get("indications_and_usage") or rec.indication or "").strip()
    why = indication
    if why:
        why = re.sub(
            r"^(?:\d+\s+)?indications?(?:\s+and\s+usage)?\s*:?\s*",
            "",
            why,
            flags=re.I,
        ).strip()
        if len(why) > 420:
            why = why[:420].rstrip() + "…"
    else:
        why = (
            "Catalog product identity from "
            + (" + ".join(sources) if sources else "FDA_NDC / DrugBank / FDA_SPL")
            + ". No indication narrative on this row — select a verified indication later if needed."
        )

    citations = []
    if rec.drugbank_id:
        citations.append(
            {
                "source": "DrugBank",
                "source_id": rec.drugbank_id,
                "title": f"{rec.canonical_name} ({rec.drugbank_id})",
                "url": f"https://go.drugbank.com/drugs/{rec.drugbank_id}",
                "excerpt": "DrugBank identifier linked from local catalog index.",
            }
        )
    if rec.product_ndc:
        citations.append(
            {
                "source": "FDA_NDC",
                "source_id": rec.product_ndc,
                "title": f"NDC {rec.product_ndc}",
                "url": "https://www.accessdata.fda.gov/scripts/cder/ndc/",
                "excerpt": "FDA NDC product identifier from local catalog index.",
            }
        )
    if rec.spl_set_id or "FDA_SPL" in sources or any("SPL" in s.upper() for s in sources):
        citations.append(
            {
                "source": "FDA_SPL",
                "source_id": rec.spl_set_id or rec.canonical_name,
                "title": f"{rec.canonical_name} — SPL catalog sections",
                "url": "https://labels.fda.gov/",
                "excerpt": (indication[:220] + "…")
                if indication and len(indication) > 220
                else (indication or "SPL source flagged on catalog row."),
            }
        )

    return {
        "drug_name": rec.canonical_name,
        "therapeutic_class": "Catalog product (FDA_NDC / DrugBank / FDA_SPL)",
        "why_used": why,
        "limitations": (
            "Local catalog excerpt from ingested FDA_NDC / DrugBank / FDA_SPL files — "
            "not a live API call and not a substitute for the full label. "
            "Pharmacist must confirm before any clinical decision."
        ),
        "citations": citations,
        "knowledge_mode": "catalog_full_diligence",
        "provenance_label": " + ".join(sources) if sources else "FDA_NDC + DrugBank + FDA_SPL catalog",
        "catalog_sources": sources,
        "routes": list(rec.routes or [])[:8],
        "dosage_forms": list(rec.dosage_forms or [])[:8],
        "strengths_sample": list(rec.strengths or [])[:8],
        "label_sections": {
            k: sections[k][:400] + ("…" if len(sections[k]) > 400 else "")
            for k in (
                "dosage_and_administration",
                "contraindications",
                "warnings_and_cautions",
                "drug_interactions",
            )
            if k in sections
        },
    }


def _high_confidence_ocr_drug_correction(ocr_name: str | None) -> str | None:
    """Map unambiguous OCR misspellings (e.g. Cetrizine) to catalog canonical for HITL.

    Production rule: only when abbrev/alias normalize differs from raw OCR and catalog
    returns a near-exact hit. Keeps ai_* as OCR for analytics; pharmacist still Confirms.
    """
    if not ocr_name or not str(ocr_name).strip():
        return None
    try:
        from app.services.datasets.match import normalize_query, suggest_medicines
    except Exception:  # noqa: BLE001
        return None
    raw = str(ocr_name).strip()
    mapped = normalize_query(raw)
    token = re.split(r"\d", raw, maxsplit=1)[0].strip(" .")
    # Require an actual abbrev/misspelling remap (not identity)
    if not mapped or normalize(mapped) == normalize(token):
        return None
    hits = suggest_medicines(raw, top_k=1, min_score=95.0)
    if not hits or hits[0].score < 95.0:
        return None
    canon = hits[0].canonical_name
    if normalize(canon) == normalize(raw):
        return None
    return _catalog_display_name(canon) or canon


def _prefer_ocr_option_first(ocr_value: str | None, options: list[str]) -> list[str]:
    """Rank catalog options so the OCR/Rx frequency (or dose) appears first when present."""
    if not options:
        return options
    matched = _canon_option(ocr_value, options)
    if not matched:
        return options
    rest = [o for o in options if normalize(o) != normalize(matched)]
    return [matched, *rest]


def _catalog_display_name(name: str | None) -> str | None:
    """HITL wrapper — Title Case drug names (see formulary_catalog.catalog_display_name)."""
    return catalog_display_name(name)


def _effective(medicine: PrescriptionMedicine) -> dict[str, str | None]:
    # Keep OCR spelling in the drug field until pharmacist applies a catalog pick / Confirm.
    # High-confidence corrections are surfaced as suggested options, not auto-greens.
    drug = medicine.pharmacist_medicine_name or medicine.ai_medicine_name
    return {
        "drug": drug,
        "strength": medicine.pharmacist_strength or medicine.ai_strength,
        "dose": medicine.pharmacist_dose or medicine.ai_dose,
        "frequency": medicine.pharmacist_frequency or medicine.ai_frequency,
        "form": medicine.pharmacist_form or medicine.ai_form,
        "route": medicine.pharmacist_route or medicine.ai_route,
        "indication": medicine.pharmacist_verified_indication,
    }


def _canon_option(value: str | None, options: list[str] | tuple[str, ...] | None) -> str | None:
    """Return dataset spelling if value matches an option (case/space insensitive)."""
    if not value or not options:
        return None
    key = normalize(value)
    for opt in options:
        if normalize(opt) == key:
            return opt
    # Catalog often stores "500 mg/1" — accept OCR "500 mg" as the same strength
    for opt in options:
        nopt = normalize(opt)
        if key and (nopt.startswith(key + " ") or nopt.startswith(key + "/") or f" {key} " in f" {nopt} "):
            return opt
    # OCR SIG aliases → catalog frequency / dose labels
    aliases = {
        "up to three times daily": "three times daily",
        "up to 3 times daily": "three times daily",
        "3 times daily": "three times daily",
        "3x daily": "three times daily",
        "3 x daily": "three times daily",
        "tid": "three times daily",
        "tds": "three times daily",
        "thrice daily": "three times daily",
        "thrice a day": "three times daily",
        "8 hourly": "three times daily",
        "every 8 hours": "three times daily",
        "bd": "twice daily",
        "bid": "twice daily",
        "12 hourly": "twice daily",
        "every 12 hours": "twice daily",
        "qid": "four times daily",
        "qds": "four times daily",
        "6 hourly": "four times daily",
        "every 6 hours": "four times daily",
        "od": "once daily",
        "qd": "once daily",
        "as required": "when required",
        "as needed": "when required",
        "prn": "when required",
        "after food": "after meal",
        "after meals": "after meal",
        "before food": "before meal",
        "before meals": "before meal",
        "1 capsule": "one capsule",
        "1 tablet": "one tablet",
        "2 capsules": "two capsules",
        "2 tablets": "two tablets",
        "2 puffs": "two puffs",
    }
    mapped = aliases.get(key)
    if mapped:
        for opt in options:
            if normalize(opt) == mapped or mapped in normalize(opt):
                return opt
    return None


def _strength_from_ocr(ocr_strength: str | None, options: list[str] | tuple[str, ...] | None) -> str | None:
    """Map OCR strength to a catalog option (exact or N× unit strength)."""
    from app.services.catalog_field_match import catalog_strength_from_ocr

    return catalog_strength_from_ocr(ocr_strength, options)


def _prefer_dose_for_ocr_total(
    ocr_strength: str | None,
    strength_canon: str | None,
    doses: list[str],
) -> str | None:
    """When OCR total = N × catalog unit, prefer N tablets/capsules from catalog doses."""
    from app.services.catalog_field_match import catalog_dose_from_ocr_total

    return catalog_dose_from_ocr_total(ocr_strength, strength_canon, doses)


def _seed_entry(name: str | None) -> dict[str, Any] | None:
    drug = find_by_canonical(name) or resolve_drug(name)
    if drug is None:
        return None
    exact = find_by_canonical(name) is not None
    return {
        "formulary_id": drug.formulary_id,
        "canonical_name": drug.canonical_name,
        "strengths": list(drug.strengths),
        "doses": list(drug.doses),
        "frequencies": list(drug.frequencies),
        "forms": list(drug.forms),
        "routes": list(drug.routes),
        "source": "seed",
        "exact_canonical": exact,
    }


def _pick_best_catalog_hit(hits: list, query: str):
    """Prefer catalog rows with usable product data and strong alias quality.

    Generic ranking only — no brand-specific branches. Thin SPL shells (no
    strengths) lose to richer NDC/DrugBank product rows; multi-ingredient
    richness is a generic signal when the alias/name match quality is equal.
    """
    if not hits:
        return None
    key = normalize(query)

    def rank(h) -> tuple:
        name = normalize(h.canonical_name)
        alias = normalize(getattr(h, "matched_alias", None) or "")
        exact_name = name == key
        alias_hit = bool(alias) and (alias == key)
        alias_quality = 2 if exact_name else (1 if alias_hit else 0)
        has_strengths = 1 if (h.strengths or []) else 0
        has_forms = 1 if (h.dosage_forms or []) else 0
        has_routes = 1 if (h.routes or []) else 0
        product_richness = has_strengths * 4 + has_forms * 2 + has_routes
        # Multi-ingredient / combo rows often carry the usable NDC product set
        if " and " in name or "/" in name:
            product_richness += 2
        src = (h.source or "").upper()
        ndc_bonus = 1 if "NDC" in src else 0
        spl_only_penalty = -1 if ("SPL" in src and not has_strengths) else 0
        return (
            -(product_richness + ndc_bonus + spl_only_penalty),
            -alias_quality,
            -float(h.score or 0),
            len(name),
        )

    return sorted(hits, key=rank)[0]


def _catalog_entry(name: str | None) -> dict[str, Any] | None:
    if not name or not name.strip():
        return None
    try:
        from app.services.datasets.catalog_store import catalog_available
        from app.services.datasets.match import suggest_medicines
    except Exception:  # noqa: BLE001
        return None
    if not catalog_available():
        return None
    hits = suggest_medicines(name, top_k=8)
    if not hits:
        return None
    key = normalize(name)
    exact_hit = next((h for h in hits if normalize(h.canonical_name) == key), None)
    # Prefer an exact canonical-name hit so selecting "Ibuprofen" does not collapse to "Ibu"
    if exact_hit is not None:
        best = exact_hit
        exact = True
        # Thin brand/ingredient shell: pull strengths/forms from a richer sibling hit
        if not (exact_hit.strengths or exact_hit.dosage_forms):
            richer = _pick_best_catalog_hit(hits, name)
            if richer is not None and (richer.strengths or richer.dosage_forms):
                best = richer
                # Keep displayed exactness against the query spelling; options come from richer row
                exact = True
    else:
        best = _pick_best_catalog_hit(hits, name)
        if best is None:
            return None
        exact = False

    strengths = list(best.strengths or [])
    # When we promoted a richer sibling, still expose the exact query spelling as canonical for HITL
    canonical_name = exact_hit.canonical_name if exact_hit is not None else best.canonical_name
    seed = next(
        (d for d in FORMULARY_DRUGS if normalize(d.canonical_name) == normalize(canonical_name)),
        None,
    )
    if seed and seed.strengths:
        merged: list[str] = []
        for s in list(seed.strengths) + strengths:
            if s not in merged:
                merged.append(s)
        strengths = merged
    return {
        "formulary_id": best.drugbank_id or best.product_ndc or canonical_name,
        "canonical_name": canonical_name,
        "strengths": strengths,
        "doses": list(seed.doses) if seed else [],
        "frequencies": list(seed.frequencies) if seed else [],
        "forms": list(best.dosage_forms or []) or (list(seed.forms) if seed else []),
        "routes": list(best.routes or []) or (list(seed.routes) if seed else []),
        "source": best.source if exact_hit is None else (exact_hit.source or best.source),
        "exact_canonical": exact,
        "score": best.score if exact_hit is None else exact_hit.score,
        "indication": None,
    }


def resolve_hitl_drug(name: str | None) -> dict[str, Any] | None:
    """Resolve drug dataset for HITL dropdowns (catalog preferred, seed fallback).

    exact_canonical is True only when the *current displayed value* equals the catalog
    canonical spelling. Fuzzy OCR (e.g. Ibrufen → Ibu/Ibuprofen) stays red until the
    pharmacist picks a catalog option — never auto-green from product metadata alone.
    """
    if not name or not str(name).strip():
        return None
    catalog = _catalog_entry(name)
    seed = _seed_entry(name)
    if catalog:
        name_key = normalize(name)
        canon_key = normalize(catalog["canonical_name"])
        catalog["exact_canonical"] = name_key == canon_key
        if catalog["exact_canonical"]:
            if seed and seed.get("exact_canonical") and normalize(seed["canonical_name"]) == canon_key:
                catalog["doses"] = seed["doses"] or catalog["doses"]
                catalog["frequencies"] = seed["frequencies"] or catalog["frequencies"]
            from app.services.catalog_sig_options import enrich_entry_forms_routes

            return enrich_entry_forms_routes(catalog)
        # Fuzzy catalog hit: keep options/evidence available but do not unlock cascade
        from app.services.catalog_sig_options import enrich_entry_forms_routes

        return enrich_entry_forms_routes(catalog)
    if seed and seed.get("exact_canonical"):
        return seed
    return seed


def _filter_strength_options(strengths: list[str], ocr_strength: str | None) -> list[str]:
    """Keep FDA/DrugBank strengths that look like clinical strengths; prefer OCR match."""
    usable: list[str] = []
    for s in strengths:
        if not s or not re.search(r"\d", s):
            continue
        if not re.search(r"\b(?:mg|g|mcg|microgram|%)\b", s, re.I):
            continue
        # Drop densitiy-style noise when better options exist
        if re.search(r"kg/kg|g/g|mL/1mL|mg/\d+mg|1\s*kg", s, re.I):
            continue
        # Prefer tablet-friendly labels over infusion/powder reconstitutions
        if re.search(r"\b(?:/mL|per\s*mL|infusion|inject|vial|powder|/100\s*mL)\b", s, re.I):
            continue
        usable.append(s)
    if not usable:
        usable = [s for s in strengths if s and re.search(r"\d+\s*mg\b", s, re.I)][:24]
    # Prefer compact oral clinical strengths (e.g. "500 mg") before long product strings
    def _strength_rank(x: str) -> tuple:
        xl = x.lower()
        solidish = 0 if re.fullmatch(r"\d+(?:\.\d+)?\s*(?:mg|mcg|g|%)", xl) else 1
        return (solidish, len(x), xl)

    usable.sort(key=_strength_rank)
    # Promote catalog unit strengths that explain OCR as N× unit (any drug)
    if ocr_strength:
        from app.services.catalog_field_match import prefer_unit_strengths_for_ocr

        usable = prefer_unit_strengths_for_ocr(ocr_strength, usable)
        hit = _canon_option(ocr_strength, usable) or _canon_option(ocr_strength, strengths)
        # Don't promote IV/ratio rows from a bare solid OCR (e.g. 1000 mg → 1000 mg/100mL)
        if hit and "/" in hit and "/" not in (ocr_strength or ""):
            hit = None
        if hit and hit not in usable:
            usable.insert(0, hit)
        elif ocr_strength not in usable and _canon_option(ocr_strength, strengths):
            raw = _canon_option(ocr_strength, strengths) or ocr_strength
            if "/" not in raw or "/" in (ocr_strength or ""):
                usable.insert(0, raw)
    # de-dupe
    out: list[str] = []
    for s in usable:
        if s not in out:
            out.append(s)
    return out[:30]


def _similar_drug_options(ocr_name: str | None, current: str | None) -> list[dict]:
    """Drug dropdown: similar FDA/DrugBank catalog matches only (no free-text invent)."""
    query = (ocr_name or current or "").strip()
    options = suggest_drugs(query, limit=12) if query else []
    # Keep only similar / suggested catalog hits
    filtered = [
        o
        for o in options
        if o.get("suggested") or (o.get("match_score") or 0) >= 0.55 or o.get("source")
    ]
    # Annotate verified-source reason
    for o in filtered:
        src = o.get("source") or "FDA_NDC+DrugBank"
        o["match_reason"] = o.get("match_reason") or f"Similar match from verified source ({src})"
        o["suggested"] = True
    # Surface high-confidence OCR→catalog remaps at top (do not auto-green the OCR value).
    corrected = _high_confidence_ocr_drug_correction(ocr_name)
    if corrected:
        for i, o in enumerate(filtered):
            if normalize(o.get("canonical_name")) == normalize(corrected):
                filtered.insert(0, filtered.pop(i))
                break
        else:
            tip_c = resolve_hitl_drug(corrected)
            if tip_c and tip_c.get("exact_canonical"):
                filtered.insert(
                    0,
                    {
                        "formulary_id": tip_c["formulary_id"],
                        "canonical_name": tip_c["canonical_name"],
                        "match_score": 1.0,
                        "match_reason": "High-confidence OCR spelling → catalog",
                        "suggested": True,
                        "strengths": tip_c.get("strengths") or [],
                        "doses": tip_c.get("doses") or [],
                        "frequencies": tip_c.get("frequencies") or [],
                        "forms": tip_c.get("forms") or [],
                        "routes": tip_c.get("routes") or [],
                        "source": tip_c.get("source") or "catalog",
                    },
                )
    if current and not any(normalize(o.get("canonical_name")) == normalize(current) for o in filtered):
        tip = resolve_hitl_drug(current)
        if tip and tip.get("exact_canonical"):
            filtered.insert(
                0,
                {
                    "formulary_id": tip["formulary_id"],
                    "canonical_name": tip["canonical_name"],
                    "match_score": 1.0,
                    "match_reason": "Selected verified catalog drug",
                    "suggested": True,
                    "strengths": tip["strengths"],
                    "doses": tip["doses"],
                    "frequencies": tip["frequencies"],
                    "forms": tip["forms"],
                    "routes": tip["routes"],
                    "source": tip.get("source") or "catalog",
                },
            )
        elif current:
            tip2 = resolve_hitl_drug(current)
            if tip2 and tip2.get("exact_canonical"):
                filtered.insert(
                    0,
                    {
                        "formulary_id": tip2["formulary_id"],
                        "canonical_name": tip2["canonical_name"],
                        "match_score": 1.0,
                        "match_reason": "Current verified catalog drug",
                        "suggested": True,
                        "strengths": tip2["strengths"],
                        "doses": tip2["doses"],
                        "frequencies": tip2["frequencies"],
                        "forms": tip2["forms"],
                        "routes": tip2["routes"],
                        "source": tip2.get("source") or "catalog",
                    },
                )
            # OCR misspellings are NOT inserted as selectable options (apply would 422)
    return filtered[:15]


def build_field_state(medicine: PrescriptionMedicine) -> dict:
    eff = _effective(medicine)
    entry = resolve_hitl_drug(eff["drug"])
    drug_ok = bool(entry and entry.get("exact_canonical"))

    strengths_raw = list(entry["strengths"]) if entry else []
    doses_raw = list(entry["doses"]) if entry else []
    frequencies = list(entry["frequencies"]) if entry else []

    if drug_ok and entry and not strengths_raw:
        seed = find_by_canonical(entry["canonical_name"])
        if seed:
            strengths_raw = list(seed.strengths)
            if not doses_raw:
                doses_raw = list(seed.doses)
            if not frequencies:
                frequencies = list(seed.frequencies)

    forms = list((entry or {}).get("forms") or [])
    catalog_routes = list((entry or {}).get("routes") or [])
    products = list((entry or {}).get("products") or [])
    seed_doses = list(doses_raw)
    seed_freqs = list(frequencies)
    catalog_sources = catalog_sources_list((entry or {}).get("source"))

    # Resolve currently matched prior fields (must be dataset-canonical)
    route_options_preview: list[str] = []
    catalog_db_for_routes = False
    if drug_ok:
        try:
            from app.services.datasets.catalog_store import catalog_available
            from app.services.datasets.hitl_catalog_query import query_routes

            catalog_db_for_routes = bool(catalog_available())
            if catalog_db_for_routes and entry.get("canonical_name"):
                r_meta, _ = query_routes(entry.get("canonical_name"))
                route_options_preview = [o["value"] for o in r_meta]
        except Exception:  # noqa: BLE001
            route_options_preview = []
        # With catalog DB: products.route only — no form-inferred invention.
        if not route_options_preview and not catalog_db_for_routes:
            route_options_preview = routes_for_drug(
                catalog_routes,
                forms=forms,
                ocr_route=eff["route"] or medicine.ai_route,
            )
    route_canon = None
    if drug_ok:
        from app.services.catalog_field_match import (
            catalog_route_from_context,
            catalog_route_suggestions,
        )

        # Prefer pharmacist-applied route when present; else strict OCR/single-route resolve.
        # Form/dose cues may rank suggestions but never auto-green multi-route ambiguity.
        pharmacist_route = (medicine.pharmacist_route or "").strip() or None
        route_canon = catalog_route_from_context(
            route_options_preview,
            ocr_route=pharmacist_route or eff["route"] or medicine.ai_route,
            catalog_forms=forms,
            ocr_form=eff.get("form") or medicine.ai_form,
            ocr_dose=eff.get("dose") or medicine.ai_dose,
        )
        if pharmacist_route and not route_canon:
            # Explicit pharmacist pick must still be a catalog option
            from app.services.formulary_catalog import normalize as _n

            for opt in route_options_preview:
                if _n(opt) == _n(pharmacist_route):
                    route_canon = opt
                    break
        suggested_routes = catalog_route_suggestions(
            route_options_preview,
            ocr_route=eff["route"] or medicine.ai_route,
            catalog_forms=forms,
            ocr_form=eff.get("form") or medicine.ai_form,
            ocr_dose=eff.get("dose") or medicine.ai_dose,
        )
        if suggested_routes:
            route_options_preview = suggested_routes
    route_ok = bool(route_canon)

    clinical = _filter_strength_options(strengths_raw, eff["strength"]) if drug_ok else []

    # Dynamic catalog options: cascade intersections only (strict when catalog DB present).
    # Resolve strength against route-scoped options before requesting dose/frequency.
    cascade = build_cascade_options(
        drug_matched=drug_ok,
        catalog_forms=forms,
        catalog_routes=catalog_routes,
        catalog_strengths=clinical,
        seed_doses=seed_doses,
        seed_frequencies=seed_freqs,
        matched_route=route_canon if route_ok else None,
        matched_strength=None,
        matched_dose=None,
        ocr_route=eff["route"] or medicine.ai_route,
        ocr_strength=eff["strength"],
        catalog_source=(entry or {}).get("source"),
        products=products,
        canonical_name=(entry or {}).get("canonical_name"),
    )

    route_options = list(cascade["route"]["options"])
    strengths = list(cascade["strength"]["options"]) if route_ok else []
    strength_canon = _strength_from_ocr(eff["strength"], strengths) if route_ok else None
    strength_ok = bool(route_ok and strength_canon)

    doses: list[str] = []
    dose_source = cascade["dose"]["option_source"]
    dose_canon = None
    if strength_ok:
        cascade = build_cascade_options(
            drug_matched=drug_ok,
            catalog_forms=forms,
            catalog_routes=catalog_routes,
            catalog_strengths=clinical,
            seed_doses=seed_doses,
            seed_frequencies=seed_freqs,
            matched_route=route_canon,
            matched_strength=strength_canon,
            matched_dose=None,
            ocr_route=eff["route"] or medicine.ai_route,
            ocr_strength=eff["strength"],
            catalog_source=(entry or {}).get("source"),
            products=products,
            canonical_name=(entry or {}).get("canonical_name"),
        )
        doses = list(cascade["dose"]["options"])
        dose_source = cascade["dose"]["option_source"]
        dose_canon = _canon_option(eff["dose"], doses)
        if not dose_canon:
            dose_canon = _prefer_dose_for_ocr_total(eff["strength"], strength_canon, doses)
    dose_ok = bool(strength_ok and dose_canon)

    if dose_ok:
        cascade = build_cascade_options(
            drug_matched=drug_ok,
            catalog_forms=forms,
            catalog_routes=catalog_routes,
            catalog_strengths=clinical,
            seed_doses=seed_doses,
            seed_frequencies=seed_freqs,
            matched_route=route_canon,
            matched_strength=strength_canon,
            matched_dose=dose_canon,
            ocr_route=eff["route"] or medicine.ai_route,
            ocr_strength=eff["strength"],
            catalog_source=(entry or {}).get("source"),
            products=products,
            canonical_name=(entry or {}).get("canonical_name"),
        )
        doses = list(cascade["dose"]["options"])
        dose_source = cascade["dose"]["option_source"]
        frequencies = list(cascade["frequency"]["options"])
        freq_source = cascade["frequency"]["option_source"]
    else:
        frequencies = []
        freq_source = cascade["frequency"]["option_source"]

    freq_canon = _canon_option(eff["frequency"] or medicine.ai_frequency, frequencies) if dose_ok else None
    frequency_ok = bool(dose_ok and freq_canon)

    indication_opts: list[dict] = []
    # Indication dropdown only after required cascade is fully catalog-matched
    if drug_ok and entry and frequency_ok:
        indication_opts = _indication_options_catalog(entry["canonical_name"])
    indication_values = [o["value"] for o in indication_opts]
    indication_selected = bool(
        frequency_ok and value_in_list(eff["indication"], indication_values)
    )
    if not drug_ok:
        indication_status = "red"
        indication_locked = True
        indication_msg = (
            "Confirm catalog drug first — indication is optional and comes from "
            "FDA_NDC / DrugBank / FDA_SPL after required fields match."
        )
    elif not frequency_ok:
        indication_status = "red"
        indication_locked = True
        indication_msg = (
            "Locked until drug, route, strength, dosage, and frequency are catalog-matched. "
            "Indication is optional."
        )
    elif not eff["indication"]:
        indication_status = "green"
        indication_locked = False
        indication_msg = (
            "Optional for Confirm — choose a catalog indication (FDA_NDC / DrugBank / FDA_SPL), "
            "or leave blank. Therapeutic alternatives later may require an indication. "
            "Confirm validates drug identity only (not a patient record)."
        )
    elif indication_selected:
        indication_status = "green"
        indication_locked = False
        indication_msg = None
    else:
        indication_status = "red"
        indication_locked = False
        indication_msg = (
            "Indication must be blank or chosen from the catalog dropdown (no free text / Unknown)."
        )

    drug_options = _filter_option_labels(
        _similar_drug_options(medicine.ai_medicine_name, eff["drug"])
    )
    for opt in drug_options:
        if isinstance(opt, dict) and opt.get("canonical_name"):
            opt["canonical_name"] = _catalog_display_name(opt["canonical_name"]) or opt["canonical_name"]
    route_options = _filter_option_labels(route_options)
    strengths = _filter_option_labels(strengths)
    doses = _filter_option_labels(doses)
    frequencies = _filter_option_labels(frequencies)
    # Prefer Rx/OCR SIG at top of dropdowns (SPL often lists alternate tablet counts / QID).
    doses = _prefer_ocr_option_first(medicine.ai_dose, doses)
    frequencies = _prefer_ocr_option_first(medicine.ai_frequency, frequencies)

    display_drug = _catalog_display_name(
        entry["canonical_name"] if drug_ok and entry else eff["drug"]
    )

    fields = {
        "drug": {
            "value": display_drug,
            "ai_value": medicine.ai_medicine_name,
            "status": "green" if drug_ok else "red",
            "locked": False,
            "options": drug_options,
            "evidence_tier": "Catalog (FDA/DrugBank/SPL)",
            "message": None
            if drug_ok
            else "OCR drug not matched — select a verified catalog drug (required before route).",
        },
        "route": {
            "value": route_canon or eff["route"],
            "ai_value": medicine.ai_route,
            "status": "green" if route_ok else "red",
            "locked": not drug_ok,
            "options": route_options,
            "option_source": cascade["route"]["option_source"],
            "catalog_sources": catalog_sources or cascade["route"]["catalog_sources"],
            "depends_on": cascade["route"]["depends_on"],
            "evidence_tier": "Catalog (FDA/DrugBank/SPL)",
            "options_context": {
                **cascade["route"]["context"],
                "catalog_sources": catalog_sources,
            },
            "message": (
                "Locked until drug name is matched (yellow)."
                if not drug_ok
                else (
                    None
                    if route_ok
                    else (
                        "No catalog routes/forms for this drug — use Unable to verify."
                        if not route_options
                        else "Select route from catalog — this filters available strengths."
                    )
                )
            ),
        },
        "strength": {
            "value": strength_canon or eff["strength"],
            "ai_value": medicine.ai_strength,
            "status": "green" if strength_ok else "red",
            "locked": not route_ok,
            "options": strengths,
            "option_source": cascade["strength"]["option_source"],
            "catalog_sources": catalog_sources or cascade["strength"]["catalog_sources"],
            "depends_on": cascade["strength"]["depends_on"],
            "evidence_tier": "Catalog (FDA/DrugBank/SPL)",
            "options_context": {
                **(cascade["strength"]["context"] if route_ok else {}),
                "catalog_sources": catalog_sources,
            },
            "message": (
                "Locked until route is matched (yellow)."
                if not route_ok
                else (
                    None
                    if strength_ok
                    else (
                        "No catalog strengths for this drug + route — use Unable to verify."
                        if not strengths
                        else "Select a strength valid for this drug + route (catalog)."
                    )
                )
            ),
        },
        "dose": {
            "value": dose_canon or eff["dose"],
            "ai_value": medicine.ai_dose,
            "status": "green" if dose_ok else "red",
            "locked": not strength_ok,
            "options": doses,
            "option_source": dose_source,
            "catalog_sources": catalog_sources or cascade["dose"]["catalog_sources"],
            "depends_on": cascade["dose"]["depends_on"],
            "options_context": {
                **(cascade["dose"]["context"] if strength_ok else {}),
                "catalog_sources": cascade["dose"].get("catalog_sources") or catalog_sources,
                "evidence": cascade["dose"].get("evidence") or [],
                "template_note": (
                    "Form/route templates (HITL_ALLOW_DOSE_TEMPLATES) — not FDA label SIG."
                    if str(dose_source).startswith("catalog") or dose_source == "seed_formulary"
                    else "FDA_SPL dosage_and_administration, scoped to drug → route → strength."
                ),
            },
            "message": (
                "Locked until drug + route + strength are matched (yellow)."
                if not strength_ok
                else (
                    None
                    if dose_ok
                    else (
                        "No SPL-extracted dose for this drug + route + strength — use Unable to verify."
                        if not doses
                        else (
                            "Select dosage from FDA_SPL evidence for this drug + route + strength."
                            if str(dose_source).startswith("FDA_SPL")
                            else "Select dosage (template fallback — enable only for demos)."
                        )
                    )
                )
            ),
            "evidence_tier": (
                "FDA_SPL SIG"
                if str(dose_source).startswith("FDA_SPL") and doses
                else (
                    "SIG template"
                    if doses and (
                        str(dose_source).startswith("catalog") or dose_source == "seed_formulary"
                    )
                    else "No SPL dose"
                )
            ),
        },
        "frequency": {
            "value": freq_canon or eff["frequency"],
            "ai_value": medicine.ai_frequency,
            "status": "green" if frequency_ok else "red",
            "locked": not dose_ok,
            "options": frequencies,
            "option_source": freq_source,
            "catalog_sources": catalog_sources or cascade["frequency"]["catalog_sources"],
            "depends_on": cascade["frequency"]["depends_on"],
            "options_context": {
                **(cascade["frequency"]["context"] if dose_ok else {}),
                "catalog_sources": cascade["frequency"].get("catalog_sources") or catalog_sources,
                "evidence": cascade["frequency"].get("evidence") or [],
                "template_note": (
                    "Form/route templates (HITL_ALLOW_FREQ_TEMPLATES) — not FDA label SIG."
                    if str(freq_source).startswith("catalog") or freq_source == "seed_formulary"
                    else (
                        "FDA_SPL dosage_and_administration, scoped to drug → route → strength → dose (near selected dose phrase)."
                        if "dose_adjacent" in str(freq_source)
                        else "FDA_SPL dosage_and_administration, scoped to drug → route → strength."
                    )
                ),
            },
            "message": (
                "Locked until drug + route + strength + dosage are matched (yellow)."
                if not dose_ok
                else (
                    None
                    if frequency_ok
                    else (
                        "No SPL-extracted frequency for this drug + route + strength — use Unable to verify."
                        if not frequencies
                        else (
                            "Select frequency from FDA_SPL evidence near the selected dosage."
                            if "dose_adjacent" in str(freq_source)
                            else (
                                "Select frequency from FDA_SPL evidence for this drug + route + strength."
                                if str(freq_source).startswith("FDA_SPL")
                                else "Select frequency (template fallback — enable only for demos)."
                            )
                        )
                    )
                )
            ),
            "evidence_tier": (
                "FDA_SPL SIG · dose-adjacent"
                if "dose_adjacent" in str(freq_source) and frequencies
                else (
                    "FDA_SPL SIG"
                    if str(freq_source).startswith("FDA_SPL") and frequencies
                    else (
                        "SIG template"
                        if frequencies
                        and (
                            str(freq_source).startswith("catalog")
                            or freq_source == "seed_formulary"
                        )
                        else "No SPL frequency"
                    )
                )
            ),
        },
        "indication": {
            "value": eff["indication"],
            "ai_value": None,
            "status": indication_status,
            "locked": indication_locked,
            "options": indication_opts if frequency_ok else [],
            "optional": True,
            "catalog_sources": catalog_sources or ["FDA_NDC", "DrugBank", "FDA_SPL"],
            "depends_on": list(REQUIRED_FOR_CONFIRM),
            "message": indication_msg,
        },
    }

    # Placeholder values on required fields can never count as matched
    for req in REQUIRED_FOR_CONFIRM:
        if _is_forbidden_placeholder(fields[req].get("value")):
            fields[req]["status"] = "red"
            fields[req]["message"] = (
                (fields[req].get("message") or "")
                + " Unknown/N/A is not allowed — pick a catalog value or Unable to verify."
            ).strip()

    confirmed = medicine.pharmacist_status == "confirmed"
    for fname, f in fields.items():
        if confirmed:
            if fname != "indication":
                f["ui_tone"] = "locked"
        elif f.get("locked") and fname != "drug":
            f["ui_tone"] = "blocked"
        elif f["status"] == "green":
            f["ui_tone"] = "yellow"  # dataset match — HITL OK, awaiting row Confirm
        else:
            f["ui_tone"] = "amber"  # OCR present/mismatch — needs dropdown correction

    next_field = None
    for name in REQUIRED_FOR_CONFIRM:
        if fields[name]["status"] != "green":
            next_field = name
            break

    can_confirm = all(fields[name]["status"] == "green" for name in REQUIRED_FOR_CONFIRM)
    # If indication has an invalid free-text value, block confirm
    if fields["indication"]["status"] == "red" and eff["indication"]:
        can_confirm = False
        if next_field is None:
            next_field = "indication"

    # When the full catalog DB is available, template/seed SIG is never Confirm-eligible.
    # Options may still appear for demos when HITL_ALLOW_* is on, but Confirm stays closed.
    def _is_template_source(src: str | None) -> bool:
        s = str(src or "")
        return s in {
            "catalog_route_form_derived",
            "catalog_route_form_derived+seed",
            "seed_formulary",
        } or "template" in s.lower()

    catalog_db_ready = False
    try:
        from app.services.datasets.catalog_store import catalog_available

        catalog_db_ready = bool(catalog_available())
    except Exception:  # noqa: BLE001
        catalog_db_ready = False
    if catalog_db_ready and can_confirm:
        if _is_template_source(dose_source) or _is_template_source(freq_source):
            can_confirm = False
            confirm_hint_template = (
                "Confirm requires FDA_SPL / indexed catalog dose and frequency "
                "(not form/route templates or seed SIG) when the medicine catalog is available."
            )
            if fields["dose"]["status"] == "green" and _is_template_source(dose_source):
                fields["dose"]["message"] = (
                    (fields["dose"].get("message") or "")
                    + " Template/seed dose is not Confirm-eligible with full catalog — "
                    "use Unable to verify or wait for SPL evidence."
                ).strip()
                if next_field is None:
                    next_field = "dose"
            if fields["frequency"]["status"] == "green" and _is_template_source(freq_source):
                fields["frequency"]["message"] = (
                    (fields["frequency"].get("message") or "")
                    + " Template/seed frequency is not Confirm-eligible with full catalog."
                ).strip()
                if next_field is None:
                    next_field = "frequency"
        else:
            confirm_hint_template = None
    else:
        confirm_hint_template = None

    # Thin brand / empty product shell: identity matched but no strength-bearing products
    thin_brand_shell = bool(
        drug_ok
        and entry
        and not any(str(p.get("strength") or "").strip() for p in products)
        and not any(str(s or "").strip() for s in (clinical or strengths_raw or []))
    )
    if thin_brand_shell and medicine.pharmacist_status != "confirmed":
        can_confirm = False
        fields["drug"]["message"] = (
            (fields["drug"].get("message") or "")
            + " Thin catalog shell (no product strengths) — select a richer NDC/DrugBank "
            "canonical (e.g. ingredient combo) or use Unable to verify."
        ).strip()

    confirm_hint = None
    if not can_confirm and medicine.pharmacist_status != "confirmed":
        if thin_brand_shell:
            confirm_hint = (
                "Selected drug has no catalog strengths/products — pick a richer NDC canonical "
                "or use Unable to verify. Do not invent dose/frequency."
            )
        elif confirm_hint_template:
            confirm_hint = confirm_hint_template
        else:
            confirm_hint = (
                "Confirm requires catalog-matched Drug, Route, Strength, Dosage, and Frequency "
                "(FDA_NDC / DrugBank / FDA_SPL). Indication is optional for Confirm. "
                "If route/strength/dose/frequency options are empty, use Unable to verify — "
                "do not invent values."
            )

    # Evidence-only CDS: Confirm validates prescription drug identity — not a patient record.
    confirm_disclaimer = (
        "Confirm is for prescription drug validation against the trusted catalog "
        "(FDA_NDC / DrugBank / FDA_SPL). It is not a patient clinical record and does not "
        "capture allergy, age, pregnancy, or other patient-context data. "
        "Indication is optional here; therapeutic alternatives later may need an indication. "
        "Decision-support only — not a substitute for clinical judgment or full product labeling."
    )

    # Once pharmacist-confirmed: freeze SIG fields; indication stays editable for alternatives
    if medicine.pharmacist_status == "confirmed":
        for name, f in fields.items():
            if name == "indication":
                continue
            f["locked"] = True
            f["options"] = []
            f["message"] = "Locked — pharmacist confirmed"
            f["ui_tone"] = "locked"
            # Keep displayed pharmacist values green for required fields
            if name in REQUIRED_FOR_CONFIRM and f.get("value"):
                f["status"] = "green"

        ind = fields["indication"]
        ind["locked"] = False
        ind["optional"] = True
        ind["options"] = indication_opts
        if not eff["indication"]:
            ind["status"] = "green"
            ind["message"] = (
                "Optional — select a catalog indication for therapeutic alternatives."
            )
            ind["ui_tone"] = "yellow"
        elif indication_selected:
            ind["status"] = "green"
            ind["message"] = (
                "You may update for therapeutic alternatives; confirmed SIG is unchanged."
            )
            ind["ui_tone"] = "yellow"
        else:
            ind["status"] = "red"
            ind["message"] = (
                "Choose a catalog indication from the list, or clear to skip."
            )
            ind["ui_tone"] = "amber"

        can_confirm = False
        next_field = None

    return {
        "medicine_id": medicine.id,
        "item_number": medicine.item_number,
        "confidence": getattr(medicine, "parser_confidence", None),
        "pharmacist_status": medicine.pharmacist_status,
        "formulary_id": entry["formulary_id"] if drug_ok and entry else None,
        "canonical_drug": (
            _catalog_display_name(entry["canonical_name"]) if drug_ok and entry else None
        ),
        "catalog_sources": catalog_sources,
        "can_confirm": can_confirm,
        "confirm_hint": confirm_hint,
        "confirm_disclaimer": confirm_disclaimer,
        "validation_scope": "prescription_drug_identity",
        "thin_brand_shell": thin_brand_shell,
        "next_field": next_field,
        "awaiting_pharmacist_confirm": medicine.pharmacist_status != "confirmed"
        and any(fields[n]["status"] == "green" for n in REQUIRED_FOR_CONFIRM),
        "evidence": _evidence_panel(entry["canonical_name"]) if drug_ok and entry else None,
        "fields": fields,
        "ai": {
            "medicine_name": medicine.ai_medicine_name,
            "strength": medicine.ai_strength,
            "dose": medicine.ai_dose,
            "frequency": medicine.ai_frequency,
            "form": medicine.ai_form,
            "route": medicine.ai_route,
        },
    }


def list_verification_table(db: Session, pharmacist: User, session_id: str) -> list[dict]:
    rows = prescription_service.list_medicines(db, pharmacist, session_id)
    ocr_mock = session_ocr_is_mock(db, session_id)
    allow_mock = bool(settings.HITL_ALLOW_MOCK_CONFIRM)
    out = []
    for row in rows:
        state = build_field_state(row)
        state["ocr_is_mock"] = ocr_mock
        state["confirm_blocked_mock_ocr"] = bool(ocr_mock and not allow_mock)
        if state["confirm_blocked_mock_ocr"] and state["pharmacist_status"] != "confirmed":
            state["can_confirm"] = False
            state["confirm_block_reason"] = (
                "MOCK OCR session — Confirm disabled. Use Google Vision or set HITL_ALLOW_MOCK_CONFIRM=true for labelled demos."
            )
        out.append(state)
    return out


def apply_field_correction(
    db: Session,
    pharmacist: User,
    session_id: str,
    medicine_id: str,
    *,
    field: str,
    value: str,
) -> dict:
    prescription_service.get_owned_session(db, pharmacist, session_id)
    medicine = db.get(PrescriptionMedicine, medicine_id)
    if not medicine or medicine.session_id != session_id:
        raise HTTPException(status_code=404, detail="Medicine not found")

    if field not in FIELD_ORDER:
        raise HTTPException(status_code=422, detail="Invalid field")

    was_confirmed = medicine.pharmacist_status == "confirmed"
    if was_confirmed and field != "indication":
        raise HTTPException(
            status_code=422,
            detail="Row already confirmed — only indication may be updated for therapeutic alternatives",
        )

    # Indication may be cleared with empty string; all other fields reject placeholders
    if field == "indication":
        if (value or "").strip():
            _reject_if_placeholder(field, value)
    else:
        _reject_if_placeholder(field, value)

    state = build_field_state(medicine)
    if state["fields"][field]["locked"]:
        raise HTTPException(
            status_code=422,
            detail=state["fields"][field].get("message")
            or "Complete prior catalog fields before editing this one",
        )

    previous_value = state["fields"][field]["value"]

    if field == "drug":
        entry = resolve_hitl_drug(value)
        if entry is None or not entry.get("exact_canonical"):
            # Allow picking a suggested catalog canonical even if OCR query was fuzzy
            try:
                from app.services.datasets.catalog_store import catalog_available
                from app.services.datasets.match import suggest_medicines

                if catalog_available():
                    hits = suggest_medicines(value, top_k=8)
                    entry = next(
                        (
                            {
                                "formulary_id": h.drugbank_id or h.product_ndc or h.canonical_name,
                                "canonical_name": h.canonical_name,
                                "strengths": list(h.strengths or []),
                                "doses": [],
                                "frequencies": [],
                                "forms": list(h.dosage_forms or []),
                                "routes": list(h.routes or []),
                                "exact_canonical": normalize(h.canonical_name) == normalize(value),
                            }
                            for h in hits
                            if normalize(h.canonical_name) == normalize(value)
                        ),
                        None,
                    )
            except Exception:  # noqa: BLE001
                entry = None
            if entry is None:
                seed = find_by_canonical(value) or resolve_drug(value)
                if seed is None or normalize(seed.canonical_name) != normalize(value):
                    raise HTTPException(
                        status_code=422,
                        detail="Selected drug is not in the formulary dataset",
                    )
                entry = {
                    "formulary_id": seed.formulary_id,
                    "canonical_name": seed.canonical_name,
                    "exact_canonical": True,
                }
        new_name = _catalog_display_name(entry["canonical_name"]) or entry["canonical_name"]
        previous_drug = medicine.pharmacist_medicine_name or medicine.ai_medicine_name
        medicine.pharmacist_medicine_name = new_name
        medicine.formulary_matched = True
        medicine.formulary_id = str(entry["formulary_id"])
        # Only clear cascade when the canonical drug actually changes
        if normalize(previous_drug) != normalize(new_name):
            medicine.pharmacist_strength = None
            medicine.pharmacist_dose = None
            medicine.pharmacist_frequency = None
            medicine.pharmacist_form = None
            medicine.pharmacist_route = None
            medicine.pharmacist_verified_indication = None
        medicine.pharmacist_status = "field_review"
        record_hitl_event(
            db,
            session_id=session_id,
            pharmacist_user_id=pharmacist.id,
            medicine_id=medicine.id,
            event_type="hitl.field_corrected",
            field_name="drug",
            payload={
                "previous": previous_value,
                "new_value": new_name,
                "item_number": medicine.item_number,
                "source": entry.get("source") or "catalog",
                "cleared_downstream": normalize(previous_drug) != normalize(new_name),
            },
        )
        db.commit()
        db.refresh(medicine)
        from app.services import alternatives_service

        alternatives_service.materialize_suggestions(db, session_id, [medicine])
        _invalidate_session_analytics(db, session_id)
        return build_field_state(medicine)

    entry = resolve_hitl_drug(medicine.pharmacist_medicine_name or medicine.ai_medicine_name)
    if entry is None or not entry.get("exact_canonical"):
        raise HTTPException(status_code=422, detail="Resolve drug name first")

    if field == "indication":
        # Pre-confirm: only after required five are catalog-matched
        if not was_confirmed and not state["can_confirm"] and state.get("next_field") in REQUIRED_FOR_CONFIRM:
            raise HTTPException(
                status_code=422,
                detail="Indication unlocks only after drug, route, strength, dosage, and frequency match",
            )
        # Optional: empty clears the indication
        if not (value or "").strip():
            medicine.pharmacist_verified_indication = None
            if not was_confirmed:
                medicine.pharmacist_status = "field_review"
            record_hitl_event(
                db,
                session_id=session_id,
                pharmacist_user_id=pharmacist.id,
                medicine_id=medicine.id,
                event_type="hitl.field_corrected",
                field_name="indication",
                payload={
                    "previous": previous_value,
                    "new_value": None,
                    "item_number": medicine.item_number,
                    "optional": True,
                    "post_confirm": was_confirmed,
                },
            )
            db.commit()
            _invalidate_session_analytics(db, medicine.session_id)
            db.refresh(medicine)
            return build_field_state(medicine)
        allowed = [o["value"] for o in _indication_options_catalog(entry["canonical_name"])]
        if not value_in_list(value, allowed):
            raise HTTPException(
                status_code=422,
                detail="Indication must be blank or chosen from DrugBank / FDA_SPL / FDA_NDC catalog values",
            )
        canonical_value = next(opt for opt in allowed if normalize(opt) == normalize(value))
        medicine.pharmacist_verified_indication = canonical_value
        if not was_confirmed:
            medicine.pharmacist_status = "field_review"
        record_hitl_event(
            db,
            session_id=session_id,
            pharmacist_user_id=pharmacist.id,
            medicine_id=medicine.id,
            event_type="hitl.field_corrected",
            field_name="indication",
            payload={
                "previous": previous_value,
                "new_value": canonical_value,
                "item_number": medicine.item_number,
                "optional": True,
                "post_confirm": was_confirmed,
            },
        )
        db.commit()
        _invalidate_session_analytics(db, medicine.session_id)
        db.refresh(medicine)
        return build_field_state(medicine)

    eff = _effective(medicine)
    clinical = _filter_strength_options(list(entry["strengths"] or []), eff["strength"])
    forms = list(entry.get("forms") or [])
    catalog_routes = list(entry.get("routes") or [])
    products = list(entry.get("products") or [])
    cascade_kw = dict(
        drug_matched=True,
        catalog_forms=forms,
        catalog_routes=catalog_routes,
        catalog_strengths=clinical,
        seed_doses=list(entry.get("doses") or []),
        seed_frequencies=list(entry.get("frequencies") or []),
        ocr_route=eff["route"] or medicine.ai_route,
        ocr_strength=eff["strength"],
        catalog_source=entry.get("source"),
        products=products,
        canonical_name=entry.get("canonical_name"),
    )
    cascade = build_cascade_options(
        **cascade_kw,
        matched_route=None,
        matched_strength=None,
        matched_dose=None,
    )
    route_opts = _filter_option_labels(list(cascade["route"]["options"]))

    def _resolve_route() -> str | None:
        from app.services.catalog_field_match import catalog_route_from_context

        return catalog_route_from_context(
            route_opts,
            ocr_route=eff["route"] or medicine.ai_route,
            catalog_forms=list(entry.get("forms") or []),
            ocr_form=eff.get("form") or medicine.ai_form,
            ocr_dose=eff.get("dose") or medicine.ai_dose,
        )

    if field == "route":
        allowed_list = route_opts
    elif field == "strength":
        route_canon = _resolve_route()
        if not route_canon:
            raise HTTPException(status_code=422, detail="Confirm route before strength")
        cascade = build_cascade_options(
            **cascade_kw,
            matched_route=route_canon,
            matched_strength=None,
            matched_dose=None,
        )
        allowed_list = _filter_option_labels(list(cascade["strength"]["options"]))
    elif field == "dose":
        route_canon = _resolve_route()
        if not route_canon:
            raise HTTPException(status_code=422, detail="Confirm route before dosage")
        cascade = build_cascade_options(
            **cascade_kw,
            matched_route=route_canon,
            matched_strength=None,
            matched_dose=None,
        )
        strengths = _filter_option_labels(list(cascade["strength"]["options"]))
        strength_canon = _strength_from_ocr(eff["strength"], strengths)
        if not strength_canon:
            raise HTTPException(status_code=422, detail="Confirm strength before dosage")
        cascade = build_cascade_options(
            **cascade_kw,
            matched_route=route_canon,
            matched_strength=strength_canon,
            matched_dose=None,
        )
        allowed_list = _filter_option_labels(list(cascade["dose"]["options"]))
    else:  # frequency
        route_canon = _resolve_route()
        if not route_canon:
            raise HTTPException(status_code=422, detail="Confirm route before frequency")
        cascade = build_cascade_options(
            **cascade_kw,
            matched_route=route_canon,
            matched_strength=None,
            matched_dose=None,
        )
        strengths = _filter_option_labels(list(cascade["strength"]["options"]))
        strength_canon = _strength_from_ocr(eff["strength"], strengths)
        if not strength_canon:
            raise HTTPException(status_code=422, detail="Confirm strength before frequency")
        cascade = build_cascade_options(
            **cascade_kw,
            matched_route=route_canon,
            matched_strength=strength_canon,
            matched_dose=None,
        )
        doses_allowed = _filter_option_labels(list(cascade["dose"]["options"]))
        dose_canon = _canon_option(eff["dose"], doses_allowed)
        if not dose_canon:
            dose_canon = _prefer_dose_for_ocr_total(eff["strength"], strength_canon, doses_allowed)
        if not dose_canon:
            raise HTTPException(status_code=422, detail="Confirm dosage before frequency")
        cascade = build_cascade_options(
            **cascade_kw,
            matched_route=route_canon,
            matched_strength=strength_canon,
            matched_dose=dose_canon,
        )
        allowed_list = _filter_option_labels(list(cascade["frequency"]["options"]))

    matched = _canon_option(value, allowed_list)
    if matched is None and field == "strength":
        matched = _strength_from_ocr(value, allowed_list)
    if matched is None and not value_in_list(value, allowed_list):
        raise HTTPException(
            status_code=422,
            detail=f"{field} must be chosen from the selected drug catalog (no Unknown)",
        )
    canonical_value = matched or next(
        opt for opt in allowed_list if normalize(opt) == normalize(value)
    )
    if field == "route":
        medicine.pharmacist_route = canonical_value
        medicine.pharmacist_strength = None
        medicine.pharmacist_dose = None
        medicine.pharmacist_frequency = None
        medicine.pharmacist_verified_indication = None
    elif field == "strength":
        medicine.pharmacist_strength = canonical_value
        medicine.pharmacist_dose = None
        medicine.pharmacist_frequency = None
        medicine.pharmacist_verified_indication = None
    elif field == "dose":
        medicine.pharmacist_dose = canonical_value
        medicine.pharmacist_frequency = None
        medicine.pharmacist_verified_indication = None
    elif field == "frequency":
        medicine.pharmacist_frequency = canonical_value
        medicine.pharmacist_verified_indication = None
    medicine.pharmacist_status = "field_review"
    # Pharmacist fields are written only for the field being applied — never
    # auto-write pharmacist_dose after strength (OCR may rank dose options only).

    record_hitl_event(
        db,
        session_id=session_id,
        pharmacist_user_id=pharmacist.id,
        medicine_id=medicine.id,
        event_type="hitl.field_corrected",
        field_name=field,
        payload={
            "previous": previous_value,
            "new_value": canonical_value,
            "item_number": medicine.item_number,
            "drug": entry["canonical_name"],
        },
    )
    db.commit()
    _invalidate_session_analytics(db, medicine.session_id)
    db.refresh(medicine)
    return build_field_state(medicine)


def confirm_when_ready(
    db: Session,
    pharmacist: User,
    session_id: str,
    medicine_id: str,
) -> dict:
    prescription_service.get_owned_session(db, pharmacist, session_id)
    medicine = db.get(PrescriptionMedicine, medicine_id)
    if not medicine or medicine.session_id != session_id:
        raise HTTPException(status_code=404, detail="Medicine not found")

    # Idempotent: already confirmed — return current state without error
    if medicine.pharmacist_status == "confirmed":
        return build_field_state(medicine)

    _assert_confirm_allowed_for_ocr(db, session_id)

    state = build_field_state(medicine)
    if not state["can_confirm"]:
        raise HTTPException(
            status_code=422,
            detail=state.get("confirm_hint")
            or (
                "Cannot confirm until drug, route, strength, dosage, and frequency are "
                "catalog-matched (indication optional). Use Unable to verify if values cannot be matched."
            ),
        )
    for req in REQUIRED_FOR_CONFIRM:
        if _is_forbidden_placeholder(state["fields"][req].get("value")):
            raise HTTPException(
                status_code=422,
                detail="Confirm rejected — required fields cannot be Unknown/N/A; use Unable to verify instead.",
            )

    medicine.pharmacist_medicine_name = (
        _catalog_display_name(state["canonical_drug"]) or state["canonical_drug"]
    )
    medicine.pharmacist_strength = state["fields"]["strength"]["value"]
    medicine.pharmacist_route = state["fields"]["route"]["value"]
    medicine.pharmacist_dose = state["fields"]["dose"]["value"]
    medicine.pharmacist_frequency = state["fields"]["frequency"]["value"]
    medicine.pharmacist_verified_indication = state["fields"]["indication"]["value"]
    medicine.formulary_matched = True
    medicine.formulary_id = state["formulary_id"]
    medicine.pharmacist_status = "confirmed"
    medicine.verified_at = datetime.now(timezone.utc)
    record_hitl_event(
        db,
        session_id=session_id,
        pharmacist_user_id=pharmacist.id,
        medicine_id=medicine.id,
        event_type="hitl.row_confirmed",
        field_name=None,
        payload={
            "item_number": medicine.item_number,
            "drug": medicine.pharmacist_medicine_name,
            "strength": medicine.pharmacist_strength,
            "route": medicine.pharmacist_route,
            "dose": medicine.pharmacist_dose,
            "frequency": medicine.pharmacist_frequency,
            "indication": medicine.pharmacist_verified_indication,
        },
    )
    db.commit()
    _invalidate_session_analytics(db, medicine.session_id)
    db.refresh(medicine)
    try:
        from app.services.retention import maybe_delete_temp_after_confirm

        maybe_delete_temp_after_confirm(db, session_id)
    except Exception:  # noqa: BLE001
        pass
    return build_field_state(medicine)


def _invalidate_session_analytics(db: Session, session_id: str) -> None:
    from app.models.prescription import ReviewSession

    sess = db.get(ReviewSession, session_id)
    if sess is not None:
        sess.analytics_json = None
        sess.analytics_fingerprint = None
        db.commit()
