"""Evidence-based route labels for HITL (no clinical merging).

Uses staged ``route_master`` / ``route_aliases`` when present; otherwise
casefold + explicit abbreviation aliases only. Never maps IV/IM/SC → Injection
or Cutaneous → Topical.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

from app.services.datasets.paths import data_dir
from app.services.datasets.route_cleaning.normalize import (
    normalize_route_key,
    preferred_display_name,
    split_route_components,
)
from app.services.datasets.route_cleaning.schema import staging_db_path

# Explicit, source-conventional abbreviations only (not fuzzy clinical equivalence).
_EXPLICIT_ABBREV: dict[str, str] = {
    "po": "oral",
    "p.o": "oral",
    "p.o.": "oral",
    "iv": "intravenous",
    "i.v": "intravenous",
    "i.v.": "intravenous",
    "im": "intramuscular",
    "i.m": "intramuscular",
    "i.m.": "intramuscular",
    "sc": "subcutaneous",
    "sq": "subcutaneous",
    "subq": "subcutaneous",
    "sl": "sublingual",
    "pr": "rectal",
    "pv": "vaginal",
}


@lru_cache(maxsize=1)
def _staging_maps() -> tuple[dict[str, str], dict[str, str]] | None:
    """Return (alias_normalized→route_name, key→route_name) or None if staging missing."""
    path = staging_db_path(data_dir())
    if not path.exists() or path.stat().st_size <= 0:
        return None
    try:
        con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        aliases: dict[str, str] = {}
        names: dict[str, str] = {}
        for row in con.execute(
            """
            SELECT a.alias_normalized, m.route_name, m.route_name_normalized
            FROM route_aliases a
            JOIN route_master m ON m.route_id = a.route_id
            WHERE m.is_active = 1
            """
        ):
            aliases[row[0]] = row[1]
            names[row[2]] = row[1]
        for row in con.execute(
            "SELECT route_name_normalized, route_name FROM route_master WHERE is_active = 1"
        ):
            names[row[0]] = row[1]
        con.close()
        if not names:
            return None
        return aliases, names
    except sqlite3.Error:
        return None


def clear_route_cache() -> None:
    _staging_maps.cache_clear()


def resolve_route_key(raw: str | None) -> str | None:
    """Normalized key for one atomic route (abbrev expanded)."""
    if not raw or not str(raw).strip():
        return None
    key = normalize_route_key(str(raw))
    if not key or key in {"not applicable", "n/a", "na", "none"}:
        return None
    if key in _EXPLICIT_ABBREV:
        return _EXPLICIT_ABBREV[key]
    maps = _staging_maps()
    if maps:
        aliases, names = maps
        if key in aliases:
            return normalize_route_key(aliases[key])
        if key in names:
            return key
    return key


def display_route_label(raw: str | None) -> str | None:
    """Canonical display name for an atomic route component."""
    key = resolve_route_key(raw)
    if not key:
        return None
    maps = _staging_maps()
    if maps:
        aliases, names = maps
        if key in names:
            return names[key]
        # alias raw may resolve to display via alias table
        alias_key = normalize_route_key(str(raw))
        if alias_key in aliases:
            return aliases[alias_key]
    # Fallback: prefer non-upper title-ish from the raw token
    token = str(raw).strip()
    if ";" in token:
        # caller should split; use first component only if misused
        parts = split_route_components(token)
        token = parts[0] if parts else token
    return preferred_display_name({token}) or token


def atomic_route_labels(raw: str | None) -> list[str]:
    """Split multi-route evidence into distinct display labels (order preserved, deduped)."""
    if not raw or not str(raw).strip():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for comp in split_route_components(str(raw)):
        label = display_route_label(comp)
        key = resolve_route_key(comp)
        if not label or not key or key in seen:
            continue
        seen.add(key)
        out.append(label)
    return out


def routes_equivalent(a: str | None, b: str | None) -> bool:
    """True if two route strings share the same evidence key (no clinical merge)."""
    ka = resolve_route_key(a)
    kb = resolve_route_key(b)
    if ka and kb and ka == kb:
        return True
    # Multi-route product vs single selected route
    a_keys = {resolve_route_key(c) for c in split_route_components(a or "")}
    b_keys = {resolve_route_key(c) for c in split_route_components(b or "")}
    a_keys.discard(None)
    b_keys.discard(None)
    if not a_keys or not b_keys:
        return False
    return bool(a_keys & b_keys)


def product_matches_selected_route(product_route: str | None, selected: str | None) -> bool:
    """Product row matches HITL-selected route if selected key ∈ product components."""
    if not selected:
        return False
    sel = resolve_route_key(selected)
    if not sel:
        return False
    comps = split_route_components(product_route or "")
    if not comps and product_route:
        comps = [str(product_route)]
    for c in comps:
        if resolve_route_key(c) == sel:
            return True
    return False
