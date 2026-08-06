"""FDA Orange Book therapeutic-equivalence lookup (Spec U-TE).

The Orange Book `TE_Code` is the *regulatory* therapeutic-equivalence rating that
NDC/DrugBank/SPL do not encode. This resolves a medicine (ingredient + dosage
form + route + strength) to its FDA TE status.

Safety rules honoured:
- ``A*`` codes = therapeutically equivalent / substitutable; ``B*`` = NOT; empty
  = single-source / innovator (no equivalence to assert).
- **Subletter is scoped:** AB1 ≠ AB2 ≠ AB3 — equivalence holds only within the same
  subletter subgroup (relative to the same reference product).
- **DISCN** (discontinued) products are flagged and excluded from "available
  equivalent" claims.

Decision-support evidence only — never an automatic substitution instruction. The
pharmacist (HITL) remains the decision-maker.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.services.datasets.paths import catalog_db_path
from app.services.therapeutic.smiles_catalog import _nkey, _strip_salt

logger = logging.getLogger(__name__)


def _strength_key(strength: str | None) -> str:
    s = (strength or "").split("**", 1)[0]
    return " ".join(s.lower().replace(" ", "").split())


@lru_cache(maxsize=1)
def _table_available() -> bool:
    try:
        con = sqlite3.connect(f"file:{catalog_db_path()}?mode=ro", uri=True)
        try:
            con.execute("SELECT 1 FROM orange_products LIMIT 1")
            return True
        finally:
            con.close()
    except Exception:
        return False


def orange_book_available() -> bool:
    return bool(settings.ENABLE_ORANGE_BOOK) and _table_available()


def _query(sql: str, params: tuple) -> list[dict[str, Any]]:
    con = sqlite3.connect(f"file:{catalog_db_path()}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def _te_bucket(code: str) -> str:
    if not code:
        return "single_source"
    if code.startswith("A"):
        return "therapeutically_equivalent"
    if code.startswith("B"):
        return "not_equivalent"
    return "other"


def _subletter_group(code: str) -> str | None:
    """AB1 -> 'AB1'; the subletter-scoped substitution group (None if no code)."""
    return code or None


def te_status_for(
    *,
    ingredient: str | None,
    dosage_form: str | None = None,
    route: str | None = None,
    strength: str | None = None,
) -> dict[str, Any]:
    """Resolve FDA Orange Book therapeutic-equivalence status for a medicine.

    Returns a decision-support block. Narrows by dosage_form/route/strength when
    given (the pharmaceutical-equivalence group); otherwise returns the ingredient
    view. ``available`` is False when Orange Book is disabled/absent or the
    ingredient is not in the Orange Book.
    """
    base: dict[str, Any] = {
        "available": False,
        "source": "FDA Orange Book",
        "ingredient_matched": False,
        "te_codes": [],
        "substitutable": None,
        "subletter_groups": [],
        "reference_listed_drug": None,
        "reference_standard": None,
        "single_source": None,
        "discontinued_only": None,
        "n_products": 0,
        "note": (
            "FDA therapeutic-equivalence rating. A-codes = substitutable within the same "
            "subletter subgroup vs the reference; empty = single-source/innovator. "
            "Decision support only — not an automatic substitution instruction; pharmacist verifies."
        ),
    }
    if not orange_book_available() or not ingredient:
        base["note"] = "Orange Book unavailable or no ingredient supplied." if not ingredient else base["note"]
        return base

    ing = _nkey(ingredient)
    ing_base = _strip_salt(ing)

    # Match on ingredient (exact or salt-stripped), then narrow the PE group.
    where = ["(ing_key = ? OR ing_base_key = ?)"]
    params: list[Any] = [ing, ing_base]
    if dosage_form:
        where.append("df = ?")
        params.append(_nkey(dosage_form))
    if route:
        where.append("route = ?")
        params.append(_nkey(route))
    if strength:
        where.append("strength_key = ?")
        params.append(_strength_key(strength))

    rows = _query(
        f"SELECT te_code, type, rld, rs, trade_name, applicant FROM orange_products WHERE {' AND '.join(where)}",
        tuple(params),
    )
    if not rows:
        # Fall back to ingredient-only view (still useful evidence) if the narrowed
        # group was empty but the ingredient exists at all.
        rows_any = _query(
            "SELECT te_code, type, rld, rs, trade_name, applicant FROM orange_products "
            "WHERE ing_key = ? OR ing_base_key = ?",
            (ing, ing_base),
        )
        if not rows_any:
            base["note"] = "Ingredient not found in the FDA Orange Book (US-approved systemic drugs only)."
            return base
        rows = rows_any
        base["note"] = "No exact form/route/strength match; showing ingredient-level Orange Book status. " + base["note"]

    return _summarise_rows(rows, base)


def _summarise_rows(rows: list[dict[str, Any]], base: dict[str, Any]) -> dict[str, Any]:
    live = [r for r in rows if (r.get("type") or "").strip() != "DISCN"]
    codes = sorted({(r.get("te_code") or "").strip() for r in live if (r.get("te_code") or "").strip()})
    a_codes = [c for c in codes if c.startswith("A")]
    rs = next((r["trade_name"] for r in rows if (r.get("rs") or "").strip() == "Yes"), None)

    # SUBLETTER SAFETY: A-codes like AB1/AB2/AB3 are NOT mutually substitutable — each
    # subletter is its own equivalence group vs its own Reference Listed Drug. Build
    # per-subgroup detail so callers never treat mixed subletters as one interchangeable
    # set. NOTE on RLDs: in the Orange Book the RLD is the *reference* (empty TE code),
    # not an A-rated row — so the RLD(s) live among the group's non-A-code rows, and the
    # data does not directly map each subletter to its specific RLD. We therefore list
    # the group's RLD brand(s) at group level and keep A-rated PRODUCTS per subletter.
    rld_brands = sorted({r["trade_name"] for r in rows if (r.get("rld") or "").strip() == "Yes" and r.get("trade_name")})
    subgroups: list[dict[str, Any]] = []
    for code in a_codes:
        grp_rows = [r for r in live if (r.get("te_code") or "").strip() == code]
        subgroups.append(
            {
                "te_code": code,
                "products": sorted({r["trade_name"] for r in grp_rows if r.get("trade_name")}),
                "n_products": len(grp_rows),
            }
        )
    multiple_subgroups = len(subgroups) > 1
    # A single unambiguous RLD only when there's exactly one; else expose the set.
    rld = rld_brands[0] if len(rld_brands) == 1 else None

    base.update(
        {
            "available": True,
            "ingredient_matched": True,
            "te_codes": codes,
            "buckets": sorted({_te_bucket(c) for c in codes}) or ["single_source"],
            # "substitutable" means an A-rated product exists — but ONLY within a matching
            # subletter subgroup. When there are multiple subgroups, substitution is
            # subgroup-scoped (see subletter_subgroups); it is NOT a blanket True.
            "substitutable": bool(a_codes),
            "substitution_scope": (
                "subletter_scoped" if multiple_subgroups else ("group" if a_codes else "none")
            ),
            "subletter_subgroups": subgroups,  # per-subgroup: code, RLD, products (mutually distinct)
            "subletter_warning": (
                "Multiple TE subletters present (e.g. AB1/AB2/AB3) — substitute ONLY within the "
                "same subletter and reference product; these subgroups are NOT interchangeable."
                if multiple_subgroups
                else None
            ),
            "reference_listed_drug": rld,  # single RLD only when unambiguous
            "reference_listed_drugs": rld_brands,  # all RLD brand(s) in the group (empty-TE references)
            "reference_standard": rs,
            "single_source": (not codes and bool(live)),  # live products but no TE code = single-source
            "discontinued_only": (not live and bool(rows)),
            "n_products": len(rows),
            "n_live_products": len(live),
        }
    )
    return base


def orange_book_gold(
    *,
    ingredient: str | None,
    dosage_form: str | None = None,
    route: str | None = None,
    strength: str | None = None,
) -> dict[str, Any]:
    """DQ2 regulatory gold standard: the A-rated products in a reference's PE group.

    Returns the set of live (non-DISCN) A-rated trade names as the *regulatory*
    relevant-set for Precision@K/Recall@K — a defensible ground truth that the
    prescription NDC/DrugBank/SPL data cannot provide. ``available`` is False when
    Orange Book is off/absent or the ingredient is not found.
    """
    out: dict[str, Any] = {
        "available": False,
        "source": "FDA Orange Book",
        "reference_ingredient": ingredient,
        "a_rated_products": [],
        "subletter_groups": [],
        "n": 0,
        "note": (
            "Regulatory relevant-set = FDA A-rated products for this ingredient (DISCN excluded). "
            "Scope = whatever form/route/strength filters are supplied; when only an ingredient is "
            "given this spans ALL its forms/strengths and MIXES subletters (AB1/AB2/AB3) — narrow by "
            "form+route+strength for a true subletter-scoped pharmaceutical-equivalence group."
        ),
    }
    if not orange_book_available() or not ingredient:
        return out

    ing = _nkey(ingredient)
    ing_base = _strip_salt(ing)
    where = ["(ing_key = ? OR ing_base_key = ?)", "type != 'DISCN'", "te_code LIKE 'A%'"]
    params: list[Any] = [ing, ing_base]
    if dosage_form:
        where.append("df = ?")
        params.append(_nkey(dosage_form))
    if route:
        where.append("route = ?")
        params.append(_nkey(route))
    if strength:
        where.append("strength_key = ?")
        params.append(_strength_key(strength))

    rows = _query(
        f"SELECT DISTINCT trade_name, te_code FROM orange_products WHERE {' AND '.join(where)}",
        tuple(params),
    )
    products = sorted({r["trade_name"] for r in rows if r.get("trade_name")})
    out.update(
        {
            "available": True,
            "a_rated_products": products,
            "subletter_groups": sorted({(r.get("te_code") or "").strip() for r in rows if r.get("te_code")}),
            "n": len(products),
        }
    )
    return out
