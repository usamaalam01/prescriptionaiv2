"""Build the `salt_forms` table in medicine_catalog.sqlite3 (Spec O3 / U6).

Populates a data-driven salt→base map from DrugBank's `salt_forms` field so the
recommendation engine's salt-awareness (`salt_normalisation.resolve_moiety`) is
backed by real drug data (~2,300 base ingredients with explicit salts) instead of
a hardcoded ~16-ingredient dict.

Each row maps a normalised salt-form key (e.g. "amlodipine besylate") to its base
ingredient key ("amlodipine") plus the detected salt token.

Usage:
    python -m scripts.build_salt_forms [path_to_drugbank_parsed.pkl]

Reproducible; the table lives inside the (gitignored) catalogue sqlite.
"""

from __future__ import annotations

import pickle
import sqlite3
import sys
from pathlib import Path

from app.services.datasets.paths import catalog_db_path

# Use the SAME key function resolve_moiety() queries with, so stored keys are always
# reachable (no build-vs-query normalisation drift).
from app.services.therapeutic.salt_normalisation import normalize_key as _nkey

_DEFAULT_SOURCE = Path("D:/AI Learning/AIPrescription/prescription/data/drugbank_parsed.pkl")


def _salt_token(form_key: str, base_key: str) -> str | None:
    """The salt counter-ion of a form relative to its base (e.g. 'besylate').

    Handles the direct '<base> <salt>' case and the acid↔ate conjugate case
    (base '<root>ic acid' → form '<root>ate <counter-ion>').
    """
    if form_key == base_key:
        return None
    if form_key.startswith(base_key + " "):
        return form_key[len(base_key):].strip() or None
    # Conjugate: strip the leading '<root>ate' token, return the counter-ion.
    if base_key.endswith("ic acid"):
        root = base_key[: -len("ic acid")].strip()
        ate = root + "ate"
        if form_key.startswith(ate):
            return form_key[len(ate):].strip() or "ate"
    return None


def build(source: Path) -> None:
    if not source.exists():
        raise SystemExit(f"DrugBank structures source not found: {source}")
    data = pickle.loads(source.read_bytes())

    # salt_form_key -> (base_key, base_display, salt_token)
    rows: dict[str, tuple[str, str, str | None]] = {}
    n_bases = 0
    for name, v in data.items():
        if not isinstance(v, dict):
            continue
        salt_forms = v.get("salt_forms") or []
        if not salt_forms:
            continue
        base_display = v.get("name") or name
        base_key = _nkey(base_display)
        if not base_key:
            continue
        n_bases += 1
        # The base itself resolves to base (identity).
        rows.setdefault(base_key, (base_key, base_display, None))
        # Accept the acid↔ate conjugate pattern too: a base "<root>ic acid" whose salt
        # is "<root>ate <counter-ion>" (e.g. valproic acid ↔ valproate sodium,
        # clavulanic acid ↔ clavulanate potassium). Requires a SHARED word root, so it
        # recovers true conjugates WITHOUT re-admitting different-word non-salts
        # (NPH insulin, argipressin — no shared root, stay excluded).
        conj_root = None
        if base_key.endswith("ic acid"):
            conj_root = base_key[: -len("ic acid")].strip()  # 'valproic acid' -> 'valpro'

        for sf in salt_forms:
            sf_key = _nkey(sf)
            if not sf_key:
                continue
            # SAFETY: only accept genuine counter-ion salts of THIS base — the form is
            # "<base> <salt-word(s)>", OR the acid↔ate conjugate of a "<root>ic acid".
            # DrugBank's salt_forms also lists non-salt entities (NPH insulin under
            # insulin human, etc.); those must NOT be treated as the same active moiety.
            is_direct_salt = sf_key == base_key or sf_key.startswith(base_key + " ")
            is_conjugate = bool(conj_root) and (
                sf_key == conj_root + "ate" or sf_key.startswith(conj_root + "ate ")
            )
            if is_direct_salt or is_conjugate:
                rows.setdefault(sf_key, (base_key, base_display, _salt_token(sf_key, base_key)))

    con = sqlite3.connect(str(catalog_db_path()))
    try:
        con.execute("DROP TABLE IF EXISTS salt_forms")
        con.execute(
            """CREATE TABLE salt_forms (
                form_key TEXT PRIMARY KEY,
                base_key TEXT NOT NULL,
                base_display TEXT NOT NULL,
                salt_token TEXT
            )"""
        )
        con.executemany(
            "INSERT OR IGNORE INTO salt_forms(form_key, base_key, base_display, salt_token) VALUES (?,?,?,?)",
            [(k, b, d, s) for k, (b, d, s) in rows.items()],
        )
        con.execute("CREATE INDEX ix_salt_base ON salt_forms(base_key)")
        con.commit()
        distinct_bases = con.execute("SELECT COUNT(DISTINCT base_key) FROM salt_forms").fetchone()[0]
        print(f"salt_forms rows: {len(rows)}  (distinct base ingredients: {distinct_bases})")
    finally:
        con.close()


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_SOURCE
    build(src)
