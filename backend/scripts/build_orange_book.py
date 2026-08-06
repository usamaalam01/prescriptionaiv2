"""Ingest the FDA Orange Book into medicine_catalog.sqlite3 (Spec U-TE / DQ2).

Parses `data/orange/products.txt` (tilde-delimited) into a read-only
`orange_products` table with normalised crosswalk columns (ing_key, df, route,
strength_key) so it can be joined to catalogue medicines by Ingredient + Dosage
Form + Route + Strength. The `TE_Code` is the authoritative FDA therapeutic-
equivalence rating (A* = equivalent, B* = not, empty = single-source/innovator).

Usage:
    python -m scripts.build_orange_book [path_to_products.txt]

Reproducible; the table lives inside the (gitignored) catalogue sqlite.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from app.services.datasets.paths import catalog_db_path

# Reuse the resolver's normalisation so OB keys match catalogue lookup keys.
from app.services.therapeutic.smiles_catalog import _nkey, _strip_salt

_DEFAULT_SOURCE = Path("D:/AI Learning/AIPrescription/new/data/orange/products.txt")

# products.txt columns (tilde-delimited), in order:
_COLUMNS = [
    "ingredient", "df_route", "trade_name", "applicant", "strength",
    "appl_type", "appl_no", "product_no", "te_code", "approval_date",
    "rld", "rs", "type", "applicant_full_name",
]


def _split_df_route(df_route: str) -> tuple[str, str]:
    """'TABLET;ORAL' -> ('tablet', 'oral'). Missing route -> ('', '')."""
    parts = (df_route or "").split(";", 1)
    df = _nkey(parts[0]) if parts else ""
    route = _nkey(parts[1]) if len(parts) > 1 else ""
    return df, route


def _strength_key(strength: str) -> str:
    """Normalise a strength for matching (lowercase, spaces collapsed).

    Orange Book strengths include free-text notes after '**'; keep only the head.
    """
    s = (strength or "").split("**", 1)[0]
    return " ".join(s.lower().replace(" ", "").split())


def build(source: Path) -> None:
    if not source.exists():
        raise SystemExit(f"Orange Book products file not found: {source}")

    rows = []
    with open(source, encoding="utf-8") as f:
        header = next(f)  # skip header
        for line in f:
            parts = line.rstrip("\n").split("~")
            if len(parts) < len(_COLUMNS):
                continue
            rec = dict(zip(_COLUMNS, parts))
            df, route = _split_df_route(rec["df_route"])
            ing_key = _nkey(rec["ingredient"])
            rows.append(
                (
                    rec["ingredient"], rec["df_route"], rec["trade_name"], rec["applicant"],
                    rec["strength"], rec["appl_type"], rec["appl_no"], rec["product_no"],
                    (rec["te_code"] or "").strip(), rec["approval_date"],
                    (rec["rld"] or "").strip(), (rec["rs"] or "").strip(),
                    (rec["type"] or "").strip(), rec["applicant_full_name"],
                    ing_key, _strip_salt(ing_key), df, route, _strength_key(rec["strength"]),
                )
            )

    con = sqlite3.connect(str(catalog_db_path()))
    try:
        con.execute("DROP TABLE IF EXISTS orange_products")
        con.execute(
            """CREATE TABLE orange_products (
                ingredient TEXT, df_route TEXT, trade_name TEXT, applicant TEXT,
                strength TEXT, appl_type TEXT, appl_no TEXT, product_no TEXT,
                te_code TEXT, approval_date TEXT, rld TEXT, rs TEXT, type TEXT,
                applicant_full_name TEXT,
                ing_key TEXT, ing_base_key TEXT, df TEXT, route TEXT, strength_key TEXT
            )"""
        )
        con.executemany(
            "INSERT INTO orange_products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
        )
        con.execute("CREATE INDEX ix_ob_ing ON orange_products(ing_key)")
        con.execute("CREATE INDEX ix_ob_base ON orange_products(ing_base_key)")
        con.execute("CREATE INDEX ix_ob_group ON orange_products(ing_base_key, df, route, strength_key)")
        con.commit()

        n = con.execute("SELECT COUNT(*) FROM orange_products").fetchone()[0]
        a = con.execute("SELECT COUNT(*) FROM orange_products WHERE te_code LIKE 'A%'").fetchone()[0]
        b = con.execute("SELECT COUNT(*) FROM orange_products WHERE te_code LIKE 'B%'").fetchone()[0]
        empty = con.execute("SELECT COUNT(*) FROM orange_products WHERE te_code = ''").fetchone()[0]
        discn = con.execute("SELECT COUNT(*) FROM orange_products WHERE type = 'DISCN'").fetchone()[0]
        ings = con.execute("SELECT COUNT(DISTINCT ing_key) FROM orange_products").fetchone()[0]
        print(f"orange_products rows: {n}  (ingredients: {ings})")
        print(f"  TE_Code: A*={a}  B*={b}  empty={empty}  |  DISCN={discn}")
    finally:
        con.close()


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_SOURCE
    build(src)
