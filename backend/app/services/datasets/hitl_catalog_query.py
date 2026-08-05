"""Strict catalog-driven HITL option queries (no template / seed invention).

Cascade intersections are resolved from product and label relations:
  routes ← products.route (split + evidence casefold; no clinical merge / form inference)
  strengths ← products WHERE selected route ∈ product components
  doses ← label_dose_options medicine+route+strength
  frequencies ← label_dose_frequency_options (fallback: label_frequency_options)
  indications ← indication_options (fallback: live miner)

OCR may rank existing options elsewhere; this module never invents options.
"""

from __future__ import annotations

from typing import Any

from app.services.datasets.catalog_store import (
    catalog_available,
    catalog_has_indication_options_table,
    catalog_has_label_dose_frequency_options_table,
    catalog_has_label_dose_options_table,
    catalog_has_label_frequency_options_table,
    catalog_has_products_table,
    get_medicine_by_canonical,
    list_indication_options,
    list_label_dose_frequency_options,
    list_label_dose_options,
    list_label_frequency_options,
    list_products_for_medicine,
)
from app.services.datasets.evidence_route import (
    atomic_route_labels,
    display_route_label,
    product_matches_selected_route,
    resolve_route_key,
    routes_equivalent,
)


def _option(
    value: str,
    *,
    source: str,
    evidence_excerpt: str | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"value": value, "source": source}
    if evidence_excerpt is not None:
        out["evidence_excerpt"] = evidence_excerpt
    if confidence is not None:
        out["confidence"] = confidence
    return out


def resolve_medicine_id(canonical_name: str | None) -> int | None:
    if not canonical_name or not catalog_available():
        return None
    rec = get_medicine_by_canonical(canonical_name)
    return int(rec.id) if rec else None


def _route_display(route: str | None) -> str | None:
    if not route or not str(route).strip():
        return None
    return display_route_label(route) or str(route).strip()


def query_routes(canonical_name: str | None) -> tuple[list[dict[str, Any]], str]:
    """Routes from products.route evidence (split + casefold). No form inference / clinical merge."""
    mid = resolve_medicine_id(canonical_name)
    if mid is None:
        return [], "catalog_none"
    if not catalog_has_products_table():
        return [], "catalog_none"
    found: list[str] = []
    meta: list[dict[str, Any]] = []
    for p in list_products_for_medicine(mid):
        raw = (p.route or "").strip()
        if not raw:
            continue
        for label in atomic_route_labels(raw):
            if label in found:
                continue
            found.append(label)
            meta.append(_option(label, source=p.source or "FDA_NDC"))
    if not meta:
        return [], "products_route_none"
    return meta, "products.route"


def query_strengths(
    canonical_name: str | None,
    *,
    route: str | None,
) -> tuple[list[dict[str, Any]], str]:
    """Strengths from products for the selected route; fallback label_dose_options."""
    mid = resolve_medicine_id(canonical_name)
    route_label = _route_display(route)
    if mid is None or not route_label or not resolve_route_key(route):
        return [], "catalog_none"

    strengths: list[str] = []
    meta: list[dict[str, Any]] = []
    if catalog_has_products_table():
        for p in list_products_for_medicine(mid):
            ps = (p.strength or "").strip()
            if not ps:
                continue
            if not product_matches_selected_route(str(p.route or ""), route_label):
                continue
            if ps in strengths:
                continue
            strengths.append(ps)
            meta.append(_option(ps, source=p.source or "FDA_NDC"))
        if meta:
            return meta, "products.strength"

    if catalog_has_label_dose_options_table():
        try:
            from app.services.datasets.catalog_store import _connect

            with _connect() as conn:
                rows = conn.execute(
                    """
                    SELECT DISTINCT strength, source, route, MAX(confidence) AS confidence
                    FROM label_dose_options
                    WHERE medicine_id=?
                    GROUP BY LOWER(TRIM(strength)), source, LOWER(TRIM(route))
                    ORDER BY strength COLLATE NOCASE
                    """,
                    (mid,),
                ).fetchall()
            for r in rows:
                if not routes_equivalent(r["route"], route_label):
                    continue
                ps = (r["strength"] or "").strip()
                if not ps or ps in strengths:
                    continue
                strengths.append(ps)
                meta.append(
                    _option(
                        ps,
                        source=r["source"] or "FDA_SPL",
                        confidence=float(r["confidence"] or 0.0),
                    )
                )
        except Exception:  # noqa: BLE001
            pass
        if meta:
            return meta, "label_dose_options.strength_fallback"
    return [], "strengths_none"


def query_doses(
    canonical_name: str | None,
    *,
    route: str | None,
    strength: str | None,
) -> tuple[list[dict[str, Any]], str]:
    """Doses from label_dose_options exact medicine+route+strength."""
    mid = resolve_medicine_id(canonical_name)
    route_label = _route_display(route)
    strength_s = (strength or "").strip()
    if mid is None or not route_label or not strength_s:
        return [], "catalog_none"
    if not catalog_has_label_dose_options_table():
        return [], "label_dose_options_absent"
    rows = list_label_dose_options(mid, route=route_label, strength=strength_s)
    if not rows:
        # Case / synonym route labels in SPL index
        try:
            from app.services.datasets.catalog_store import _connect

            with _connect() as conn:
                cand = conn.execute(
                    """
                    SELECT dose_label, source, evidence_excerpt, confidence, route
                    FROM label_dose_options
                    WHERE medicine_id=? AND LOWER(TRIM(strength))=LOWER(TRIM(?))
                    """,
                    (mid, strength_s),
                ).fetchall()
            rows = [
                type(
                    "R",
                    (),
                    {
                        "dose_label": c["dose_label"],
                        "source": c["source"],
                        "evidence_excerpt": c["evidence_excerpt"],
                        "confidence": c["confidence"],
                    },
                )()
                for c in cand
                if routes_equivalent(c["route"], route_label)
            ]
        except Exception:  # noqa: BLE001
            rows = []
    meta = [
        _option(
            o.dose_label,
            source=o.source or "FDA_SPL",
            evidence_excerpt=o.evidence_excerpt,
            confidence=o.confidence,
        )
        for o in rows
        if o.dose_label
    ]
    if not meta:
        return [], "FDA_SPL_none"
    return meta, "FDA_SPL_label_dose_options"


def query_frequencies(
    canonical_name: str | None,
    *,
    route: str | None,
    strength: str | None,
    dose: str | None,
) -> tuple[list[dict[str, Any]], str]:
    """Frequencies from dose-frequency relation; fallback older frequency table."""
    mid = resolve_medicine_id(canonical_name)
    route_label = _route_display(route)
    strength_s = (strength or "").strip()
    dose_s = (dose or "").strip()
    if mid is None or not route_label or not strength_s or not dose_s:
        return [], "catalog_none"

    if catalog_has_label_dose_frequency_options_table():
        rows = list_label_dose_frequency_options(
            mid, route=route_label, strength=strength_s, dose_label=dose_s
        )
        meta = [
            _option(
                o.frequency_label,
                source=o.source or "FDA_SPL",
                evidence_excerpt=o.evidence_excerpt,
                confidence=o.confidence,
            )
            for o in rows
            if o.frequency_label
        ]
        if meta:
            return meta, "FDA_SPL_label_dose_frequency_options"

    if catalog_has_label_frequency_options_table():
        rows = list_label_frequency_options(mid, route=route_label, strength=strength_s)
        if not rows:
            try:
                from app.services.datasets.catalog_store import _connect

                with _connect() as conn:
                    cand = conn.execute(
                        """
                        SELECT frequency_label, source, evidence_excerpt, confidence, route
                        FROM label_frequency_options
                        WHERE medicine_id=? AND LOWER(TRIM(strength))=LOWER(TRIM(?))
                        """,
                        (mid, strength_s),
                    ).fetchall()
                rows = [
                    type(
                        "R",
                        (),
                        {
                            "frequency_label": c["frequency_label"],
                            "source": c["source"],
                            "evidence_excerpt": c["evidence_excerpt"],
                            "confidence": c["confidence"],
                        },
                    )()
                    for c in cand
                    if routes_equivalent(c["route"], route_label)
                ]
            except Exception:  # noqa: BLE001
                rows = []
        meta = [
            _option(
                o.frequency_label,
                source=o.source or "FDA_SPL",
                evidence_excerpt=o.evidence_excerpt,
                confidence=o.confidence,
            )
            for o in rows
            if o.frequency_label
        ]
        if meta:
            return meta, "FDA_SPL_label_frequency_options_legacy"
    return [], "FDA_SPL_none"


def query_indications(canonical_name: str | None) -> tuple[list[dict[str, Any]], str]:
    """Indications from indication_options; live miner fallback for older DBs."""
    mid = resolve_medicine_id(canonical_name)
    if mid is None:
        return [], "catalog_none"

    if catalog_has_indication_options_table():
        rows = list_indication_options(mid)
        meta = [
            _option(
                o.indication_label,
                source=o.source or "FDA_SPL",
                evidence_excerpt=o.evidence_excerpt,
                confidence=o.confidence,
            )
            for o in rows
            if o.indication_label
        ]
        if meta:
            return meta, "indication_options"

    try:
        from app.services.datasets.indication_options import catalog_indication_options

        live = catalog_indication_options(canonical_name) or []
    except Exception:  # noqa: BLE001
        live = []
    meta = []
    for o in live:
        if isinstance(o, dict):
            val = o.get("value") or o.get("label")
            if not val:
                continue
            sources = o.get("sources") or ["FDA_SPL"]
            meta.append(
                _option(
                    str(val),
                    source=str(sources[0]) if sources else "FDA_SPL",
                    evidence_excerpt=o.get("evidence_excerpt"),
                )
            )
        else:
            meta.append(_option(str(o), source="FDA_SPL"))
    if meta:
        return meta, "indication_options_live_fallback"
    return [], "indication_none"


def strict_cascade_labels(
    *,
    canonical_name: str | None,
    matched_route: str | None = None,
    matched_strength: str | None = None,
    matched_dose: str | None = None,
) -> dict[str, Any]:
    """Return label lists + sources for HITL cascade (no templates)."""
    routes, route_src = query_routes(canonical_name)
    out: dict[str, Any] = {
        "route": {
            "options": [o["value"] for o in routes],
            "evidence": routes,
            "option_source": route_src,
        },
        "strength": {"options": [], "evidence": [], "option_source": "catalog_none"},
        "dose": {"options": [], "evidence": [], "option_source": "catalog_none"},
        "frequency": {"options": [], "evidence": [], "option_source": "catalog_none"},
        "indication": {"options": [], "evidence": [], "option_source": "catalog_none"},
    }
    if not matched_route:
        return out
    strengths, s_src = query_strengths(canonical_name, route=matched_route)
    out["strength"] = {
        "options": [o["value"] for o in strengths],
        "evidence": strengths,
        "option_source": s_src,
    }
    if not matched_strength:
        return out
    doses, d_src = query_doses(
        canonical_name, route=matched_route, strength=matched_strength
    )
    out["dose"] = {
        "options": [o["value"] for o in doses],
        "evidence": doses,
        "option_source": d_src,
    }
    if not matched_dose:
        return out
    freqs, f_src = query_frequencies(
        canonical_name,
        route=matched_route,
        strength=matched_strength,
        dose=matched_dose,
    )
    out["frequency"] = {
        "options": [o["value"] for o in freqs],
        "evidence": freqs,
        "option_source": f_src,
    }
    return out
