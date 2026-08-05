"""Shared formulary catalog for HITL field-by-field verification.

Synthetic academic dataset. Canonical drug names + OCR aliases + allowed
strength / dose / frequency / form / route values.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher


def normalize(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.lower().replace("-", " ").split())


def catalog_display_name(name: str | None) -> str | None:
    """Standardize medicine display names: first letter capital, rest lower per word.

    Examples: metformin → Metformin, ATORVASTATIN → Atorvastatin,
    amoxicillin/clavulanate → Amoxicillin/Clavulanate.

    Matching still uses ``normalize()`` — this is display / Confirm write formatting only.
    Small connector words (and, of, …) stay lowercase when not the first word.
    """
    if not name:
        return name
    n = " ".join(str(name).split()).strip()
    if not n:
        return n

    def _token(part: str) -> str:
        if not part:
            return part
        if len(part) == 1:
            return part.upper()
        return part[0].upper() + part[1:].lower()

    small = {"and", "or", "of", "with", "for", "to", "in"}
    words: list[str] = []
    for i, raw in enumerate(n.split()):
        if "/" in raw:
            words.append("/".join(_token(p) for p in raw.split("/")))
        elif "-" in raw:
            words.append("-".join(_token(p) for p in raw.split("-")))
        elif i > 0 and raw.lower() in small:
            words.append(raw.lower())
        else:
            words.append(_token(raw))
    return " ".join(words)


@dataclass(frozen=True)
class FormularyDrug:
    formulary_id: str
    canonical_name: str
    aliases: tuple[str, ...]
    strengths: tuple[str, ...]
    doses: tuple[str, ...]
    frequencies: tuple[str, ...]
    forms: tuple[str, ...]
    routes: tuple[str, ...]


FORMULARY_DRUGS: tuple[FormularyDrug, ...] = (
    FormularyDrug(
        formulary_id="FORM-AMOX-001",
        canonical_name="Amoxicillin",
        aliases=("amoxycillin", "amoxil", "amoxicilin"),
        strengths=("250 mg", "500 mg"),
        doses=("ONE capsule", "TWO capsules", "5 ml", "10 ml"),
        frequencies=("ONCE daily", "TWICE daily", "THREE times daily", "FOUR times daily"),
        forms=("capsule", "capsules", "tablet", "tablets", "oral suspension"),
        routes=("Oral",),
    ),
    FormularyDrug(
        formulary_id="FORM-IBU-001",
        canonical_name="Ibuprofen",
        aliases=("ibrufen", "brufen", "ibuorofen", "ibuprofn"),
        strengths=("200 mg", "400 mg"),
        doses=("ONE tablet", "TWO tablets", "ONE or TWO tablets"),
        frequencies=("ONCE daily", "TWICE daily", "THREE times daily", "up to THREE times daily"),
        forms=("tablet", "tablets", "capsule", "capsules"),
        routes=("Oral",),
    ),
    FormularyDrug(
        formulary_id="FORM-SAL-001",
        canonical_name="Salbutamol",
        aliases=("albuterol", "salbutomal", "ventolin"),
        strengths=("100 micrograms/actuation", "100 mcg/actuation"),
        doses=("ONE puff", "TWO puffs"),
        frequencies=("as required", "FOUR times daily", "when required"),
        forms=("inhaler", "aerosol"),
        routes=("Inhalation", "Inhaled"),
    ),
)


def all_canonical_names() -> list[str]:
    return [d.canonical_name for d in FORMULARY_DRUGS]


def find_by_canonical(name: str) -> FormularyDrug | None:
    key = normalize(name)
    for drug in FORMULARY_DRUGS:
        if normalize(drug.canonical_name) == key:
            return drug
    return None


def resolve_drug(name: str | None) -> FormularyDrug | None:
    """Exact canonical or alias match."""
    key = normalize(name)
    if not key:
        return None
    for drug in FORMULARY_DRUGS:
        if normalize(drug.canonical_name) == key:
            return drug
        if any(normalize(alias) == key for alias in drug.aliases):
            return drug
    return None


def suggest_drugs(query: str | None, *, limit: int | None = None) -> list[dict]:
    """Pharmacist dropdown options ranked by OCR similarity.

    When the real FDA_NDC + DrugBank catalog is built, returns top candidates
    from that catalog (never silently a single auto-select). Falls back to the
    small seed formulary if the catalog SQLite is not present.
    """
    top = 3 if limit is None else max(1, limit)
    try:
        from app.services.datasets.catalog_store import catalog_available
        from app.services.datasets.match import suggest_medicines

        if catalog_available():
            qn = normalize(query) if query else ""
            min_score = 40.0 if len(qn) <= 4 else 55.0
            hits = suggest_medicines(query, top_k=max(top, 10), min_score=min_score)
            out: list[dict] = []
            for hit in hits[:top]:
                out.append(
                    {
                        "formulary_id": hit.drugbank_id or hit.product_ndc or hit.canonical_name,
                        "canonical_name": catalog_display_name(hit.canonical_name) or hit.canonical_name,
                        "match_score": round(hit.score / 100.0, 3),
                        "match_reason": hit.reason,
                        "suggested": hit.score >= 55,
                        "strengths": hit.strengths or [],
                        "doses": [],
                        "frequencies": [],
                        "forms": hit.dosage_forms,
                        "routes": hit.routes,
                        "source": hit.source,
                        "matched_alias": hit.matched_alias,
                    }
                )
            if out:
                # Prefer richer product rows + stronger alias/name match (generic only)
                def _opt_rank(o: dict) -> tuple:
                    name = normalize(o.get("canonical_name"))
                    qn = normalize(query)
                    alias = normalize(o.get("matched_alias") or "")
                    exact = 2 if name == qn else (1 if alias and alias == qn else 0)
                    has_s = 1 if o.get("strengths") else 0
                    has_f = 1 if o.get("forms") else 0
                    has_r = 1 if o.get("routes") else 0
                    richness = has_s * 4 + has_f * 2 + has_r
                    if " and " in name or "/" in name:
                        richness += 2
                    src = (o.get("source") or "").upper()
                    ndc = 1 if "NDC" in src else 0
                    return (-(richness + ndc), -exact, -(o.get("match_score") or 0), len(name))

                out.sort(key=_opt_rank)
                return out[:top]
    except Exception:
        pass

    key = normalize(query)
    scored: list[tuple[float, FormularyDrug, str]] = []
    for drug in FORMULARY_DRUGS:
        names = (drug.canonical_name, *drug.aliases)
        best = 0.0
        best_reason = "catalog"
        for candidate in names:
            cand = normalize(candidate)
            if not key:
                score = 0.0
                reason = "catalog"
            elif cand == key:
                score = 1.0
                reason = "exact" if candidate == drug.canonical_name else "alias"
            elif key in cand or cand in key:
                score = 0.92
                reason = "partial"
            else:
                score = SequenceMatcher(None, key, cand).ratio()
                reason = "similar spelling" if score >= 0.55 else "catalog"
            if score > best:
                best = score
                best_reason = reason
        scored.append((best, drug, best_reason))
    scored.sort(key=lambda item: (item[0], item[1].canonical_name.lower()), reverse=True)
    selected = scored if limit is None else scored[:limit]
    out = []
    for score, drug, reason in selected:
        out.append(
            {
                "formulary_id": drug.formulary_id,
                "canonical_name": catalog_display_name(drug.canonical_name) or drug.canonical_name,
                "match_score": round(score, 3),
                "match_reason": reason,
                "suggested": score >= 0.55,
                "strengths": list(drug.strengths),
                "doses": list(drug.doses),
                "frequencies": list(drug.frequencies),
                "forms": list(drug.forms),
                "routes": list(drug.routes),
            }
        )
    return out


def value_in_list(value: str | None, options: tuple[str, ...] | list[str]) -> bool:
    key = normalize(value)
    if not key:
        return False
    return any(normalize(opt) == key for opt in options)


# Backward-compatible dict used by older pipeline validator
SEED_FORMULARY = {
    normalize(d.canonical_name): {
        "formulary_id": d.formulary_id,
        "strengths": list(d.strengths),
        "forms": list(d.forms),
        "routes": [r.lower() for r in d.routes],
        "doses": list(d.doses),
        "frequencies": list(d.frequencies),
        "canonical_name": d.canonical_name,
        "aliases": list(d.aliases),
    }
    for d in FORMULARY_DRUGS
}
