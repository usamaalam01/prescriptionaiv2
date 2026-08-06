"""Build the `smiles_by_name` table in medicine_catalog.sqlite3 (Spec O3 / DQ2).

Populates a normalised ingredient-name -> canonical SMILES map used by the RDKit
MCS structural signal (app/services/therapeutic/smiles_catalog.py). Source is the
DrugBank-derived structures cache (name / synonyms / smiles). Salt-normalised keys
are added so catalogue names like "Hydroxyzine Hydrochloride" resolve to the base
ingredient's SMILES.

Usage:
    python -m scripts.build_smiles_table [path_to_drugbank_parsed.pkl]

Default source: the prescription project's drugbank_parsed.pkl. To regenerate from
raw DrugBank XML instead, parse name/synonyms/<calculated-property kind="SMILES">
into the same {name: {"name","synonyms","smiles"}} shape and pass its pickle path.
"""

from __future__ import annotations

import pickle
import sqlite3
import sys
from pathlib import Path

from app.services.datasets.paths import catalog_db_path

# Reuse the resolver's normalisation so the builder's keys always match the lookup
# keys (single source of truth — no salt-regex drift between build and query).
from app.services.therapeutic.smiles_catalog import _nkey, _strip_salt

_DEFAULT_SOURCE = Path("D:/AI Learning/AIPrescription/prescription/data/drugbank_parsed.pkl")


def build(source: Path) -> None:
    if not source.exists():
        raise SystemExit(f"DrugBank structures source not found: {source}")
    data = pickle.loads(source.read_bytes())

    rows: dict[str, str] = {}
    for name, v in data.items():
        if not isinstance(v, dict) or not v.get("smiles"):
            continue
        smiles = v["smiles"]
        candidates = [v.get("name") or name] + (v.get("synonyms") or [])
        for nm in candidates:
            for key in {_nkey(nm), _strip_salt(_nkey(nm))}:
                if key:
                    rows.setdefault(key, smiles)

    db = str(catalog_db_path())
    con = sqlite3.connect(db)
    try:
        con.execute("DROP TABLE IF EXISTS smiles_by_name")
        con.execute(
            "CREATE TABLE smiles_by_name (name_key TEXT PRIMARY KEY, smiles TEXT NOT NULL)"
        )
        con.executemany(
            "INSERT OR IGNORE INTO smiles_by_name(name_key, smiles) VALUES (?, ?)",
            list(rows.items()),
        )
        con.commit()
        # Report coverage against catalogue medicines (informational).
        cat = [_nkey(r[0]) for r in con.execute("SELECT canonical_name FROM medicines")]
        keys = set(rows)

        def _covered(nm: str) -> bool:
            if nm in keys:
                return True
            ks = _strip_salt(nm)
            return ks in keys or (bool(ks.split()) and ks.split()[0] in keys)

        cov = sum(1 for nm in cat if _covered(nm))
        print(f"smiles_by_name rows: {len(rows)}")
        print(f"catalogue coverage:  {cov}/{len(cat)} ({100 * cov // max(len(cat), 1)}%)")
    finally:
        con.close()


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_SOURCE
    build(src)
