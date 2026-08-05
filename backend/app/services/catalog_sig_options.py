"""Derive HITL route/strength/dosage/frequency dropdowns from catalog context.

Evidence-only CDS (CSCK700): FDA NDC + DrugBank store dosage_forms + routes + strengths.
When the medicine catalog DB is mounted, runtime options come from
``hitl_catalog_query`` strict intersections:
  routes ← products.route (no form inference)
  strengths ← products for selected route
  doses ← label_dose_options exact medicine+route+strength
  frequencies ← label_dose_frequency_options exact medicine+route+strength+dose

Form/route SIG templates remain available only when the catalog DB is absent and
HITL_ALLOW_DOSE_TEMPLATES / HITL_ALLOW_FREQ_TEMPLATES are true (offline demos).

Fail-closed: empty options when no catalog evidence matches (no invented defaults).
Decision-support only — pharmacist must still Confirm.
"""

from __future__ import annotations

import re
from typing import Any

_SPACE = re.compile(r"\s+")

# Canonical route labels shown in HITL (catalog strings map into these)
ROUTE_ORAL = "Oral"
ROUTE_INHALATION = "Inhalation"
ROUTE_TOPICAL = "Topical"
ROUTE_INJECTION = "Injection"
ROUTE_OPHTHALMIC = "Ophthalmic"
ROUTE_OTIC = "Otic"
ROUTE_RECTAL = "Rectal"
ROUTE_TRANSDERMAL = "Transdermal"
ROUTE_NASAL = "Nasal"
ROUTE_OTHER = "Other"

_ROUTE_ORDER = (
    ROUTE_ORAL,
    ROUTE_INHALATION,
    ROUTE_TOPICAL,
    ROUTE_INJECTION,
    ROUTE_OPHTHALMIC,
    ROUTE_OTIC,
    ROUTE_RECTAL,
    ROUTE_TRANSDERMAL,
    ROUTE_NASAL,
    ROUTE_OTHER,
)

# Which form families are valid for each route
_ROUTE_FORMS: dict[str, frozenset[str]] = {
    ROUTE_ORAL: frozenset({"tablet", "capsule", "liquid"}),
    ROUTE_INHALATION: frozenset({"inhaler"}),
    ROUTE_TOPICAL: frozenset({"topical"}),
    ROUTE_INJECTION: frozenset({"injection", "liquid"}),
    ROUTE_OPHTHALMIC: frozenset({"drop"}),
    ROUTE_OTIC: frozenset({"drop"}),
    ROUTE_RECTAL: frozenset({"suppository"}),
    ROUTE_TRANSDERMAL: frozenset({"patch"}),
    ROUTE_NASAL: frozenset({"inhaler", "drop"}),
    ROUTE_OTHER: frozenset({"tablet", "capsule", "liquid", "inhaler", "injection", "topical", "drop", "suppository", "patch"}),
}

# Form family → catalog-conditioned dosage options
_FORM_DOSES: dict[str, tuple[str, ...]] = {
    "tablet": (
        "Half tablet",
        "One tablet",
        "One and Half tablets",
        "Two tablets",
              
    ),
    "capsule": (
        "ONE capsule",
        "TWO capsules",
    ),
    "liquid": (
        "2.5 ml",
        "5 ml",
        "7.5 ml",
        "10 ml",
        "15 ml",
        "ONE teaspoonful (5 ml)",
    ),
    "inhaler": (
        "ONE puff",
        "TWO puffs",

    ),
    "injection": (
        "as directed",
    ),
    "topical": (
        "Apply thinly",
        "Apply as directed",
        "Apply to affected area",
    ),
    "drop": (
        "ONE drop",
        "TWO drops",
    ),
    "suppository": (
        "ONE suppository",
        "insert ONE as directed",
    ),
    "patch": (
        "Apply ONE patch",
        "ONE patch as directed",
    ),
}

_ORAL_SOLID_FREQ = (
    "ONCE daily",
    "TWICE daily",
    "THREE times daily",
    "FOUR times daily",
    "before meal",
    "after meal",
    "at bedtime",
)
_ORAL_LIQUID_FREQ = (
    "ONCE daily",
    "TWICE daily",
    "THREE times daily",
    "FOUR times daily",
    "before meal",
    "after meal",
    "at bedtime",
)
_INHALER_FREQ = (
    "ONCE daily",
    "TWICE daily",
    "THREE times daily",
    "FOUR times daily",
    "when required",
)
_TOPICAL_FREQ = (
    "ONCE daily",
    "TWICE daily",
    "THREE times daily",
    "FOUR times daily",
    "when required",
)
_INJECTION_FREQ = (
     "ONCE daily",
    "TWICE daily",
    "THREE times daily",
    "FOUR times daily",
    "when required",
)
_GENERIC_FREQ = (
     "ONCE daily",
    "TWICE daily",
    "THREE times daily",
    "FOUR times daily",
    "when required",
)

_FREQ_BY_ROUTE: dict[str, tuple[str, ...]] = {
    ROUTE_ORAL: _ORAL_SOLID_FREQ,
    ROUTE_INHALATION: _INHALER_FREQ,
    ROUTE_TOPICAL: _TOPICAL_FREQ,
    ROUTE_INJECTION: _INJECTION_FREQ,
    ROUTE_OPHTHALMIC: _GENERIC_FREQ,
    ROUTE_OTIC: _GENERIC_FREQ,
    ROUTE_RECTAL: _GENERIC_FREQ,
    ROUTE_TRANSDERMAL: ("ONCE daily", "every 72 hours", "as directed", "ONCE weekly"),
    ROUTE_NASAL: _INHALER_FREQ,
    ROUTE_OTHER: _GENERIC_FREQ,
}


def _norm(value: str | None) -> str:
    if not value:
        return ""
    return _SPACE.sub(" ", value.strip().lower().replace("-", " "))


def classify_route(route: str | None) -> str | None:
    """Legacy coarse route buckets for seed/template demos only.

    Prefer ``app.services.datasets.evidence_route`` for catalog HITL — it does not
    merge clinically distinct routes (IV≠IM, Oral≠Sublingual, Cutaneous≠Topical).
    """
    from app.services.datasets.evidence_route import display_route_label, resolve_route_key

    # When evidence staging is available, return evidence display (no merge).
    key = resolve_route_key(route)
    if key:
        label = display_route_label(route)
        if label:
            return label
    r = _norm(route)
    if not r or r in {"not applicable", "n/a", "na", "none"}:
        return None
    # Whole-token abbreviations first
    if re.fullmatch(r"po|p\.o\.?", r):
        return ROUTE_ORAL
    if re.fullmatch(r"iv|i\.v\.?", r):
        return "Intravenous"
    if re.fullmatch(r"im|i\.m\.?", r):
        return "Intramuscular"
    if re.fullmatch(r"sc|sq|subq", r):
        return "Subcutaneous"
    if "oral" in r or r.startswith("po "):
        return ROUTE_ORAL
    if any(k in r for k in ("inhal", "respiratory", "nebuli")):
        return ROUTE_INHALATION
    if "transdermal" in r:
        return ROUTE_TRANSDERMAL
    if "cutaneous" in r:
        return "Cutaneous"
    if any(k in r for k in ("topical", "dermal")) and "transdermal" not in r:
        return ROUTE_TOPICAL
    if "intravenous" in r:
        return "Intravenous"
    if "intramuscular" in r:
        return "Intramuscular"
    if "subcutaneous" in r:
        return "Subcutaneous"
    if "inject" in r or "parenteral" in r:
        return ROUTE_INJECTION
    if "ophthalm" in r or "eye" in r:
        return ROUTE_OPHTHALMIC
    if "otic" in r or "ear" in r:
        return ROUTE_OTIC
    if "rectal" in r:
        return ROUTE_RECTAL
    if "nasal" in r:
        return ROUTE_NASAL
    if "sublingual" in r:
        return "Sublingual"
    if "dental" in r:
        return "Dental"
    return ROUTE_OTHER


def _strength_kind(strength: str | None) -> str:
    """Coarse strength shape used to align with route (oral solid vs liquid vs inhaler…)."""
    s = _norm(strength)
    if not s:
        return "unknown"
    if re.search(r"actuation|inhal|/puff|mcg/|microgram", s):
        return "inhaler"
    if re.search(r"%|mg/g|g/g|w/w", s):
        return "topical"
    if re.search(r"mcg/hr|µg/hr|mg/24|mg/day|per\s*24", s):
        return "transdermal"
    if re.search(r"/\s*5\s*ml|per\s*5\s*ml", s):
        return "oral_liquid"
    if re.search(r"mg\s*/\s*ml|/\s*ml\b|mg/1ml|/\s*100\s*ml", s):
        return "injectable_or_liquid"
    # Ratio / density / NDC-style noise is not a patient oral tablet strength
    if "/" in s:
        if re.search(r"/\s*5\s*ml|per\s*5\s*ml", s):
            return "oral_liquid"
        if re.search(r"mg\s*/\s*ml|/\s*ml\b|/\s*100\s*ml", s):
            return "injectable_or_liquid"
        return "unknown"
    if re.fullmatch(r"\d+(?:\.\d+)?\s*(?:mg|mcg|g)", s):
        return "oral_solid"
    if re.search(r"\bmg\b|\bg\b|\bmcg\b", s):
        return "oral_solid"
    return "unknown"


_ROUTE_STRENGTH_KINDS: dict[str, frozenset[str]] = {
    ROUTE_ORAL: frozenset({"oral_solid", "oral_liquid", "unknown"}),
    ROUTE_INHALATION: frozenset({"inhaler", "unknown"}),
    ROUTE_TOPICAL: frozenset({"topical", "unknown"}),
    ROUTE_INJECTION: frozenset({"injectable_or_liquid", "oral_liquid", "unknown"}),
    ROUTE_OPHTHALMIC: frozenset({"topical", "injectable_or_liquid", "unknown"}),
    ROUTE_OTIC: frozenset({"topical", "injectable_or_liquid", "unknown"}),
    ROUTE_RECTAL: frozenset({"oral_solid", "unknown"}),
    ROUTE_TRANSDERMAL: frozenset({"transdermal", "topical", "unknown"}),
    ROUTE_NASAL: frozenset({"inhaler", "topical", "unknown"}),
    ROUTE_OTHER: frozenset({"oral_solid", "oral_liquid", "inhaler", "topical", "injectable_or_liquid", "transdermal", "unknown"}),
}


def strengths_for_route(
    strengths: list[str] | tuple[str, ...] | None,
    route: str | None,
    *,
    ocr_strength: str | None = None,
    products: list[dict] | None = None,
) -> list[str]:
    """Filter catalog strengths so only route-relevant options appear."""
    route_label = classify_route(route) or route

    catalog_list = [s for s in (strengths or []) if s]
    # Prefer compact oral-solid catalog strengths; product rows are often IV/ratio noise
    product_strengths: list[str] = []
    if products and route_label:
        for p in products:
            ps = (p.get("strength") or "").strip()
            if not ps:
                continue
            p_route = classify_route(str(p.get("route") or ""))
            if p_route and p_route != route_label:
                continue
            if not p_route and p.get("route"):
                if route_label.lower() not in str(p.get("route")).lower():
                    continue
            if ps not in product_strengths:
                product_strengths.append(ps)

    # Merge: catalog first, then product (dedupe). Do not replace catalog solids with IV products.
    merged: list[str] = []
    for s in catalog_list + product_strengths:
        if s and s not in merged:
            merged.append(s)

    allowed_kinds = _ROUTE_STRENGTH_KINDS.get(route_label or "", frozenset({"unknown"}))
    out: list[str] = []
    for s in merged:
        kind = _strength_kind(s)
        if kind in allowed_kinds:
            if s not in out:
                out.append(s)

    # Fail-closed: do not dump unfiltered strengths when route filter empties
    if not out:
        return []

    # Compact oral solids only when available (drop 1 kg/1kg / 80 mg/1 noise)
    if route_label == ROUTE_ORAL and not _strength_prefers_liquid(ocr_strength):
        solids = [
            s
            for s in out
            if _strength_kind(s) == "oral_solid" and "/" not in s
        ]
        liquids = [s for s in out if _strength_kind(s) == "oral_liquid"]
        if solids:
            out = solids
        elif liquids:
            out = liquids

    # Prefer catalog unit strength when OCR is an N× multiple (any drug)
    if ocr_strength and route_label == ROUTE_ORAL:
        from app.services.catalog_field_match import prefer_unit_strengths_for_ocr

        out = prefer_unit_strengths_for_ocr(ocr_strength, out)
        # Exact OCR solid match first when present as its own option
        ocr_m = re.search(r"(\d+(?:\.\d+)?)\s*mg\b", ocr_strength, re.I)
        if ocr_m:
            exact = f"{ocr_m.group(1)} mg"
            for s in list(out):
                if _norm(s) == _norm(exact):
                    out.remove(s)
                    out.insert(0, s)
                    break

    # Prefer OCR match at top when it survives the filter (unless unit remap already applied)
    if ocr_strength:
        from app.services.catalog_field_match import catalog_strength_from_ocr

        remapped = catalog_strength_from_ocr(ocr_strength, out)
        key = _norm(ocr_strength)
        if remapped and _norm(remapped) != key:
            # Unit remap already ordered by prefer_unit_strengths_for_ocr
            pass
        else:
            for s in list(out):
                if _norm(s) == key or key and key in _norm(s):
                    if "/" in s and "/" not in (ocr_strength or ""):
                        continue
                    out.remove(s)
                    out.insert(0, s)
                    break

    # Oral: solids before liquids for readability (unless OCR is liquid)
    if route_label == ROUTE_ORAL and not _strength_prefers_liquid(ocr_strength):
        head = out[0] if out else None
        out.sort(
            key=lambda s: (
                0 if _strength_kind(s) == "oral_solid" and "/" not in s else 1,
                0 if re.fullmatch(r"\d+(?:\.\d+)?\s*mg", s, re.I) else 1,
                len(s),
                s.lower(),
            )
        )
        # Restore catalog unit preference after sort
        if ocr_strength:
            from app.services.catalog_field_match import prefer_unit_strengths_for_ocr

            out = prefer_unit_strengths_for_ocr(ocr_strength, out)
        elif head and head in out:
            out = [head] + [s for s in out if s != head]
    return out[:30]



def routes_for_drug(
    catalog_routes: list[str] | tuple[str, ...] | None,
    *,
    forms: list[str] | tuple[str, ...] | None = None,
    strength: str | None = None,
    ocr_route: str | None = None,
) -> list[str]:
    """Catalog route options for the selected drug (before strength selection)."""
    found: list[str] = []
    for raw in catalog_routes or []:
        label = classify_route(raw)
        if label and label not in found and label != ROUTE_OTHER:
            found.append(label)
        elif label == ROUTE_OTHER and label not in found:
            found.append(label)

    # Infer routes from dosage forms when catalog routes are empty/noisy
    if not found:
        for form in forms or []:
            fam = _classify_form(form)
            if fam in {"tablet", "capsule", "liquid"} and ROUTE_ORAL not in found:
                found.append(ROUTE_ORAL)
            elif fam == "inhaler" and ROUTE_INHALATION not in found:
                found.append(ROUTE_INHALATION)
            elif fam == "topical" and ROUTE_TOPICAL not in found:
                found.append(ROUTE_TOPICAL)
            elif fam == "injection" and ROUTE_INJECTION not in found:
                found.append(ROUTE_INJECTION)
            elif fam == "drop" and ROUTE_OPHTHALMIC not in found:
                found.append(ROUTE_OPHTHALMIC)
            elif fam == "suppository" and ROUTE_RECTAL not in found:
                found.append(ROUTE_RECTAL)
            elif fam == "patch" and ROUTE_TRANSDERMAL not in found:
                found.append(ROUTE_TRANSDERMAL)

    # Fail-closed: never invent a default Oral route when catalog has no routes/forms.
    # Empty list → HITL must use Unable to verify (evidence-only CDS).
    if not found:
        return []

    # Prefer OCR route at top when it maps to a catalog option
    ocr_label = classify_route(ocr_route)
    if ocr_label and ocr_label in found:
        found = [ocr_label] + [r for r in found if r != ocr_label]

    # Optional: if strength already known (re-open), nudge compatible routes first
    if strength:
        kind = _strength_kind(strength)
        preferred: list[str] = []
        if kind == "inhaler":
            preferred = [ROUTE_INHALATION, ROUTE_NASAL]
        elif kind == "topical":
            preferred = [ROUTE_TOPICAL, ROUTE_OPHTHALMIC, ROUTE_OTIC]
        elif kind == "transdermal":
            preferred = [ROUTE_TRANSDERMAL]
        elif kind in {"oral_liquid", "oral_solid"}:
            preferred = [ROUTE_ORAL]
        elif kind == "injectable_or_liquid":
            preferred = [ROUTE_INJECTION, ROUTE_ORAL]
        bumped = [r for r in preferred if r in found]
        if bumped:
            found = bumped + [r for r in found if r not in bumped]

    # Community Rx lines often say "tablets"/"capsules" — prefer Oral over IV/powder noise
    # when OCR did not specify another route.
    if not ocr_label and ROUTE_ORAL in found:
        form_blob = " ".join(str(f) for f in (forms or [])).lower()
        if any(k in form_blob for k in ("tablet", "capsule", "caplet")):
            found = [ROUTE_ORAL] + [r for r in found if r != ROUTE_ORAL]

    order = {r: i for i, r in enumerate(_ROUTE_ORDER)}
    # Keep OCR / strength preference order among equals by stable secondary sort only when no bump
    if not strength and not ocr_label and found[:1] != [ROUTE_ORAL]:
        found.sort(key=lambda r: order.get(r, 99))
    return found


def _classify_form(form: str) -> str | None:
    f = _norm(form)
    if not f:
        return None
    if any(k in f for k in ("inhal", "aerosol", "spray", "nebuli")):
        return "inhaler"
    if any(k in f for k in ("inject", "syringe", "iv ", "intravenous")):
        return "injection"
    if any(k in f for k in ("cream", "ointment", "gel", "lotion", "topical")):
        return "topical"
    if any(k in f for k in ("drop", "ophthalm", "otic")):
        return "drop"
    if "suppositor" in f:
        return "suppository"
    if "patch" in f or "transdermal" in f:
        return "patch"
    if any(
        k in f
        for k in (
            "suspension",
            "syrup",
            "solution",
            "elixir",
            "liquid",
            "for suspension",
            "powder, for suspension",
        )
    ):
        return "liquid"
    if "capsule" in f:
        return "capsule"
    if "tablet" in f or "tab" == f or f.startswith("tab "):
        return "tablet"
    return None


def _strength_prefers_liquid(strength: str | None) -> bool:
    s = _norm(strength)
    if not s:
        return False
    return bool(re.search(r"/\s*5\s*ml|/\s*ml|mg\s*/\s*ml|per\s*5\s*ml", s))


def _strength_prefers_solid(strength: str | None) -> bool:
    s = _norm(strength)
    if not s:
        return False
    if _strength_prefers_liquid(s):
        return False
    return bool(re.search(r"\bmg\b|\bmcg\b|\bmicrogram|\bg\b", s)) and "/" not in s.replace("/1", "")


def _active_form_families(
    forms: list[str] | tuple[str, ...],
    strength: str | None,
    route: str | None,
) -> list[str]:
    families: list[str] = []
    for form in forms or []:
        fam = _classify_form(form)
        if fam and fam not in families:
            families.append(fam)

    route_label = classify_route(route) or route
    allowed = _ROUTE_FORMS.get(route_label or "", None)

    if allowed is not None:
        families = [f for f in families if f in allowed]
        if not families:
            # Catalog forms didn't intersect — use route defaults
            families = list(allowed)

    if not families:
        if route_label == ROUTE_INHALATION:
            return ["inhaler"]
        if route_label == ROUTE_TOPICAL:
            return ["topical"]
        if route_label == ROUTE_INJECTION:
            return ["injection"]
        if route_label in {ROUTE_OPHTHALMIC, ROUTE_OTIC}:
            return ["drop"]
        if route_label == ROUTE_RECTAL:
            return ["suppository"]
        if route_label == ROUTE_TRANSDERMAL:
            return ["patch"]
        if _strength_prefers_liquid(strength):
            return ["liquid"]
        return ["tablet", "capsule"]

    # Within a route, strength further gates oral solids vs liquids
    if route_label in {None, ROUTE_ORAL, ROUTE_OTHER}:
        if _strength_prefers_liquid(strength):
            liquid = [f for f in families if f == "liquid"]
            return liquid or ["liquid"]
        if _strength_prefers_solid(strength):
            solids = [f for f in families if f in {"tablet", "capsule"}]
            if solids:
                return solids
    return families


def _dose_family(dose: str | None) -> str | None:
    d = _norm(dose)
    if not d:
        return None
    if "puff" in d or "inhal" in d:
        return "inhaler"
    if "ml" in d or "teaspoon" in d:
        return "liquid"
    if "capsule" in d:
        return "capsule"
    if "tablet" in d or "tab" in d:
        return "tablet"
    if "drop" in d:
        return "drop"
    if "patch" in d:
        return "patch"
    if "suppositor" in d:
        return "suppository"
    if "inject" in d:
        return "injection"
    if "apply" in d:
        return "topical"
    return None


def doses_for_drug_strength_route(
    *,
    forms: list[str] | tuple[str, ...] | None,
    strength: str | None,
    route: str | None,
    seed_doses: list[str] | tuple[str, ...] | None = None,
) -> tuple[list[str], str]:
    """Template dosage options for selected drug + strength + route (legacy / demo)."""
    families = _active_form_families(list(forms or []), strength, route)
    out: list[str] = []

    seed_kept: list[str] = []
    for d in seed_doses or []:
        fam = _dose_family(d)
        if fam is None or fam in families or (
            fam in {"tablet", "capsule"} and any(f in families for f in ("tablet", "capsule"))
        ):
            if d not in seed_kept:
                seed_kept.append(d)

    for d in seed_kept:
        if d not in out:
            out.append(d)

    for fam in families:
        for d in _FORM_DOSES.get(fam, ()):
            if d not in out:
                out.append(d)

    source = "catalog_route_form_derived"
    if seed_kept and len(seed_kept) == len(out):
        source = "seed_formulary"
    elif seed_kept:
        source = "catalog_route_form_derived+seed"

    return out, source


def _live_dosage_section_text(
    canonical_name: str, medicine_id: int, strength: str | None = None
) -> str:
    """Return dosage_and_administration text, preferring a sibling label if primary is thin.

    Some ingredient rows (e.g. generic ``ibuprofen``) only carry pediatric OTC directions.
    Prefer a same-ingredient oral solid label that yields usable SIG extracts.
    """
    from app.services.datasets.catalog_store import get_medicine_by_canonical, list_label_sections
    from app.services.datasets.label_dose_extract import doses_for_label_context

    sections = list_label_sections(medicine_id)
    primary = (sections.get("dosage_and_administration") or "").strip()
    # Thin / non-yielding primaries fall through to sibling search below.
    if len(primary) >= 800:
        probe_primary_early = doses_for_label_context(
            primary,
            route="Oral",
            strength=strength or "200 mg",
            dosage_form="TABLET",
        )
        if probe_primary_early and any(
            c.dose_label.upper().startswith("ONE ") for c in probe_primary_early
        ):
            return primary

    try:
        from app.services.datasets.match import suggest_medicines
    except Exception:  # noqa: BLE001
        return primary

    best_text = primary
    # score: prefer non-combo oral solids that yield a ONE-unit dose for this strength
    best_score = (-1, 0, 0, 0, len(primary))  # has_one, non_combo, exactish, n_probe, len
    probe_primary = doses_for_label_context(
        primary,
        route="Oral",
        strength=strength or "200 mg",
        dosage_form="TABLET",
    ) if primary else []
    if probe_primary:
        has_one = any(c.dose_label.upper().startswith("ONE ") for c in probe_primary)
        best_score = (1 if has_one else 0, 1, 1, len(probe_primary), len(primary))

    probe_strength = strength or "200 mg"
    # Also try strength-qualified sibling names (e.g. "Acetaminophen 500 mg")
    queries = [canonical_name]
    if strength and canonical_name:
        m = re.search(r"(\d+(?:\.\d+)?)\s*mg", strength, re.I)
        if m:
            mg = m.group(1)
            queries.append(f"{canonical_name} {mg} mg")
            queries.append(f"{canonical_name} {mg}Mg")
    seen_ids: set[int] = {medicine_id}
    base = canonical_name.lower()
    for query in queries:
        try:
            hits = suggest_medicines(query, top_k=12)
        except Exception:  # noqa: BLE001
            continue
        for hit in hits:
            forms = " ".join(hit.dosage_forms or []).lower()
            routes = " ".join(hit.routes or []).lower()
            oralish = ("oral" in routes) or any(x in forms for x in ("tablet", "capsule", "caplet"))
            nm = (hit.canonical_name or "").lower()
            if not oralish and nm:
                oralish = "tablet" in nm or "capsule" in nm or "oral" in nm or "mg" in nm
            if not oralish:
                continue
            rec = get_medicine_by_canonical(hit.canonical_name)
            if rec is None or rec.id in seen_ids:
                continue
            seen_ids.add(rec.id)
            text = (list_label_sections(rec.id).get("dosage_and_administration") or "").strip()
            if not text:
                continue
            probe = doses_for_label_context(
                text,
                route="Oral",
                strength=probe_strength,
                dosage_form="TABLET",
            )
            if not probe:
                probe = doses_for_label_context(
                    text,
                    route="Oral",
                    strength=probe_strength,
                    dosage_form="CAPSULE",
                )
            if not probe:
                continue
            combo = 0 if (" and " not in nm and "," not in nm) else 1
            exactish = 1 if (nm == base or nm.startswith(base + " ")) else 0
            has_one = 1 if any(c.dose_label.upper().startswith("ONE ") for c in probe) else 0
            score = (has_one, 1 - combo, exactish, len(probe), len(text))
            if score > best_score:
                best_score = score
                best_text = text
    return best_text


def _preferred_oral_solid_form(
    forms: list[str] | tuple[str, ...] | None,
) -> str | None:
    """Prefer tablet/capsule forms over suspension/injection noise for SIG extract."""
    tablets: list[str] = []
    capsules: list[str] = []
    other: list[str] = []
    for f in forms or []:
        if not f:
            continue
        fam = _classify_form(f)
        if fam == "tablet":
            tablets.append(f)
        elif fam == "capsule":
            capsules.append(f)
        else:
            other.append(f)
    if tablets:
        return tablets[0]
    if capsules:
        return capsules[0]
    return other[0] if other else "TABLET"


def evidence_doses_for_drug_route_strength(
    *,
    canonical_name: str | None,
    route: str | None,
    strength: str | None,
    forms: list[str] | tuple[str, ...] | None = None,
) -> tuple[list[str], str, list[dict[str, Any]]]:
    """Prefer indexed FDA_SPL dose options; live-parse label_sections if index empty."""
    if not canonical_name or not route or not strength:
        return [], "FDA_SPL_none", []

    try:
        from app.services.datasets.catalog_store import (
            get_medicine_by_canonical,
            list_label_dose_options,
        )
        from app.services.datasets.label_dose_extract import doses_for_label_context
    except Exception:  # noqa: BLE001
        return [], "FDA_SPL_none", []

    rec = get_medicine_by_canonical(canonical_name)
    if rec is None:
        return [], "FDA_SPL_none", []

    indexed = list_label_dose_options(rec.id, route=route, strength=strength)
    indexed_labels = [o.dose_label for o in indexed]
    indexed_meta = [
        {
            "value": o.dose_label,
            "evidence_excerpt": o.evidence_excerpt,
            "confidence": o.confidence,
            "source": o.source,
        }
        for o in indexed
    ]

    text = _live_dosage_section_text(canonical_name, rec.id, strength=strength)
    live_labels: list[str] = []
    live_meta: list[dict[str, Any]] = []
    if text.strip():
        form = _preferred_oral_solid_form(forms)
        cands = doses_for_label_context(
            text,
            route=route,
            strength=strength,
            dosage_form=form,
        )
        live_labels = [c.dose_label for c in cands]
        live_meta = [
            {
                "value": c.dose_label,
                "evidence_excerpt": c.evidence_excerpt,
                "confidence": c.confidence,
                "source": "FDA_SPL",
            }
            for c in cands
        ]

    # Prefer live parse (strength-aware conversion) then fill gaps from index
    labels: list[str] = []
    meta: list[dict[str, Any]] = []
    for lab, m in list(zip(live_labels, live_meta)) + list(zip(indexed_labels, indexed_meta)):
        if lab and lab not in labels:
            labels.append(lab)
            meta.append(m)
    if labels:
        src = (
            "FDA_SPL_dosage_and_administration_live"
            if live_labels
            else "FDA_SPL_dosage_and_administration"
        )
        if live_labels and indexed_labels:
            src = "FDA_SPL_dosage_and_administration_merged"
        return labels, src, meta
    return [], "FDA_SPL_none", []


def evidence_frequencies_for_drug_route_strength(
    *,
    canonical_name: str | None,
    route: str | None,
    strength: str | None,
    dose: str | None = None,
) -> tuple[list[str], str, list[dict[str, Any]]]:
    """Prefer indexed FDA_SPL frequency options; live-parse label_sections if empty.

    When ``dose`` is set, re-parse the dosage section and prefer frequencies that
    co-occur near the selected dose phrase (dose-adjacent scoping).
    """
    if not canonical_name or not route or not strength:
        return [], "FDA_SPL_none", []

    try:
        from app.services.datasets.catalog_store import (
            get_medicine_by_canonical,
            list_label_frequency_options,
        )
        from app.services.datasets.label_dose_extract import frequencies_for_label_context
    except Exception:  # noqa: BLE001
        return [], "FDA_SPL_none", []

    rec = get_medicine_by_canonical(canonical_name)
    if rec is None:
        return [], "FDA_SPL_none", []

    text = _live_dosage_section_text(canonical_name, rec.id, strength=strength)

    indexed = list_label_frequency_options(rec.id, route=route, strength=strength)

    # Dose selected → live dose-adjacent ranking from full section text
    if dose and dose.strip() and text.strip():
        cands = frequencies_for_label_context(
            text,
            route=route,
            strength=strength,
            dose=dose,
        )
        if cands:
            any_adj = any(c.dose_adjacent for c in cands)
            labels = [c.frequency_label for c in cands]
            meta = [
                {
                    "value": c.frequency_label,
                    "evidence_excerpt": c.evidence_excerpt,
                    "confidence": c.confidence,
                    "source": "FDA_SPL",
                    "dose_adjacent": c.dose_adjacent,
                    "distance_to_dose": c.distance_to_dose,
                }
                for c in cands
            ]
            # Union broader freqs so OCR ONCE daily is not dropped when adjacency
            # latches onto a twice-daily sibling phrase.
            for o in indexed:
                if o.frequency_label not in labels:
                    labels.append(o.frequency_label)
                    meta.append(
                        {
                            "value": o.frequency_label,
                            "evidence_excerpt": o.evidence_excerpt,
                            "confidence": o.confidence,
                            "source": o.source,
                        }
                    )
            for c in frequencies_for_label_context(
                text, route=route, strength=strength, dose=None
            ):
                if c.frequency_label not in labels:
                    labels.append(c.frequency_label)
                    meta.append(
                        {
                            "value": c.frequency_label,
                            "evidence_excerpt": c.evidence_excerpt,
                            "confidence": c.confidence,
                            "source": "FDA_SPL",
                        }
                    )
            src = (
                "FDA_SPL_dosage_and_administration_dose_adjacent"
                if any_adj
                else "FDA_SPL_dosage_and_administration_live"
            )
            return labels, src, meta

    if indexed:
        labels = [o.frequency_label for o in indexed]
        meta = [
            {
                "value": o.frequency_label,
                "evidence_excerpt": o.evidence_excerpt,
                "confidence": o.confidence,
                "source": o.source,
            }
            for o in indexed
        ]
        return labels, "FDA_SPL_dosage_and_administration", meta

    if not text.strip():
        return [], "FDA_SPL_none", []

    cands = frequencies_for_label_context(text, route=route, strength=strength)
    if not cands:
        return [], "FDA_SPL_none", []
    labels = [c.frequency_label for c in cands]
    meta = [
        {
            "value": c.frequency_label,
            "evidence_excerpt": c.evidence_excerpt,
            "confidence": c.confidence,
            "source": "FDA_SPL",
        }
        for c in cands
    ]
    return labels, "FDA_SPL_dosage_and_administration_live", meta


# Back-compat alias used by older call sites
def doses_for_drug_strength(
    *,
    forms: list[str] | tuple[str, ...] | None,
    strength: str | None,
    seed_doses: list[str] | tuple[str, ...] | None = None,
    route: str | None = None,
) -> tuple[list[str], str]:
    return doses_for_drug_strength_route(
        forms=forms,
        strength=strength,
        route=route,
        seed_doses=seed_doses,
    )


def frequencies_for_drug_strength_dose(
    *,
    forms: list[str] | tuple[str, ...] | None,
    routes: list[str] | tuple[str, ...] | None,
    strength: str | None,
    dose: str | None,
    route: str | None = None,
    seed_frequencies: list[str] | tuple[str, ...] | None = None,
) -> tuple[list[str], str]:
    """Frequency options for drug + strength + route + dosage."""
    route_label = classify_route(route) if route else None
    if not route_label and routes:
        # Fall back to first classified catalog route
        for raw in routes:
            route_label = classify_route(raw)
            if route_label:
                break

    fam = _dose_family(dose)
    if fam is None:
        families = _active_form_families(list(forms or []), strength, route_label)
        fam = families[0] if families else None

    if route_label == ROUTE_ORAL and fam == "liquid":
        base = list(_ORAL_LIQUID_FREQ)
    elif route_label and route_label in _FREQ_BY_ROUTE:
        base = list(_FREQ_BY_ROUTE[route_label])
        # Oral solids: prefer solid freq list when dose is tablet/capsule
        if route_label == ROUTE_ORAL and fam in {"tablet", "capsule"}:
            base = list(_ORAL_SOLID_FREQ)
    elif fam == "inhaler":
        base = list(_INHALER_FREQ)
    elif fam == "liquid":
        base = list(_ORAL_LIQUID_FREQ)
    elif fam in {"tablet", "capsule"}:
        base = list(_ORAL_SOLID_FREQ)
    elif fam == "topical":
        base = list(_TOPICAL_FREQ)
    elif fam == "injection":
        base = list(_INJECTION_FREQ)
    else:
        base = list(_GENERIC_FREQ)

    out: list[str] = []
    seed_kept: list[str] = []
    for f in seed_frequencies or []:
        if f in base or (route_label == ROUTE_ORAL and fam in {"tablet", "capsule", "liquid"}):
            if f not in seed_kept:
                seed_kept.append(f)

    for f in seed_kept:
        if f not in out:
            out.append(f)
    for f in base:
        if f not in out:
            out.append(f)

    source = "catalog_route_form_derived"
    if seed_kept and set(seed_kept) >= set(out):
        source = "seed_formulary"
    elif seed_kept:
        source = "catalog_route_form_derived+seed"

    return out, source


def forms_compatible_with_route(
    forms: list[str] | tuple[str, ...] | None,
    route: str | None,
) -> list[str]:
    """Keep only catalog dosage forms that belong to the matched route."""
    route_label = classify_route(route) or route
    allowed = _ROUTE_FORMS.get(route_label or "", None)
    if not forms:
        return []
    if allowed is None:
        return [f for f in forms if f]
    out: list[str] = []
    for form in forms:
        fam = _classify_form(form)
        if fam and fam in allowed and form not in out:
            out.append(form)
    return out


def catalog_sources_list(source: str | None) -> list[str]:
    """Normalize catalog provenance into FDA_NDC / DrugBank / FDA_SPL labels."""
    if not source:
        return []
    parts = [p.strip() for p in str(source).replace(",", "+").split("+") if p.strip()]
    out: list[str] = []
    for p in parts:
        u = p.upper().replace(" ", "_")
        if "SPL" in u:
            label = "FDA_SPL"
        elif "NDC" in u or u == "FDA":
            label = "FDA_NDC"
        elif "DRUGBANK" in u or u == "DB":
            label = "DrugBank"
        elif u in {"SEED", "SEED_FORMULARY"}:
            label = "seed_formulary"
        else:
            label = p
        if label not in out:
            out.append(label)
    return out


def build_cascade_options(
    *,
    drug_matched: bool,
    catalog_forms: list[str] | tuple[str, ...] | None,
    catalog_routes: list[str] | tuple[str, ...] | None,
    catalog_strengths: list[str] | tuple[str, ...] | None,
    seed_doses: list[str] | tuple[str, ...] | None = None,
    seed_frequencies: list[str] | tuple[str, ...] | None = None,
    matched_route: str | None = None,
    matched_strength: str | None = None,
    matched_dose: str | None = None,
    ocr_route: str | None = None,
    ocr_strength: str | None = None,
    catalog_source: str | None = None,
    products: list[dict[str, Any]] | None = None,
    canonical_name: str | None = None,
    allow_dose_templates: bool | None = None,
    allow_freq_templates: bool | None = None,
) -> dict[str, Any]:
    """Build HITL dropdown lists from catalog, conditioned on prior matched fields.

    Cascade:
      drug matched → route options
      drug + route matched → strength options (route-filtered)
      drug + route + strength matched → dosage options (SPL evidence; templates optional)
      drug + route + strength + dose matched → frequency options (SPL evidence; templates optional)
    """
    sources = catalog_sources_list(catalog_source)
    if not sources:
        sources = ["FDA_NDC", "DrugBank"]

    empty = {
        "route": {
            "options": [],
            "depends_on": ["drug"],
            "catalog_sources": sources,
            "option_source": "catalog_routes",
            "context": {},
        },
        "strength": {
            "options": [],
            "depends_on": ["drug", "route"],
            "catalog_sources": sources,
            "option_source": "catalog_strengths",
            "context": {},
        },
        "dose": {
            "options": [],
            "depends_on": ["drug", "route", "strength"],
            "catalog_sources": sources,
            "option_source": "FDA_SPL_none",
            "context": {},
            "evidence": [],
        },
        "frequency": {
            "options": [],
            "depends_on": ["drug", "route", "strength", "dose"],
            "catalog_sources": sources,
            "option_source": "FDA_SPL_none",
            "context": {},
            "evidence": [],
        },
        "forms_for_route": [],
    }
    if not drug_matched:
        return empty

    catalog_db = False
    try:
        from app.services.datasets.catalog_store import catalog_available

        catalog_db = bool(catalog_available())
    except Exception:  # noqa: BLE001
        catalog_db = False

    route_opts: list[str] = []
    route_src = "catalog_routes"
    try:
        from app.services.datasets.hitl_catalog_query import query_routes

        if catalog_db and canonical_name:
            r_meta, r_src = query_routes(canonical_name)
            if r_meta:
                route_opts = [o["value"] for o in r_meta]
                route_src = r_src
            else:
                # Catalog present: products.route only — never invent via form inference.
                route_opts = []
                route_src = r_src or "products_route_none"
    except Exception:  # noqa: BLE001
        if catalog_db:
            route_opts = []
            route_src = "products_route_none"
        else:
            route_opts = []
    if not route_opts and not catalog_db:
        # Offline / no catalog DB: allow legacy catalog_routes (+ form inference).
        route_opts = routes_for_drug(
            catalog_routes,
            forms=catalog_forms,
            ocr_route=ocr_route,
        )
        route_src = "catalog_routes"
    empty["route"]["options"] = route_opts
    empty["route"]["option_source"] = route_src
    empty["route"]["context"] = {"drug_matched": True, "strict_catalog": catalog_db}

    if not matched_route:
        return empty

    forms_for_route = forms_compatible_with_route(catalog_forms, matched_route)
    # If catalog forms don't intersect route (noisy merge), still allow route-default families
    forms_for_dose = forms_for_route or list(catalog_forms or [])

    strength_opts: list[str] = []
    strength_src = "catalog_strengths"
    strength_evidence: list[dict[str, Any]] = []
    try:
        from app.services.datasets.hitl_catalog_query import query_strengths

        if catalog_db and canonical_name:
            s_meta, s_src = query_strengths(canonical_name, route=matched_route)
            if s_meta:
                # Rank existing product strengths for OCR; do not invent.
                ranked = strengths_for_route(
                    [o["value"] for o in s_meta],
                    matched_route,
                    ocr_strength=ocr_strength,
                    products=None,
                )
                strength_opts = ranked or [o["value"] for o in s_meta]
                strength_src = s_src
                by_val = {o["value"]: o for o in s_meta}
                strength_evidence = [by_val[v] for v in strength_opts if v in by_val]
    except Exception:  # noqa: BLE001
        strength_opts = []
    if not strength_opts:
        strength_opts = strengths_for_route(
            list(catalog_strengths or []),
            matched_route,
            ocr_strength=ocr_strength,
            products=products,
        )
        strength_src = "catalog_products" if products else "catalog_strengths"
    empty["strength"]["options"] = strength_opts
    empty["strength"]["option_source"] = strength_src
    empty["strength"]["context"] = {
        "drug_matched": True,
        "route": matched_route,
        "forms_considered": forms_for_route[:12],
        "products_used": bool(products) or strength_src.startswith("products"),
        "strict_catalog": catalog_db and strength_src.startswith("products"),
    }
    if strength_evidence:
        empty["strength"]["evidence"] = strength_evidence
    empty["forms_for_route"] = forms_for_route

    if not matched_strength:
        return empty

    # Prefer strict indexed catalog intersections when the catalog DB is present.
    # Never invent template/seed options via this path when indexed relations exist.
    strict_used = False
    dose_opts: list[str] = []
    dose_src = "FDA_SPL_none"
    dose_evidence: list[dict[str, Any]] = []
    try:
        from app.services.datasets.hitl_catalog_query import query_doses

        if catalog_db and canonical_name:
            strict_meta, strict_src = query_doses(
                canonical_name, route=matched_route, strength=matched_strength
            )
            if strict_meta:
                dose_opts = [o["value"] for o in strict_meta]
                dose_src = strict_src
                dose_evidence = list(strict_meta)
                strict_used = True
    except Exception:  # noqa: BLE001
        strict_used = False

    if not strict_used:
        dose_opts, dose_src, dose_evidence = evidence_doses_for_drug_route_strength(
            canonical_name=canonical_name,
            route=matched_route,
            strength=matched_strength,
            forms=forms_for_dose,
        )
    if allow_dose_templates is None:
        try:
            from app.core.config import settings

            allow_dose_templates = bool(settings.HITL_ALLOW_DOSE_TEMPLATES)
        except Exception:  # noqa: BLE001
            allow_dose_templates = False
    # Templates never when catalog DB exists (Confirm also fail-closed separately).
    # Offline demos only: empty evidence AND HITL_ALLOW_DOSE_TEMPLATES.
    if not dose_opts and allow_dose_templates and not catalog_db:
        dose_opts, dose_src = doses_for_drug_strength_route(
            forms=forms_for_dose,
            strength=matched_strength,
            route=matched_route,
            seed_doses=seed_doses,
        )
        dose_evidence = []
    used_families = _active_form_families(forms_for_dose, matched_strength, matched_route)
    forms_used = [
        f for f in forms_for_dose if _classify_form(f) in used_families
    ][:12] or forms_for_route[:12]

    empty["dose"]["options"] = dose_opts
    empty["dose"]["option_source"] = dose_src
    empty["dose"]["evidence"] = dose_evidence
    empty["dose"]["catalog_sources"] = (
        ["FDA_SPL"] if dose_src.startswith("FDA_SPL") and dose_opts else sources
    )
    empty["dose"]["context"] = {
        "drug_matched": True,
        "route": matched_route,
        "strength": matched_strength,
        "forms_used": forms_used,
        "evidence_based": dose_src.startswith("FDA_SPL") and bool(dose_opts),
        "strict_catalog": strict_used,
    }

    if not matched_dose:
        return empty

    freq_opts: list[str] = []
    freq_src = "FDA_SPL_none"
    freq_evidence: list[dict[str, Any]] = []
    strict_freq = False
    try:
        from app.services.datasets.hitl_catalog_query import query_frequencies

        if catalog_db and canonical_name:
            f_meta, f_src = query_frequencies(
                canonical_name,
                route=matched_route,
                strength=matched_strength,
                dose=matched_dose,
            )
            if f_meta:
                freq_opts = [o["value"] for o in f_meta]
                freq_src = f_src
                freq_evidence = list(f_meta)
                strict_freq = True
    except Exception:  # noqa: BLE001
        strict_freq = False

    if not strict_freq:
        freq_opts, freq_src, freq_evidence = evidence_frequencies_for_drug_route_strength(
            canonical_name=canonical_name,
            route=matched_route,
            strength=matched_strength,
            dose=matched_dose,
        )
    if allow_freq_templates is None:
        try:
            from app.core.config import settings

            allow_freq_templates = bool(settings.HITL_ALLOW_FREQ_TEMPLATES)
        except Exception:  # noqa: BLE001
            allow_freq_templates = False
    # Templates never when catalog DB exists.
    if not freq_opts and allow_freq_templates and not catalog_db:
        freq_opts, freq_src = frequencies_for_drug_strength_dose(
            forms=forms_for_dose,
            routes=catalog_routes,
            strength=matched_strength,
            dose=matched_dose,
            route=matched_route,
            seed_frequencies=seed_frequencies,
        )
        freq_evidence = []
    empty["frequency"]["options"] = freq_opts
    empty["frequency"]["option_source"] = freq_src
    empty["frequency"]["evidence"] = freq_evidence
    empty["frequency"]["catalog_sources"] = (
        ["FDA_SPL"] if freq_src.startswith("FDA_SPL") and freq_opts else sources
    )
    empty["frequency"]["context"] = {
        "drug_matched": True,
        "route": matched_route,
        "strength": matched_strength,
        "dose": matched_dose,
        "evidence_based": freq_src.startswith("FDA_SPL") and bool(freq_opts),
        "dose_adjacent": "dose_adjacent" in str(freq_src),
        "strict_catalog": strict_freq,
    }
    return empty


def products_for_canonical(name: str | None) -> list[dict[str, Any]]:
    """Return catalog product rows (strength/form/route) for a medicine name."""
    if not name:
        return []
    try:
        from app.services.datasets.catalog_store import (
            get_medicine_by_canonical,
            list_products_for_medicine,
            catalog_has_products_table,
        )
    except Exception:  # noqa: BLE001
        return []
    if not catalog_has_products_table():
        return []
    rec = get_medicine_by_canonical(name)
    if rec is None:
        return []
    return [
        {
            "strength": p.strength,
            "dosage_form": p.dosage_form,
            "route": p.route,
            "product_ndc": p.product_ndc,
            "source": p.source,
        }
        for p in list_products_for_medicine(rec.id)
    ]


def enrich_entry_forms_routes(entry: dict[str, Any]) -> dict[str, Any]:
    entry.setdefault("forms", [])
    entry.setdefault("routes", [])
    entry.setdefault("strengths", [])
    entry.setdefault("doses", [])
    entry.setdefault("frequencies", [])
    # Prefer product-table forms/routes/strengths when diligence catalog is built
    products = products_for_canonical(entry.get("canonical_name"))
    if products:
        forms = list(entry.get("forms") or [])
        routes = list(entry.get("routes") or [])
        strengths = list(entry.get("strengths") or [])
        for p in products:
            if p.get("dosage_form") and p["dosage_form"] not in forms:
                forms.append(p["dosage_form"])
            if p.get("route") and p["route"] not in routes:
                routes.append(p["route"])
            if p.get("strength") and p["strength"] not in strengths:
                strengths.append(p["strength"])
        entry["forms"] = forms
        entry["routes"] = routes
        entry["strengths"] = strengths
        entry["products"] = products
    return entry
