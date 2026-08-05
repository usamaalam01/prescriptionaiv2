"""Catalog overview + medicine lookup for award-grade dataset provenance UI."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.services.datasets.catalog_store import catalog_available, catalog_db_path, get_meta
from app.services.datasets.indication_options import catalog_indication_options
from app.services.datasets.match import suggest_medicines
from app.services.datasets.models import DISCLAIMER
from app.services.formulary_catalog import normalize
from app.services.retention import retention_policy


def catalog_overview() -> dict[str, Any]:
    ready = catalog_available()
    meta = get_meta() if ready else {}
    stats: dict[str, Any] = {}
    if meta.get("stats"):
        try:
            stats = json.loads(meta["stats"])
        except json.JSONDecodeError:
            stats = {}
    return {
        "available": ready,
        "catalog_db": str(catalog_db_path()) if ready else None,
        "built_at": meta.get("built_at"),
        "disclaimer": DISCLAIMER,
        "intended_use": (
            "Pharmacist decision-support only. Dataset matches are evidence for HITL confirmation, "
            "not automatic clinical decisions."
        ),
        "retention": retention_policy(),
        "sources": [
            {
                "id": "FDA_NDC",
                "label": "FDA National Drug Code",
                "role": "Product strengths, forms, routes, NDC product rows",
                "rows_ingested": stats.get("ndc"),
            },
            {
                "id": "DrugBank",
                "label": "DrugBank",
                "role": "Canonical names, synonyms, products, indication sections",
                "rows_ingested": stats.get("drugbank"),
            },
            {
                "id": "FDA_SPL",
                "label": "FDA Structured Product Labeling",
                "role": "Label diligence sections + openFDA identity/routes",
                "rows_ingested": stats.get("spl"),
                "shards": stats.get("spl_shards")
                or (stats.get("source_files") or {}).get("spl"),
            },
        ],
        "unified": {
            "medicines": stats.get("medicines"),
            "aliases": stats.get("aliases"),
            "products": stats.get("products"),
            "label_sections": stats.get("label_sections"),
            "full_data": stats.get("full_data"),
            "full_diligence": stats.get("full_diligence"),
            "build_seconds": stats.get("seconds"),
        },
    }


def lookup_medicine(query: str, *, top_k: int = 8) -> dict[str, Any]:
    """Return ranked catalog hits plus detail for the best exact/canonical match."""
    q = (query or "").strip()
    if not q:
        return {"query": q, "candidates": [], "selected": None, "disclaimer": DISCLAIMER}
    if not catalog_available():
        return {
            "query": q,
            "candidates": [],
            "selected": None,
            "disclaimer": DISCLAIMER,
            "error": "Catalog not built",
        }

    hits = suggest_medicines(q, top_k=top_k)
    candidates = [
        {
            "canonical_name": h.canonical_name,
            "score": h.score,
            "source": h.source,
            "strengths": h.strengths[:20],
            "dosage_forms": h.dosage_forms[:12],
            "routes": h.routes[:12],
            "drugbank_id": h.drugbank_id,
            "product_ndc": h.product_ndc,
            "matched_alias": h.matched_alias,
            "reason": h.reason,
            "brand_names": h.brand_names[:8],
        }
        for h in hits
    ]

    selected = None
    key = normalize(q)
    best = next((h for h in hits if normalize(h.canonical_name) == key), hits[0] if hits else None)
    if best is not None:
        detail = _medicine_detail(best.canonical_name)
        base = next(
            (
                c
                for c in candidates
                if normalize(c["canonical_name"]) == normalize(best.canonical_name)
            ),
            {
                "canonical_name": best.canonical_name,
                "score": best.score,
                "source": best.source,
                "strengths": best.strengths[:20],
                "dosage_forms": best.dosage_forms[:12],
                "routes": best.routes[:12],
                "drugbank_id": best.drugbank_id,
                "product_ndc": best.product_ndc,
                "matched_alias": best.matched_alias,
                "reason": best.reason,
                "brand_names": best.brand_names[:8],
            },
        )
        selected = {
            **base,
            "indication_options": catalog_indication_options(best.canonical_name),
            "indication_snippet": (detail or {}).get("indication_snippet"),
            "sources_list": (detail or {}).get("sources_list") or str(best.source).split("+"),
            "aliases_sample": (detail or {}).get("aliases_sample") or [],
        }

    return {
        "query": q,
        "candidates": candidates,
        "selected": selected,
        "disclaimer": DISCLAIMER,
        "note": "Top candidates only — pharmacist must confirm. No silent auto-select.",
    }


def _medicine_detail(canonical_name: str) -> dict[str, Any] | None:
    from app.services.datasets.catalog_store import _connect

    key = normalize(canonical_name)
    try:
        conn = _connect()
    except Exception:  # noqa: BLE001
        return None
    try:
        row = conn.execute(
            """
            SELECT m.id, m.canonical_name, m.indication, m.sources, m.drugbank_id, m.product_ndc
            FROM medicines m
            JOIN aliases a ON a.medicine_id = m.id
            WHERE a.alias_key = ?
            ORDER BY CASE WHEN lower(m.canonical_name) = ? THEN 0 ELSE 1 END, length(m.canonical_name)
            LIMIT 1
            """,
            (key, key),
        ).fetchone()
        if not row:
            return None
        aliases = [
            r[0]
            for r in conn.execute(
                "SELECT alias_raw FROM aliases WHERE medicine_id=? ORDER BY alias_raw LIMIT 12",
                (row["id"],),
            ).fetchall()
        ]
        try:
            sources_list = json.loads(row["sources"] or "[]")
        except json.JSONDecodeError:
            sources_list = []
        snippet = (row["indication"] or "")[:280]
        return {
            "indication_snippet": snippet or None,
            "sources_list": sources_list,
            "aliases_sample": aliases,
            "drugbank_id": row["drugbank_id"],
            "product_ndc": row["product_ndc"],
        }
    finally:
        conn.close()
