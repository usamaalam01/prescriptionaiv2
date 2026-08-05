from __future__ import annotations

import csv
from pathlib import Path

from app.services.catalog_sig_options import (
    evidence_doses_for_drug_route_strength,
    evidence_frequencies_for_drug_route_strength,
)
from app.services.datasets.catalog_store import _connect


def _pick_route_strength_forms(medicine_id: int) -> list[tuple[str, str, list[str]]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT route, strength, dosage_form
            FROM products
            WHERE medicine_id=?
              AND TRIM(COALESCE(route, '')) <> ''
              AND TRIM(COALESCE(strength, '')) <> ''
            ORDER BY
              CASE
                WHEN LOWER(route) LIKE '%oral%' THEN 0
                WHEN LOWER(route) LIKE '%inhal%' THEN 1
                ELSE 2
              END,
              route,
              strength,
              dosage_form
            """,
            (medicine_id,),
        ).fetchall()
    combos: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        route = str(r["route"] or "").strip()
        strength = str(r["strength"] or "").strip()
        form = str(r["dosage_form"] or "").strip()
        if not route or not strength:
            continue
        key = (route, strength)
        combos.setdefault(key, [])
        if form and form not in combos[key]:
            combos[key].append(form)
    return [(route, strength, forms) for (route, strength), forms in combos.items()]


def build_rows(limit: int | None = 100) -> list[dict[str, str]]:
    with _connect() as conn:
        meds = conn.execute(
            """
            SELECT id, canonical_name, indication
            FROM medicines
            WHERE TRIM(COALESCE(indication, '')) <> ''
            ORDER BY canonical_name COLLATE NOCASE
            """
        ).fetchall()

    out: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for med in meds:
        if limit is not None and len(out) >= limit:
            break
        name = str(med["canonical_name"] or "").strip()
        indication = str(med["indication"] or "").strip()
        if not name or not indication or name.lower() in seen_names:
            continue

        for route_raw, strength, forms in _pick_route_strength_forms(int(med["id"])):
            route = route_raw.split(";")[0].split(",")[0].strip()
            if not route:
                continue

            doses, dose_src, dose_meta = evidence_doses_for_drug_route_strength(
                canonical_name=name,
                route=route,
                strength=strength,
                forms=forms,
            )
            if not doses:
                continue

            dose = doses[0]
            freqs, freq_src, freq_meta = evidence_frequencies_for_drug_route_strength(
                canonical_name=name,
                route=route,
                strength=strength,
                dose=dose,
            )
            if not freqs:
                continue

            row = {
                "drug": name,
                "route": route,
                "strength": strength,
                "dosage": dose,
                "frequency": freqs[0],
                "indication": indication.replace("\n", " ").replace("\r", " ").strip(),
                "dose_source": dose_src,
                "frequency_source": freq_src,
                "dose_evidence_excerpt": str((dose_meta[0] if dose_meta else {}).get("evidence_excerpt") or ""),
                "frequency_evidence_excerpt": str((freq_meta[0] if freq_meta else {}).get("evidence_excerpt") or ""),
            }
            out.append(row)
            seen_names.add(name.lower())
            break

    return out


def main(limit: int | None = 100, out_name: str = "catalog_complete_details_100.csv") -> None:
    rows = build_rows(limit)
    out_path = Path(r"D:\Projects\PharmaAssist\reports") / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "drug",
                "route",
                "strength",
                "dosage",
                "frequency",
                "indication",
                "dose_source",
                "frequency_source",
                "dose_evidence_excerpt",
                "frequency_evidence_excerpt",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
