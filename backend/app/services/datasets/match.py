"""Pharmaceutical validation: fuzzy match OCR text to catalog, return top-3 candidates.

Uses FDA_NDC + DrugBank (+ optional SPL) index. Does not silently pick a single match.
Decision-support only — pharmacist must confirm.

Performance: exact + prefix/bucket candidates only — never WRatio over all ~370k aliases.
"""

from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from functools import lru_cache

from app.services.datasets.catalog_store import (
    catalog_available,
    clear_alias_cache,
    get_medicine,
    _alias_rows,
)
from app.services.datasets.models import CatalogHit, DISCLAIMER

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None  # type: ignore

_SPACE = re.compile(r"\s+")
_COMMON_ABBREV = {
    "asa": "aspirin",
    "apap": "acetaminophen",
    "paracetamol": "acetaminophen",  # US catalog primary; keep OCR Acetaminophen exact
    "hctz": "hydrochlorothiazide",
    "mtx": "methotrexate",
    "amox": "amoxicillin",
    "amoxil": "amoxicillin",
    "amoxycillin": "amoxicillin",
    "amoxcillin": "amoxicillin",
    "amoxcilin": "amoxicillin",
    "ibrufen": "ibuprofen",
    "brufen": "ibuprofen",
    "ibuprofene": "ibuprofen",
    "ventolin": "salbutamol",
    "albuterol": "salbutamol",
    # Common handwritten / OCR misspellings (decision-support suggestions only)
    "arcabose": "acarbose",
    "acarbos": "acarbose",
    "pantoprazol": "pantoprazole",
    "pantoprozole": "pantoprazole",
    "cetirizin": "cetirizine",
    "cetrizine": "cetirizine",
    "ceterizine": "cetirizine",
    "cetirizene": "cetirizine",
    "metformine": "metformin",
    "acetaminophe": "acetaminophen",
    "acetaminophn": "acetaminophen",
}

_LEADING_ITEM = re.compile(r"^[\d]+[.)]\s*")
_STRENGTH_CUT = re.compile(r"\s+\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ml)\b", re.I)


def normalize_query(value: str | None) -> str:
    """Normalize OCR drug text for catalog lookup (abbrev + first-token misspellings)."""
    if not value:
        return ""
    text = _SPACE.sub(" ", value.strip().lower().replace("-", " "))
    text = _LEADING_ITEM.sub("", text).strip()
    if text in _COMMON_ABBREV:
        return _COMMON_ABBREV[text]
    # "Cetrizine 10 mg …" → remap first token, then use canonical for exact alias hit
    head = _STRENGTH_CUT.split(text, 1)[0].strip()
    token = head.split(" ", 1)[0] if head else ""
    if token in _COMMON_ABBREV:
        return _COMMON_ABBREV[token]
    if head in _COMMON_ABBREV:
        return _COMMON_ABBREV[head]
    return text


def _score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 100.0
    if fuzz is not None:
        return float(fuzz.WRatio(a, b))
    return SequenceMatcher(None, a, b).ratio() * 100.0


@lru_cache(maxsize=1)
def _alias_indexes() -> tuple[dict[str, list[tuple[int, str]]], dict[str, list[tuple[str, int, str]]]]:
    """exact[alias_key] -> [(medicine_id, alias_raw), ...]
    buckets[first3] -> [(alias_key, medicine_id, alias_raw), ...]
    """
    exact: dict[str, list[tuple[int, str]]] = defaultdict(list)
    buckets: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for alias_key, medicine_id, alias_raw in _alias_rows():
        if not alias_key:
            continue
        exact[alias_key].append((medicine_id, alias_raw))
        buckets[alias_key[:3]].append((alias_key, medicine_id, alias_raw))
    return dict(exact), dict(buckets)


def _hit_from_medicine(
    medicine_id: int,
    *,
    score: float,
    alias_raw: str,
    reason: str,
) -> CatalogHit | None:
    rec = get_medicine(medicine_id)
    if not rec:
        return None
    return CatalogHit(
        canonical_name=rec.canonical_name,
        score=score,
        source="+".join(rec.sources),
        brand_names=[a for a in rec.aliases if a.lower() != rec.canonical_name.lower()][:8],
        strengths=rec.strengths[:12],
        dosage_forms=rec.dosage_forms,
        routes=rec.routes,
        drugbank_id=rec.drugbank_id,
        product_ndc=rec.product_ndc,
        matched_alias=alias_raw,
        reason=reason,
    )


def suggest_medicines(
    query: str | None,
    *,
    top_k: int = 3,
    min_score: float = 55.0,
    context_strength: str | None = None,
) -> list[CatalogHit]:
    """Return top-k catalog candidates for an OCR medicine string (fast path)."""
    q = normalize_query(query)
    if not q:
        return []
    if not catalog_available():
        return []

    try:
        exact_idx, buckets = _alias_indexes()
    except Exception:  # noqa: BLE001
        return []

    seen_meds: set[int] = set()
    exact: list[CatalogHit] = []

    for medicine_id, alias_raw in exact_idx.get(q, ()):
        if medicine_id in seen_meds:
            continue
        seen_meds.add(medicine_id)
        hit = _hit_from_medicine(
            medicine_id,
            score=100.0,
            alias_raw=alias_raw,
            reason="Exact alias / name match against FDA_NDC + DrugBank catalog",
        )
        if hit:
            exact.append(hit)
        # Enough unique exact hits to rank — avoid hydrating dozens of rows
        if len(exact) >= max(top_k * 4, 8):
            break

    def _exact_rank(hit: CatalogHit) -> tuple:
        canon = hit.canonical_name.strip().lower()
        return (
            0 if canon == q else 1,
            0 if " and " not in canon and "," not in canon else 1,
            len(canon),
            canon,
        )

    exact.sort(key=_exact_rank)
    if len(exact) >= top_k:
        return exact[:top_k]

    # Candidate pool: same 3-char bucket only (tight cap)
    candidates: list[tuple[str, int, str]] = []
    prefix = q[:3]
    if prefix:
        candidates.extend(buckets.get(prefix, ())[:200])
    token = q.split(" ", 1)[0]
    if len(token) >= 3 and token[:3] != prefix:
        candidates.extend(buckets.get(token[:3], ())[:100])

    # Single-token OCR typos often change the first 3 letters (arcabose vs acarbose).
    # Probe nearby 3-char prefixes so WRatio can still rank the true drug.
    if len(q.split()) == 1 and len(prefix) == 3 and len(candidates) < 40:
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        near: set[str] = set()
        for i in range(3):
            for ch in alphabet:
                if ch == prefix[i]:
                    continue
                near.add(prefix[:i] + ch + prefix[i + 1 :])
        # Transpositions of the first three letters
        near.add(prefix[1] + prefix[0] + prefix[2])
        near.add(prefix[0] + prefix[2] + prefix[1])
        for pfx in near:
            if pfx == prefix:
                continue
            candidates.extend(buckets.get(pfx, ())[:40])
        if len(candidates) > 400:
            candidates = candidates[:400]

    # Cheap filter first; WRatio only on shortlist
    shortlist: list[tuple[str, int, str]] = []
    for alias_key, medicine_id, alias_raw in candidates:
        if medicine_id in seen_meds:
            continue
        if (
            alias_key.startswith(q)
            or q.startswith(alias_key[: min(len(alias_key), max(3, len(q)))])
            or q in alias_key
            or alias_key in q
        ):
            shortlist.append((alias_key, medicine_id, alias_raw))
        if len(shortlist) >= 80:
            break

    fuzzy_pool: list[tuple[float, int, str]] = []
    for alias_key, medicine_id, alias_raw in shortlist:
        if alias_key.startswith(q):
            sc = 95.0
        else:
            sc = _score(q, alias_key)
        if sc >= min_score:
            fuzzy_pool.append((sc, medicine_id, alias_raw))

    fuzzy_pool.sort(key=lambda t: t[0], reverse=True)
    fuzzy_pool = fuzzy_pool[:40]

    hits = list(exact)
    for sc, medicine_id, alias_raw in fuzzy_pool:
        if medicine_id in seen_meds:
            continue
        seen_meds.add(medicine_id)
        boost = 0.0
        hit = _hit_from_medicine(
            medicine_id,
            score=min(100.0, sc + boost),
            alias_raw=alias_raw,
            reason="Fuzzy match (generic/brand/synonym) — top candidates for pharmacist confirmation",
        )
        if not hit:
            continue
        if context_strength and hit.strengths:
            ns = normalize_query(context_strength)
            if any(ns and ns in normalize_query(s) for s in hit.strengths):
                hit = CatalogHit(
                    canonical_name=hit.canonical_name,
                    score=min(100.0, hit.score + 5.0),
                    source=hit.source,
                    brand_names=hit.brand_names,
                    strengths=hit.strengths,
                    dosage_forms=hit.dosage_forms,
                    routes=hit.routes,
                    drugbank_id=hit.drugbank_id,
                    product_ndc=hit.product_ndc,
                    matched_alias=hit.matched_alias,
                    reason=hit.reason,
                )
        hits.append(hit)
        if len(hits) >= top_k:
            break

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]


def reload_catalog() -> None:
    clear_alias_cache()
    _alias_indexes.cache_clear()


__all__ = ["suggest_medicines", "reload_catalog", "DISCLAIMER", "CatalogHit"]
