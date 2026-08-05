"""Retrieve SAME_ACTIVE_MOIETY_PRODUCT candidates from the local catalogue."""

from __future__ import annotations

from typing import Any

from app.services.therapeutic.canonical_envelope import build_canonical_envelope
from app.services.therapeutic.salt_normalisation import normalize_key, resolve_moiety


def retrieve_same_moiety_product_candidates(
    *,
    source_identity: dict[str, Any],
    source_envelope: dict[str, Any],
    source_route: str | None,
    source_form: str | None,
    source_strength: str | None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Find catalogue medicines sharing the verified active moiety (different products)."""
    try:
        from app.services.datasets.catalog_store import catalog_available, get_medicine, _connect
    except Exception:
        return []

    if not catalog_available():
        return []

    base = source_envelope.get("base_ingredient") or resolve_moiety(
        source_identity.get("canonical_name")
    ).get("base_ingredient")
    if not base:
        return []

    source_id = source_identity.get("catalog_medicine_id")
    source_name_key = normalize_key(source_identity.get("canonical_name"))

    # Build search tokens from moiety map forms
    from app.services.therapeutic.salt_normalisation import _MOIETY_FORMS

    forms = sorted(_MOIETY_FORMS.get(base, {base}), key=len, reverse=True)
    # Also search base token
    like_terms = list(dict.fromkeys([base, *list(forms)[:6]]))

    ids: list[int] = []
    seen: set[int] = set()
    with _connect() as conn:
        for term in like_terms:
            rows = conn.execute(
                """
                SELECT id, canonical_name, drugbank_id, product_ndc, sources,
                       dosage_forms, routes
                FROM medicines
                WHERE lower(canonical_name) LIKE ?
                LIMIT ?
                """,
                (f"%{term}%", limit),
            ).fetchall()
            for row in rows:
                mid = int(row["id"])
                if mid in seen:
                    continue
                seen.add(mid)
                ids.append(mid)
            if len(ids) >= limit:
                break

    out: list[dict[str, Any]] = []
    for mid in ids:
        if source_id is not None and mid == int(source_id):
            continue
        rec = get_medicine(mid)
        if not rec:
            continue
        cname = rec.canonical_name or ""
        if normalize_key(cname) == source_name_key:
            continue
        # Must resolve to same base
        c_moiety = resolve_moiety(cname)
        if c_moiety.get("base_ingredient") != base and not (
            {c_moiety.get("base_ingredient"), base} <= {"acetaminophen", "paracetamol"}
        ):
            continue

        routes = list(rec.routes or [])
        forms = list(rec.dosage_forms or [])
        route = source_route if source_route and normalize_key(source_route) in [
            normalize_key(r) for r in routes
        ] else (routes[0] if routes else source_route)
        form = source_form if source_form and any(
            normalize_key(source_form) in normalize_key(f) or normalize_key(f) in normalize_key(source_form)
            for f in forms
        ) else (forms[0] if forms else source_form)

        strength = None
        if rec.strengths:
            strength = rec.strengths[0]
        if source_strength:
            # Prefer matching strength string if present
            for s in rec.strengths or []:
                if normalize_key(s) == normalize_key(source_strength):
                    strength = s
                    break

        srcs = list(rec.sources or [])
        envelope = build_canonical_envelope(
            medicine_name=cname,
            strength=strength or source_strength,
            dosage_form=form,
            route=route,
            product_ndc=rec.product_ndc,
            drugbank_id=rec.drugbank_id,
            catalog_medicine_id=rec.id,
            source_provenance=srcs,
        )

        drugbank_id = rec.drugbank_id or f"CATALOG:{rec.id}"
        out.append(
            {
                "candidate_drug_id": drugbank_id,
                "candidate_name": cname,
                "active_ingredient": cname,
                "classification": "same_active_moiety_product",
                "why_retrieved": [
                    "Same active moiety (salt/base map)",
                    "Catalogue product identity for pharmacist review",
                ],
                "indication_relationship": {
                    "overlap": False,
                    "note": "Product candidate path — indication overlap not required",
                },
                "class_relationship": {"related": False},
                "mechanism_relationship": {"related": False},
                "target_relationship": {"related": False, "shared_targets": []},
                "record": {
                    "drugbank_id": drugbank_id,
                    "generic_name": cname,
                    "sources": srcs,
                    "routes": routes,
                    "dosage_forms": forms,
                    "catalog_medicine_id": rec.id,
                    "approval_status": ["approved"],
                    "market_status": "active",
                    "withdrawal_status": None,
                    "drug_interactions": [],
                },
                "spl": {
                    "route": route,
                    "dosage_form": form,
                    "linked_drugbank_id": rec.drugbank_id,
                },
                "canonical_envelope": envelope,
                "data_source": "catalog",
                "provenance_label": "FDA NDC + DrugBank catalog",
                "retrieval_path": "SAME_ACTIVE_MOIETY_PRODUCT",
            }
        )
        if len(out) >= limit:
            break
    return out
