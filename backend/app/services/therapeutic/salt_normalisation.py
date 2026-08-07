"""Salt / base / ester normalisation for Sprint 1 (decision-support only).

Does not silently replace OCR values — returns a suggestion envelope for HITL.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# U6 — base_ingredient -> accepted salt/ester/hydrate surface forms (normalised keys).
# This curated map is now a small hand-verified OVERRIDE; the primary, data-driven
# source is the DrugBank-derived `salt_forms` catalogue table (see resolve_moiety).
_MOIETY_FORMS: dict[str, set[str]] = {
    "cetirizine": {
        "cetirizine",
        "cetirizine hydrochloride",
        "cetirizine dihydrochloride",
        "cetirizine hcl",
    },
    "amlodipine": {
        "amlodipine",
        "amlodipine besylate",
        "amlodipine besilate",
        "amlodipine maleate",
    },
    "diclofenac": {
        "diclofenac",
        "diclofenac sodium",
        "diclofenac potassium",
        "diclofenac diethylamine",
    },
    "metformin": {
        "metformin",
        "metformin hydrochloride",
        "metformin hcl",
    },
    "omeprazole": {
        "omeprazole",
        "omeprazole magnesium",
        "omeprazole sodium",
    },
    "pantoprazole": {
        "pantoprazole",
        "pantoprazole sodium",
        "pantoprazole sodium sesquihydrate",
    },
    "ibuprofen": {"ibuprofen"},
    "naproxen": {"naproxen", "naproxen sodium"},
    "loratadine": {"loratadine"},
    "paracetamol": {"paracetamol", "acetaminophen"},
    "acetaminophen": {"acetaminophen", "paracetamol"},
    "amoxicillin": {"amoxicillin", "amoxicillin trihydrate"},
    "sertraline": {"sertraline", "sertraline hydrochloride", "sertraline hcl"},
    "fluoxetine": {"fluoxetine", "fluoxetine hydrochloride", "fluoxetine hcl"},
    "losartan": {"losartan", "losartan potassium"},
    "atorvastatin": {"atorvastatin", "atorvastatin calcium"},
}

# reverse lookup: surface form -> base
_FORM_TO_BASE: dict[str, str] = {}
for _base, forms in _MOIETY_FORMS.items():
    for f in forms:
        _FORM_TO_BASE[f] = _base


@lru_cache(maxsize=1)
def _catalogue_salt_map() -> dict[str, tuple[str, str | None]]:
    """DrugBank-derived salt→base map from the catalogue `salt_forms` table.

    Returns {form_key: (base_key, salt_token)}. Empty (falls back to the curated
    map + heuristics) when the table is absent — keeps older catalogues working.
    """
    try:
        from app.services.datasets.paths import catalog_db_path

        con = sqlite3.connect(f"file:{catalog_db_path()}?mode=ro", uri=True)
        try:
            rows = con.execute("SELECT form_key, base_key, salt_token FROM salt_forms").fetchall()
        finally:
            con.close()
        return {fk: (bk, st) for fk, bk, st in rows if fk and bk}
    except Exception as exc:  # noqa: BLE001 - table may not exist on older catalogues
        logger.info("salt_forms table unavailable (%s); using curated map + heuristics.", exc)
        return {}


_SALT_TOKENS = (
    "hydrochloride",
    "dihydrochloride",
    "hcl",
    "besylate",
    "besilate",
    "maleate",
    "sodium",
    "potassium",
    "magnesium",
    "calcium",
    "diethylamine",
    "trihydrate",
    "sesquihydrate",
    "hydrate",
    "mesylate",
    "succinate",
    "fumarate",
    "tartrate",
    "acetate",
    "phosphate",
    "sulfate",
    "sulphate",
)


def normalize_key(value: str | None) -> str:
    if not value:
        return ""
    s = value.lower().replace("-", " ").replace(",", " ")
    s = re.sub(r"[^a-z0-9\s/]", " ", s)
    return " ".join(s.split())


def _detect_salt(form_key: str, base: str) -> str | None:
    remainder = form_key
    if form_key.startswith(base):
        remainder = form_key[len(base) :].strip()
    if not remainder:
        return None
    for tok in _SALT_TOKENS:
        if tok in remainder:
            return tok
    return remainder or None


def resolve_moiety(name: str | None) -> dict[str, Any]:
    """Map a medicine name to base ingredient + optional salt/ester."""
    key = normalize_key(name)
    warnings: list[str] = []
    if not key:
        return {
            "base_ingredient": None,
            "salt_or_ester": None,
            "canonical_ingredient_name": None,
            "match_method": "empty",
            "confidence": 0.0,
            "warnings": ["Empty medicine name"],
        }

    if key in _FORM_TO_BASE:
        base = _FORM_TO_BASE[key]
        salt = _detect_salt(key, base)
        return {
            "base_ingredient": base,
            "salt_or_ester": salt,
            "canonical_ingredient_name": base.title() if not salt else f"{base} {salt}".title(),
            "match_method": "salt_map_exact",
            "confidence": 0.95,
            "warnings": warnings,
        }

    # U6 — data-driven salt map from DrugBank (thousands of ingredients, not the
    # curated 16). High confidence: this is a source-data salt→base relationship.
    cat_map = _catalogue_salt_map()
    if key in cat_map:
        base, salt = cat_map[key]
        return {
            "base_ingredient": base,
            "salt_or_ester": salt or _detect_salt(key, base),
            "canonical_ingredient_name": base.title() if not salt else f"{base} {salt}".title(),
            "match_method": "salt_map_drugbank",
            "confidence": 0.9,
            "warnings": warnings,
        }

    # Prefix / contains match against known forms (longest first)
    for form in sorted(_FORM_TO_BASE.keys(), key=len, reverse=True):
        if key == form or key.startswith(form + " ") or f" {form}" in f" {key}":
            base = _FORM_TO_BASE[form]
            salt = _detect_salt(form, base)
            warnings.append("Matched via partial/token salt map — pharmacist confirmation required")
            return {
                "base_ingredient": base,
                "salt_or_ester": salt,
                "canonical_ingredient_name": base.title(),
                "match_method": "salt_map_partial",
                "confidence": 0.75,
                "warnings": warnings,
            }

    # Heuristic: strip trailing salt tokens
    tokens = key.split()
    stripped = tokens[:]
    salt_found = None
    while stripped and stripped[-1] in _SALT_TOKENS:
        salt_found = stripped.pop()
    guess = " ".join(stripped) if stripped else key
    if salt_found and guess:
        warnings.append("Heuristic salt strip — active moiety not in curated map")
        return {
            "base_ingredient": guess,
            "salt_or_ester": salt_found,
            "canonical_ingredient_name": guess.title(),
            "match_method": "heuristic_salt_strip",
            "confidence": 0.45,
            "warnings": warnings,
        }

    warnings.append("Active moiety not verified in curated salt/base map")
    return {
        "base_ingredient": key,
        "salt_or_ester": None,
        "canonical_ingredient_name": (name or "").strip() or key,
        "match_method": "passthrough",
        "confidence": 0.3,
        "warnings": warnings,
    }


def same_active_moiety(name_a: str | None, name_b: str | None) -> tuple[bool, str]:
    """Return (compatible, reason_code_or_ok)."""
    a = resolve_moiety(name_a)
    b = resolve_moiety(name_b)
    if not a["base_ingredient"] or not b["base_ingredient"]:
        return False, "ACTIVE_MOIETY_UNVERIFIED"
    if a["confidence"] < 0.5 or b["confidence"] < 0.5:
        # Still allow if bases equal after passthrough/heuristic and strings share root
        if a["base_ingredient"] == b["base_ingredient"] and a["match_method"] != "passthrough":
            pass
        elif a["base_ingredient"] != b["base_ingredient"]:
            return False, "ACTIVE_MOIETY_UNVERIFIED"
        else:
            if a["match_method"] == "passthrough" and b["match_method"] == "passthrough":
                return False, "ACTIVE_MOIETY_UNVERIFIED"
    if a["base_ingredient"] != b["base_ingredient"]:
        # acetaminophen / paracetamol alias
        aliases = {"acetaminophen", "paracetamol"}
        if not ({a["base_ingredient"], b["base_ingredient"]} <= aliases):
            return False, "ACTIVE_INGREDIENT_MISMATCH"
    if a["confidence"] < 0.5 or b["confidence"] < 0.5:
        return False, "SALT_RELATIONSHIP_UNVERIFIED"
    return True, "OK"


def normalize_medicine_suggestion(
    *,
    input_value: str | None,
    source: str = "salt_map",
) -> dict[str, Any]:
    """Normalisation suggestion for UI — never silently replaces OCR."""
    moiety = resolve_moiety(input_value)
    canonical = moiety.get("canonical_ingredient_name") or input_value
    return {
        "input_value": input_value,
        "canonical_value": canonical,
        "base_ingredient": moiety.get("base_ingredient"),
        "salt_or_ester": moiety.get("salt_or_ester"),
        "match_method": moiety.get("match_method"),
        "confidence": moiety.get("confidence"),
        "source": source,
        "warnings": list(moiety.get("warnings") or []),
        "ui_label": "Suggested normalisation — pharmacist confirmation required",
    }


def infer_release_type(form: str | None, name: str | None = None) -> str:
    text = normalize_key(f"{form or ''} {name or ''}")
    if any(
        t in text
        for t in (
            "extended release",
            "extended-release",
            "modified release",
            "modified-release",
            "sustained release",
            "delayed release",
            "er ",
            " xr",
            " xl",
            " sr",
            "cr ",
            "mr ",
        )
    ) or text.endswith(" er") or text.endswith(" xr") or text.endswith(" xl"):
        return "modified_release"
    if "immediate" in text:
        return "immediate_release"
    return "unspecified"


def infer_combination(name: str | None, ingredient_text: str | None = None) -> bool | None:
    text = normalize_key(f"{name or ''} {ingredient_text or ''}")
    if not text:
        return None
    if " and " in text or "/" in text or ";" in text or " with " in text:
        # Avoid flagging salt names
        if any(s in text for s in ("hydrochloride", "besylate", "sodium", "potassium")):
            # combination if multiple distinct actives likely
            if " and " in text or text.count("/") >= 1:
                parts = re.split(r"\s+and\s+|/", text)
                if len([p for p in parts if p.strip()]) >= 2:
                    # Check if second part is only a salt token
                    return not all(
                        normalize_key(p) in _SALT_TOKENS or not p.strip() for p in parts[1:]
                    )
        return True
    return False
