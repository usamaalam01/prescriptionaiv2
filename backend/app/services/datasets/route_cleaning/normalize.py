"""Safe route text normalization (matching keys — not Title Case)."""

from __future__ import annotations

import re
import unicodedata

_SPLIT_RE = re.compile(r"\s*;\s*")

# Broad↔specific pairs that must never auto-merge (illustrative; keys are casefold)
CLINICALLY_DISTINCT_PAIRS: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"cutaneous", "topical"}),
        frozenset({"ophthalmic", "conjunctival"}),
        frozenset({"oral", "buccal"}),
        frozenset({"oral", "sublingual"}),
        frozenset({"intravenous", "intravascular"}),
        frozenset({"epidural", "intrathecal"}),
        frozenset({"auricular (otic)", "intratympanic"}),
        frozenset({"respiratory (inhalation)", "intrabronchial"}),
        frozenset({"dental", "periodontal"}),
    }
)


def normalize_route_key(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value.casefold()


def split_route_components(raw: str | None) -> list[str]:
    """Split multi-route FDA strings on `;`. Does not choose a single preferred route."""
    raw_s = unicodedata.normalize("NFKC", raw or "").replace("\u00a0", " ")
    raw_s = re.sub(r"\s+", " ", raw_s).strip()
    if not raw_s:
        return []
    return [p.strip() for p in _SPLIT_RE.split(raw_s) if p.strip()]


def preferred_display_name(variants: set[str] | list[str]) -> str:
    """Pick a stable display label among case variants (not used for matching)."""
    vals = [v for v in variants if v and str(v).strip()]
    if not vals:
        return ""
    # Prefer mixed/title over ALL CAPS
    non_upper = [v for v in vals if not v.isupper()]
    pool = non_upper or vals
    return sorted(pool, key=lambda s: (len(s), s.lower()))[0]


def dosage_form_conflict(route_key: str, form: str | None) -> str | None:
    """Flag only — never auto-correct."""
    if not form:
        return None
    f = normalize_route_key(form)
    r = route_key
    if any(x in f for x in ("tablet", "capsule", "caplet")) and r in {
        "topical",
        "ophthalmic",
        "otic",
        "auricular (otic)",
        "vaginal",
        "rectal",
    }:
        return "ROUTE_DOSAGE_FORM_CONFLICT"
    if any(x in f for x in ("ointment", "cream", "gel")) and r in {
        "oral",
        "intravenous",
        "intramuscular",
        "subcutaneous",
    }:
        return "ROUTE_DOSAGE_FORM_CONFLICT"
    if any(x in f for x in ("injection", "injectable")) and r in {
        "oral",
        "topical",
        "ophthalmic",
    }:
        return "ROUTE_DOSAGE_FORM_CONFLICT"
    return None


def route_code_from_key(key: str) -> str:
    """Stable route_code from normalized key."""
    code = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return (code or "unknown")[:120]
