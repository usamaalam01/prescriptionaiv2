"""Therapeutic alternatives backed by the local FDA NDC + DrugBank (+ SPL) catalog.

Decision-support only — not clinical care / auto-substitution.
Uses medicine_catalog.sqlite3 for identity + indication-overlap candidate retrieval.
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.services.datasets.catalog_store import (
    MedicineRecord,
    catalog_available,
    get_medicine,
    get_meta,
    _connect,
)
from app.services.datasets.match import normalize_query, suggest_medicines
from app.services.therapeutic.indication import (
    indications_overlap,
    normalize_indication_text,
)

CATALOG_LABEL = "FDA NDC + DrugBank catalog"


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.lower().replace("-", " ").split())
_STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "onto",
    "due",
    "these",
    "those",
    "symptoms",
    "symptom",
    "treatment",
    "treat",
    "relief",
    "relieve",
    "temporarily",
    "uses",
    "use",
    "of",
    "or",
    "a",
    "an",
    "in",
    "on",
    "to",
    "by",
    "as",
    "is",
    "are",
    "be",
    "mg",
    "ml",
    "oral",
    "tablet",
    "tablets",
    "capsule",
    "capsules",
}


def catalog_dataset_version() -> str:
    meta = get_meta() if catalog_available() else {}
    built = meta.get("built_at") or meta.get("version") or "local"
    return f"catalog-{built}"


def resolve_catalog_identity(medicine_name: str) -> dict | None:
    """Map a medicine name to a catalog identity envelope, or None if unavailable."""
    if not catalog_available():
        return None
    q = normalize_query(medicine_name)
    if not q:
        return None

    hits = suggest_medicines(medicine_name, top_k=5, min_score=70.0)
    if not hits:
        return None

    best = hits[0]
    # Prefer exact / near-exact over weak fuzzy
    exact = best.score >= 98.0 or normalize_name(best.canonical_name) == q
    if best.score < 78.0 and not exact:
        return None

    # Load full record when possible
    record = None
    for h in hits:
        # Resolve medicine id via alias exact key
        mid = _medicine_id_for_canonical(h.canonical_name)
        if mid is not None:
            record = get_medicine(mid)
            if record:
                best = h
                break

    if record is None:
        # Synthesize from hit alone
        drugbank_id = best.drugbank_id or f"CATALOG:{best.canonical_name}"
        return {
            "canonical_drug_id": drugbank_id,
            "canonical_name": best.canonical_name,
            "active_ingredient": best.canonical_name,
            "drugbank_id": drugbank_id,
            "unii": "",
            "matched_spl_ids": [],
            "matched_product_ndcs": [best.product_ndc] if best.product_ndc else [],
            "match_method": "catalog_exact" if exact else "catalog_fuzzy",
            "identity_confidence": round(min(1.0, best.score / 100.0), 3),
            "manual_confirmation_required": not exact and best.score < 92.0,
            "identity_confirmed": exact or best.score >= 92.0,
            "message": None,
            "data_source": "catalog",
            "catalog_medicine_id": None,
            "catalog_sources": (best.source or "").split("+") if best.source else [],
            "dosage_forms": list(best.dosage_forms or []),
            "routes": list(best.routes or []),
            "indication": None,
            "provenance_label": CATALOG_LABEL,
        }

    drugbank_id = record.drugbank_id or f"CATALOG:{record.id}"
    return {
        "canonical_drug_id": drugbank_id,
        "canonical_name": record.canonical_name,
        "active_ingredient": record.canonical_name,
        "drugbank_id": drugbank_id,
        "unii": "",
        "matched_spl_ids": [],
        "matched_product_ndcs": [record.product_ndc] if record.product_ndc else [],
        "match_method": "catalog_exact" if exact else "catalog_fuzzy",
        "identity_confidence": round(min(1.0, best.score / 100.0), 3),
        "manual_confirmation_required": not exact and best.score < 92.0,
        "identity_confirmed": exact or best.score >= 92.0,
        "message": None,
        "data_source": "catalog",
        "catalog_medicine_id": record.id,
        "catalog_sources": list(record.sources or []),
        "dosage_forms": list(record.dosage_forms or []),
        "routes": list(record.routes or []),
        "indication": record.indication,
        "provenance_label": CATALOG_LABEL,
    }


def _medicine_id_for_canonical(canonical_name: str) -> int | None:
    key = normalize_name(canonical_name)
    if not key:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM medicines WHERE canonical_key=? LIMIT 1",
            (key,),
        ).fetchone()
    return int(row["id"]) if row else None


def _tokens_for_search(text: str) -> list[str]:
    raw = normalize_name(text)
    if not raw:
        return []
    parts = re.findall(r"[a-z0-9]+", raw)
    out: list[str] = []
    for p in parts:
        if len(p) < 4 or p in _STOP:
            continue
        if p not in out:
            out.append(p)
    return out[:12]


def _priority_phrases(indication: str) -> list[str]:
    """High-signal clinical phrases present in the verified indication (no free token soup)."""
    from app.services.therapeutic.indication import CONDITION_ALIASES

    lowered = normalize_name(indication)
    phrases: list[str] = []
    catalog = [
        "gastroesophageal reflux disease",
        "gastroesophageal reflux",
        "erosive esophagitis",
        "duodenal ulcer",
        "gastric ulcer",
        "allergic rhinitis",
        "hay fever",
        "upper respiratory allergies",
        "urticaria",
        "runny nose",
        "watery eyes",
        "bacterial infection",
        "rheumatoid arthritis",
        "osteoarthritis",
        "bronchospasm",
        "asthma",
        "mild to moderate pain",
        "inflammation",
        "schizophrenia",
        "bipolar i disorder",
        "bipolar disorder",
        "major depressive disorder",
        "autistic disorder",
        "tourette's disorder",
        "tourette disorder",
        "parkinsonism",
        "parkinson's disease",
        "extrapyramidal disorders",
        "extrapyramidal symptoms",
        "fever",
        "pain",
    ]
    # Longest-first so "hay fever" wins over "fever"
    for phrase in sorted(catalog, key=len, reverse=True):
        p = normalize_name(phrase)
        if not p:
            continue
        # Skip if a longer matched phrase already covers this token (e.g. hay fever > fever)
        if any(p != normalize_name(m) and p in normalize_name(m) for m in phrases):
            continue
        if lowered == p or f" {p} " in f" {lowered} " or lowered.startswith(p + " ") or lowered.endswith(" " + p):
            phrases.append(phrase)

    condition = normalize_indication_text(indication).get("condition") or ""
    if condition and condition in CONDITION_ALIASES:
        phrases.append(condition)
        for alias in CONDITION_ALIASES[condition]:
            if len(alias) >= 4:
                phrases.append(alias)
    elif condition and len(condition) >= 4:
        # Unknown but usable clinical label from HITL catalog dropdown
        phrases.append(condition)

    seen: set[str] = set()
    out: list[str] = []
    for p in phrases:
        key = normalize_name(p)
        if key and key not in seen:
            seen.add(key)
            out.append(p)
    return out[:12]


@lru_cache(maxsize=64)
def _indication_candidates_cached(phrase_key: str, limit: int) -> list[int]:
    """Cache medicine ids matching any of the ||-joined phrases."""
    phrases = [p for p in phrase_key.split("||") if p]
    if not phrases or not catalog_available():
        return []
    ids: list[int] = []
    seen: set[int] = set()
    with _connect() as conn:
        for phrase in phrases:
            like = f"%{phrase}%"
            rows = conn.execute(
                """
                SELECT id FROM medicines
                WHERE indication IS NOT NULL AND length(indication) > 20
                  AND lower(indication) LIKE ?
                LIMIT ?
                """,
                (like, limit),
            ).fetchall()
            for row in rows:
                mid = int(row["id"])
                if mid not in seen:
                    seen.add(mid)
                    ids.append(mid)
    return ids[: limit * 2]


def retrieve_catalog_candidates(source_identity: dict, verified_indication: str) -> list[dict]:
    """Retrieve different-ingredient alternatives via catalog indication overlap."""
    if not catalog_available():
        return []
    if not (verified_indication or "").strip():
        return []

    source_name = normalize_name(source_identity.get("canonical_name") or "")
    source_id = source_identity.get("catalog_medicine_id")
    source_dbid = normalize_name(str(source_identity.get("drugbank_id") or ""))

    indication = normalize_indication_text(
        verified_indication,
        source_section="pharmacist_verified_indication",
    )
    phrases = _priority_phrases(verified_indication)
    # Fall back to normalized condition text so HITL catalog indications still search
    if not phrases and indication.get("condition"):
        phrases = [str(indication["condition"])]
    if not phrases:
        return []
    phrase_key = "||".join(phrases[:6])
    medicine_ids = _indication_candidates_cached(phrase_key, 80)

    candidates: list[dict] = []
    condition = indication.get("condition") or ""
    for mid in medicine_ids:
        if source_id is not None and mid == source_id:
            continue
        rec = get_medicine(mid)
        if not rec:
            continue
        cand_key = normalize_name(rec.canonical_name)
        if not cand_key or cand_key == source_name:
            continue
        if source_dbid and rec.drugbank_id and normalize_name(rec.drugbank_id) == source_dbid:
            continue

        cand_labels = _labels_from_indication(rec.indication)
        raw = normalize_name(rec.indication or "")
        overlap = indications_overlap(condition, cand_labels)
        if not overlap and condition and condition in raw:
            overlap = True
        if not overlap and any(normalize_name(p) in raw for p in phrases if len(p) >= 6):
            overlap = True
        if not overlap:
            continue

        why_extra = "Catalog indication overlap with pharmacist-verified indication"
        why = [why_extra, "Different active ingredient / product from prescribed medicine"]
        srcs = rec.sources or []
        if "DrugBank" in srcs:
            why.append("DrugBank catalog record")
        if "FDA_NDC" in srcs or "FDA_SPL" in srcs:
            why.append("FDA product/label catalog evidence")

        drugbank_id = rec.drugbank_id or f"CATALOG:{rec.id}"
        record = {
            "drugbank_id": drugbank_id,
            "generic_name": rec.canonical_name,
            "synonyms": list(rec.aliases or [])[:12],
            "indications": cand_labels,
            "drug_class": "",
            "atc_classification": "",
            "mechanism_of_action": {},
            "targets": [],
            "drug_interactions": [],
            "approval_status": ["approved"],
            "withdrawal_status": None,
            "market_status": "active",
            "routes": list(rec.routes or []),
            "dosage_forms": list(rec.dosage_forms or []),
            "sources": list(srcs),
            "catalog_medicine_id": rec.id,
            "indication_text": (rec.indication or "")[:500],
        }
        spl = {
            "spl_id": f"CATALOG-SPL:{rec.id}",
            "route": (rec.routes or [None])[0],
            "dosage_form": (rec.dosage_forms or [None])[0],
            "contraindications": [],
            "warnings_and_precautions": "",
            "drug_interactions": "",
            "indications_and_usage": (rec.indication or "")[:400],
            "linked_drugbank_id": rec.drugbank_id,
        }

        candidates.append(
            {
                "candidate_drug_id": drugbank_id,
                "candidate_name": rec.canonical_name,
                "active_ingredient": rec.canonical_name,
                "classification": "therapeutic_alternative",
                "why_retrieved": why,
                "indication_relationship": {
                    "source_condition": condition,
                    "candidate_indications": cand_labels[:8],
                    "overlap": True,
                    "source_section": "catalog.indication",
                },
                "class_relationship": {
                    "source_class": source_identity.get("drug_class") or "",
                    "candidate_class": "",
                    "source_atc": "",
                    "candidate_atc": "",
                    "related": False,
                    "note": "ATC/class not fully indexed in local catalog — indication overlap used.",
                },
                "mechanism_relationship": {
                    "source": {},
                    "candidate": {},
                    "related": False,
                    "note": "Mechanism not indexed in local catalog v1.",
                },
                "target_relationship": {"shared_targets": [], "related": False},
                "record": record,
                "spl": spl,
                "data_source": "catalog",
                "provenance_label": CATALOG_LABEL,
            }
        )

    candidates.sort(
        key=lambda c: (
            -int(bool(c["record"].get("drugbank_id") and not str(c["record"]["drugbank_id"]).startswith("CATALOG:"))),
            -len(c["indication_relationship"].get("candidate_indications") or []),
            c["candidate_name"].lower(),
        )
    )
    return candidates[:40]


def _labels_from_indication(indication: str | None) -> list[str]:
    try:
        from app.services.datasets.indication_options import _extract_labels

        return _extract_labels(indication)
    except Exception:
        if not indication:
            return []
        return [indication[:160]]
