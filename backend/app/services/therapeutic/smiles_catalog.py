"""Catalogue-backed SMILES lookup for RDKit MCS (Spec O3).

The medicine catalogue (`medicine_catalog.sqlite3`) carries a `smiles_by_name`
table (built from DrugBank structures) mapping a normalised ingredient key →
canonical SMILES. This resolver salt-normalises the query name and falls back to
the first ingredient token, then to the small hardcoded seed. Read-only; cached.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from functools import lru_cache

from app.services.datasets.paths import catalog_db_path
from app.services.therapeutic.smiles_seed import lookup_smiles as _seed_lookup

logger = logging.getLogger(__name__)

_SALT_WORDS = (
    r"\b(hydrochloride|hcl|sodium|potassium|calcium|magnesium|sulfate|sulphate|"
    r"phosphate|maleate|besylate|mesylate|tartrate|succinate|fumarate|citrate|"
    r"acetate|bromide|chloride|nitrate|dihydrate|trihydrate|monohydrate|hydrate|"
    r"hydrobromide|tosylate|estolate|valerate|propionate|dipropionate|base)\b"
)


def _nkey(s: str | None) -> str:
    if not s:
        return ""
    return " ".join(str(s).lower().replace("-", " ").split())


def _strip_salt(k: str) -> str:
    return " ".join(re.sub(_SALT_WORDS, " ", k).split())


@lru_cache(maxsize=1)
def _name_smiles_map() -> dict[str, str]:
    """Load the catalogue's smiles_by_name table once. Empty if table absent."""
    try:
        con = sqlite3.connect(f"file:{catalog_db_path()}?mode=ro", uri=True)
        try:
            rows = con.execute("SELECT name_key, smiles FROM smiles_by_name").fetchall()
        finally:
            con.close()
        return {k: v for k, v in rows if k and v}
    except Exception as exc:  # noqa: BLE001 - table may not exist on older catalogues
        logger.info("smiles_by_name unavailable (%s); using seed only.", exc)
        return {}


def resolve_smiles_catalog(*, drugbank_id: str | None, name: str | None) -> str | None:
    """Catalogue SMILES for a medicine; seed fallback. None if unresolved."""
    # Seed first for the curated demo drugs (exact, hand-verified).
    seeded = _seed_lookup(drugbank_id=drugbank_id, name=name)
    if seeded:
        return seeded

    smap = _name_smiles_map()
    if not smap or not name:
        return None
    k = _nkey(name)
    if k in smap:
        return smap[k]
    # Salt-normalise — but only if stripping leaves a real ingredient. Names composed
    # only of salt words (e.g. "sodium chloride", "potassium chloride") strip to empty
    # or to a bare counter-ion; do NOT resolve those to a wrong/partial molecule.
    ks = _strip_salt(k)
    if ks and ks != k and ks in smap:
        return smap[ks]
    # Single-ingredient first-token fallback ONLY (never for combinations like
    # "amoxicillin clavulanate", where a single-component SMILES would be misleading).
    tokens = ks.split()
    if len(tokens) == 1 and tokens[0] in smap:
        return smap[tokens[0]]
    return None
