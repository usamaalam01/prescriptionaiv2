"""Catalog-first field matching for HITL (no per-drug special cases).

OCR values are mapped to options that already exist in FDA_NDC / DrugBank / FDA_SPL.
Algorithms are general: exact match, unit-strength multiples, quantity-word doses,
catalog-gated route inference from forms (never invent a route not in catalog options).
"""

from __future__ import annotations

import re
from typing import Iterable

from app.services.formulary_catalog import normalize

_MG_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|µg)\b", re.I)
_QTY_WORDS = {
    1: ("one", "1"),
    2: ("two", "2"),
    3: ("three", "3"),
    4: ("four", "4"),
    5: ("five", "5"),
    6: ("six", "6"),
    8: ("eight", "8"),
}
_FORM_WORDS = ("tablet", "tablets", "capsule", "capsules", "caplet", "caplets", "puff", "puffs")

# Dosage-form family → HITL route (only applied when that route is already a catalog option)
_FORM_FAMILY_TO_ROUTE: dict[str, str] = {
    "tablet": "Oral",
    "capsule": "Oral",
    "liquid": "Oral",
    "inhaler": "Inhalation",
    "injection": "Injection",
    "topical": "Topical",
    "drop": "Ophthalmic",
    "suppository": "Rectal",
    "patch": "Transdermal",
}
_FORM_CUE_RE = re.compile(
    r"\b(tablet|tablets|capsule|capsules|caplet|caplets|syrup|suspension|solution|"
    r"inhaler|puff|puffs|injection|injectable|cream|ointment|gel|drop|drops|"
    r"suppository|patch|transdermal)\b",
    re.I,
)


def _norm_opt(value: str | None, options: Iterable[str] | None) -> str | None:
    if not value or not options:
        return None
    key = normalize(value)
    for opt in options:
        if normalize(opt) == key:
            return opt
    for opt in options:
        nopt = normalize(opt)
        if key and (nopt.startswith(key + " ") or nopt.startswith(key + "/") or f" {key} " in f" {nopt} "):
            # Reject promoting ratio/IV rows from bare OCR solids
            if "/" in opt and "/" not in value:
                continue
            return opt
    return None


def _parse_amount(text: str | None) -> tuple[float, str] | None:
    if not text:
        return None
    m = _MG_RE.search(text)
    if not m:
        return None
    unit = m.group(2).lower().replace("µg", "mcg")
    return float(m.group(1)), unit


def catalog_strength_from_ocr(
    ocr_strength: str | None,
    options: list[str] | tuple[str, ...] | None,
    *,
    max_multiplier: int = 8,
) -> str | None:
    """Map OCR strength to a catalog option.

    1) Exact / prefix match against catalog spellings.
    2) If OCR is N× a catalog unit strength (same unit), return that unit
       (e.g. OCR 1000 mg with catalog 500 mg → 500 mg for any drug).
    Prefers smallest multiplier ≥ 2, then largest matching unit (fewer tablets).
    """
    hit = _norm_opt(ocr_strength, options)
    if hit:
        return hit
    parsed = _parse_amount(ocr_strength)
    if not parsed or not options:
        return None
    ocr_amt, ocr_unit = parsed

    candidates: list[tuple[int, float, str]] = []
    for opt in options:
        p = _parse_amount(opt)
        if not p:
            continue
        unit_amt, unit = p
        if unit != ocr_unit or unit_amt <= 0:
            continue
        ratio = ocr_amt / unit_amt
        n = int(round(ratio))
        if n < 1 or n > max_multiplier:
            continue
        if abs(ratio - n) > 1e-6:
            continue
        # Exact unit already handled above; multiples are the interesting case
        if n == 1:
            return opt
        candidates.append((n, unit_amt, opt))

    if not candidates:
        return None
    # Prefer lowest tablet count, then highest unit strength
    candidates.sort(key=lambda t: (t[0], -t[1]))
    return candidates[0][2]


def catalog_dose_from_ocr_total(
    ocr_strength: str | None,
    strength_canon: str | None,
    doses: list[str] | tuple[str, ...] | None,
    *,
    max_multiplier: int = 8,
) -> str | None:
    """When OCR total = N × catalog unit strength, prefer N tablets/capsules from catalog doses."""
    if not doses or not ocr_strength or not strength_canon:
        return None
    ocr = _parse_amount(ocr_strength)
    unit = _parse_amount(strength_canon)
    if not ocr or not unit or ocr[1] != unit[1] or unit[0] <= 0:
        return None
    ratio = ocr[0] / unit[0]
    n = int(round(ratio))
    if n < 1 or n > max_multiplier or abs(ratio - n) > 1e-6:
        return None

    words = _QTY_WORDS.get(n, (str(n),))
    # Try form-specific labels present in catalog options
    for form in _FORM_WORDS:
        for w in words:
            for candidate in (
                f"{w} {form}",
                f"{w.upper()} {form}",
                f"{w.title()} {form}",
            ):
                hit = _norm_opt(candidate, doses)
                if hit:
                    return hit
        # Plural/singular soft match via substring
        for opt in doses:
            nopt = normalize(opt)
            if any(normalize(w) == nopt.split()[0] for w in words if nopt.split()) and form.rstrip("s") in nopt:
                return opt
    return None


def prefer_unit_strengths_for_ocr(
    ocr_strength: str | None,
    strengths: list[str],
    *,
    max_multiplier: int = 8,
) -> list[str]:
    """Reorder catalog strengths so OCR multiples of a unit rise to the top."""
    if not ocr_strength or not strengths:
        return list(strengths)
    hit = catalog_strength_from_ocr(ocr_strength, strengths, max_multiplier=max_multiplier)
    if not hit:
        return list(strengths)
    return [hit] + [s for s in strengths if s != hit]


def _form_family(text: str | None) -> str | None:
    """Map free-text form / dose cue to a coarse dosage-form family."""
    if not text:
        return None
    t = text.lower()
    # Injection before liquid — "injection, solution" is IV, not oral liquid
    if re.search(r"\b(?:inject|intravenous|intramuscular|subcutaneous|\biv\b|\bim\b|\bsc\b)", t):
        return "injection"
    if re.search(r"\b(?:tablets?|tabs?|caplets?)\b", t):
        return "tablet"
    if re.search(r"\b(?:capsules?|\bcaps?\b)", t):
        return "capsule"
    if re.search(r"\b(?:syrup|suspension|elixir|oral\s+solution)\b", t):
        return "liquid"
    if re.search(r"\b(?:inhal|puffs?|nebul)\b", t):
        return "inhaler"
    if re.search(r"\b(?:cream|ointment|gel|lotion|topical)\b", t):
        return "topical"
    if re.search(r"\b(?:drops?|ophthalm|eye)\b", t):
        return "drop"
    if re.search(r"\b(?:suppositor|rectal)\b", t):
        return "suppository"
    if re.search(r"\b(?:patch|transdermal)\b", t):
        return "patch"
    return None


def _routes_implied_by_forms(forms: Iterable[str] | None) -> list[str]:
    """Unique HITL routes implied by catalog dosage forms (order preserved)."""
    found: list[str] = []
    for form in forms or []:
        fam = _form_family(str(form))
        route = _FORM_FAMILY_TO_ROUTE.get(fam or "")
        if route and route not in found:
            found.append(route)
    return found


def catalog_route_suggestions(
    options: list[str] | tuple[str, ...] | None,
    *,
    ocr_route: str | None = None,
    catalog_forms: list[str] | tuple[str, ...] | None = None,
    ocr_form: str | None = None,
    ocr_dose: str | None = None,
) -> list[str]:
    """Rank existing catalog routes; never invent routes not in ``options``.

    Bare mg never implies a route. Form/dose cues and unique form implication
    may reorder suggestions only — they do not auto-select for green HITL status.
    """
    if not options:
        return []
    opts = [o for o in options if o]
    if not opts:
        return []

    ranked: list[str] = []

    def _push(route: str | None) -> None:
        if route and route in opts and route not in ranked:
            ranked.append(route)

    if ocr_route:
        from app.services.datasets.evidence_route import display_route_label, routes_equivalent

        mapped = display_route_label(ocr_route)
        _push(mapped if mapped in opts else None)
        _push(_norm_opt(ocr_route, opts))
        for opt in opts:
            if routes_equivalent(ocr_route, opt):
                _push(opt)
                break

    for cue in (ocr_form, ocr_dose):
        fam = _form_family(cue)
        _push(_FORM_FAMILY_TO_ROUTE.get(fam or ""))
        if cue:
            m = _FORM_CUE_RE.search(cue)
            if m:
                fam = _form_family(m.group(1))
                _push(_FORM_FAMILY_TO_ROUTE.get(fam or ""))

    for route in _routes_implied_by_forms(catalog_forms):
        _push(route)

    for route in opts:
        _push(route)
    return ranked


def catalog_route_from_context(
    options: list[str] | tuple[str, ...] | None,
    *,
    ocr_route: str | None = None,
    catalog_forms: list[str] | tuple[str, ...] | None = None,
    ocr_form: str | None = None,
    ocr_dose: str | None = None,
) -> str | None:
    """Strict route resolution for green HITL status (fail closed).

    Resolves only when:
      1) OCR / pharmacist route text maps to a catalog option, or
      2) Exactly one catalog route exists.

    Never invents a route not in ``options``.
    Never treats bare mg as Oral.
    Never majority-votes catalog forms into a route.
    Form/dose cues may rank suggestions via ``catalog_route_suggestions`` but
    do not auto-green an ambiguous multi-route drug.
    """
    del catalog_forms, ocr_form, ocr_dose  # ranking-only; not used for green resolve
    if not options:
        return None
    opts = [o for o in options if o]
    if not opts:
        return None

    # 1) OCR / explicit pharmacist route text → catalog option (evidence-based)
    if ocr_route:
        from app.services.datasets.evidence_route import display_route_label, routes_equivalent

        mapped = display_route_label(ocr_route)
        if mapped and mapped in opts:
            return mapped
        hit = _norm_opt(ocr_route, opts)
        if hit:
            return hit
        for opt in opts:
            if routes_equivalent(ocr_route, opt):
                return opt

    # 2) Exactly one catalog route
    if len(opts) == 1:
        return opts[0]

    return None
