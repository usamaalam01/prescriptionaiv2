"""Phase 2 DRY_RUN: read-only route profile for medicine_catalog.sqlite3.

No writes to the catalog. Outputs reports under reports/route_cleaning/.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "data" / "medicine_catalog.sqlite3"
OUT = Path(__file__).resolve().parents[2] / "reports" / "route_cleaning"


def normalize_route_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value.casefold()


# Delimiters observed / allowed for multi-route FDA strings
_SPLIT_RE = re.compile(r"\s*;\s*")


def split_components(raw: str) -> list[str]:
    raw = unicodedata.normalize("NFKC", raw or "").replace("\u00a0", " ")
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        return []
    # Primary FDA delimiter is semicolon. Also catch accidental commas that look like lists
    # of routes (not dosage phrases) — only split on ';' for safety in dry-run.
    parts = _SPLIT_RE.split(raw)
    return [p.strip() for p in parts]


def dosage_form_conflict(route_key: str, form: str | None) -> str | None:
    """Heuristic conflict flags only — never auto-correct."""
    if not form:
        return None
    f = normalize_route_key(form)
    r = route_key
    # Tablet/capsule typically oral (not absolute — flag broad mismatches only)
    if any(x in f for x in ("tablet", "capsule", "caplet")) and r in {
        "topical",
        "ophthalmic",
        "otic",
        "auricular (otic)",
        "vaginal",
        "rectal",
    }:
        return "ROUTE_DOSAGE_FORM_CONFLICT"
    if "ointment" in f or "cream" in f or "gel" in f:
        if r in {"oral", "intravenous", "intramuscular", "subcutaneous"}:
            return "ROUTE_DOSAGE_FORM_CONFLICT"
    if "injection" in f or "injectable" in f:
        if r in {"oral", "topical", "ophthalmic"}:
            return "ROUTE_DOSAGE_FORM_CONFLICT"
    return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    total_products = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    with_route = con.execute(
        "SELECT COUNT(*) FROM products WHERE route IS NOT NULL AND TRIM(route) != ''"
    ).fetchone()[0]
    without_route = total_products - with_route

    raw_counter: Counter[str] = Counter()
    concept_counter: Counter[str] = Counter()  # casefold key of FULL raw string
    atomic_counter: Counter[str] = Counter()
    atomic_display: dict[str, str] = {}  # key -> first seen display
    case_variants: dict[str, set[str]] = defaultdict(set)

    single_route = 0
    multi_route = 0
    empty_components = 0
    malformed_delimiter = 0  # e.g. trailing/leading ';'
    duplicate_components_products = 0
    unusual_many = 0  # >3 atomic routes
    conflict_samples: list[dict] = []
    conflict_count = 0

    multi_samples: list[dict] = []
    capitalization_groups: dict[str, set[str]] = defaultdict(set)

    source_by_route: Counter[tuple[str, str]] = Counter()

    cur = con.execute(
        "SELECT id, medicine_id, route, dosage_form, source, product_ndc, spl_set_id "
        "FROM products"
    )
    scanned = 0
    for row in cur:
        scanned += 1
        raw = row["route"]
        if raw is None or not str(raw).strip():
            continue
        raw_s = str(raw)
        raw_counter[raw_s] += 1
        full_key = normalize_route_key(raw_s)
        concept_counter[full_key] += 1
        capitalization_groups[full_key].add(raw_s)
        source_by_route[(full_key, row["source"] or "")] += 1

        # malformed delimiters
        if raw_s.strip().startswith(";") or raw_s.strip().endswith(";") or ";;" in raw_s:
            malformed_delimiter += 1

        comps = split_components(raw_s)
        # empty components
        raw_parts = _SPLIT_RE.split(re.sub(r"\s+", " ", raw_s.strip()))
        if any(not p.strip() for p in raw_parts):
            empty_components += 1

        keys = [normalize_route_key(c) for c in comps if c]
        if len(keys) <= 1:
            single_route += 1
        else:
            multi_route += 1
            if len(multi_samples) < 25:
                multi_samples.append(
                    {
                        "product_id": row["id"],
                        "medicine_id": row["medicine_id"],
                        "route_raw": raw_s,
                        "components": comps,
                        "source": row["source"],
                    }
                )

        if len(keys) != len(set(keys)):
            duplicate_components_products += 1
        if len(set(keys)) > 3:
            unusual_many += 1

        for c in comps:
            if not c:
                continue
            k = normalize_route_key(c)
            atomic_counter[k] += 1
            case_variants[k].add(c)
            atomic_display.setdefault(k, c)

            issue = dosage_form_conflict(k, row["dosage_form"])
            if issue:
                conflict_count += 1
                if len(conflict_samples) < 40:
                    conflict_samples.append(
                        {
                            "product_id": row["id"],
                            "route_component": c,
                            "dosage_form": row["dosage_form"],
                            "issue_code": issue,
                            "source": row["source"],
                        }
                    )

    # Case variant groups (same key, >1 spellings)
    case_variant_groups = {
        k: sorted(v) for k, v in capitalization_groups.items() if len(v) > 1
    }
    atomic_case_variants = {k: sorted(v) for k, v in case_variants.items() if len(v) > 1}

    # medicines.routes JSON profile
    med_total = con.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    med_with_routes = 0
    med_route_atomic: Counter[str] = Counter()
    for (raw,) in con.execute("SELECT routes FROM medicines"):
        try:
            arr = json.loads(raw or "[]")
        except json.JSONDecodeError:
            continue
        if arr:
            med_with_routes += 1
        for r in arr:
            if r and str(r).strip():
                med_route_atomic[normalize_route_key(str(r))] += 1

    # label_dose_options distinct routes
    dose_routes = con.execute(
        "SELECT route, COUNT(*) FROM label_dose_options GROUP BY route ORDER BY COUNT(*) DESC"
    ).fetchall()

    profile = {
        "mode": "DRY_RUN",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(DB),
        "engine": "SQLite " + con.execute("select sqlite_version()").fetchone()[0],
        "tables_scanned": ["products", "medicines", "label_dose_options"],
        "products_scanned": scanned,
        "products_total": total_products,
        "products_with_route": with_route,
        "products_without_route": without_route,
        "pct_with_route": round(100 * with_route / total_products, 2) if total_products else 0,
        "distinct_raw_route_strings": len(raw_counter),
        "distinct_full_route_concepts_casefold": len(concept_counter),
        "distinct_atomic_route_components": len(atomic_counter),
        "single_route_product_rows": single_route,
        "multi_route_product_rows": multi_route,
        "empty_route_component_events": empty_components,
        "malformed_delimiter_events": malformed_delimiter,
        "duplicate_component_within_product": duplicate_components_products,
        "products_with_gt3_atomic_routes": unusual_many,
        "case_variant_full_string_groups": len(case_variant_groups),
        "case_variant_atomic_groups": len(atomic_case_variants),
        "route_dosage_form_conflict_events": conflict_count,
        "medicines_total": med_total,
        "medicines_with_routes_json": med_with_routes,
        "distinct_atomic_in_medicines_json": len(med_route_atomic),
        "label_dose_distinct_routes": len(dose_routes),
        "top_raw_routes": raw_counter.most_common(40),
        "top_atomic_routes": atomic_counter.most_common(40),
        "top_case_variant_groups": sorted(
            ((k, sorted(v)) for k, v in case_variant_groups.items()),
            key=lambda x: -sum(raw_counter[s] for s in x[1]),
        )[:30],
        "multi_route_samples": multi_samples,
        "conflict_samples": conflict_samples,
        "label_dose_route_top": [{"route": r, "count": c} for r, c in dose_routes[:30]],
        "safety": {
            "authoritative_tables_modified": False,
            "writes_performed": False,
            "note": "DRY_RUN only — no STAGE/APPLY",
        },
    }

    (OUT / "route_profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")

    # CSV: atomic candidates for route master
    lines = ["route_key,example_display,product_component_count,case_variants"]
    for k, n in atomic_counter.most_common():
        variants = "|".join(sorted(case_variants[k]))
        disp = atomic_display.get(k, k)
        lines.append(
            f'"{k}","{disp.replace(chr(34), chr(34)+chr(34))}",{n},"{variants.replace(chr(34), chr(34)+chr(34))}"'
        )
    (OUT / "route_master_candidates.csv").write_text("\n".join(lines), encoding="utf-8")

    # CSV: case alias candidates (AUTO_APPROVED_FORMATTING candidates)
    alias_lines = [
        "alias_raw,alias_normalized,proposed_display,match_type,confidence,validation_status"
    ]
    for k, variants in sorted(atomic_case_variants.items(), key=lambda x: -len(x[1])):
        # Prefer Title-ish display: first non-all-upper variant, else title suggestion
        preferred = next((v for v in variants if not v.isupper()), sorted(variants)[0])
        for v in variants:
            if normalize_route_key(v) != k:
                continue
            status = "AUTO_APPROVED_FORMATTING" if v != preferred else "SOURCE_VERIFIED"
            alias_lines.append(
                f'"{v.replace(chr(34), chr(34)+chr(34))}","{k}","{preferred.replace(chr(34), chr(34)+chr(34))}",'
                f"casefold_equality,1.0,{status}"
            )
    (OUT / "route_alias_candidates.csv").write_text("\n".join(alias_lines), encoding="utf-8")

    # Review-required: multi-route, conflicts, empty, malformed
    review_lines = ["issue_code,severity,product_id,medicine_id,route_raw,detail,source"]
    for s in multi_samples:
        review_lines.append(
            f'MULTIPLE_ROUTES,INFO,{s["product_id"]},{s["medicine_id"]},'
            f'"{s["route_raw"].replace(chr(34), chr(34)+chr(34))}","components={len(s["components"])}",{s["source"]}'
        )
    for s in conflict_samples:
        review_lines.append(
            f'{s["issue_code"]},HIGH,{s["product_id"]},,'
            f'"{str(s["route_component"]).replace(chr(34), chr(34)+chr(34))}",'
            f'"dosage_form={s["dosage_form"]}",{s["source"]}'
        )
    (OUT / "route_review_required.csv").write_text("\n".join(review_lines), encoding="utf-8")

    quality = {
        "mode": "DRY_RUN",
        "generated_at": profile["generated_at"],
        "tables_scanned": profile["tables_scanned"],
        "products_scanned": scanned,
        "products_total": total_products,
        "products_with_route": with_route,
        "products_without_route": without_route,
        "distinct_raw_route_values": len(raw_counter),
        "distinct_atomic_route_components": len(atomic_counter),
        "case_variant_full_string_groups": len(case_variant_groups),
        "case_variant_atomic_groups": len(atomic_case_variants),
        "single_route_products": single_route,
        "multi_route_products": multi_route,
        "missing_routes": without_route,
        "empty_route_components": empty_components,
        "malformed_delimiters": malformed_delimiter,
        "duplicate_components": duplicate_components_products,
        "route_dosage_form_conflicts": conflict_count,
        "proposed_automatic_normalizations": "casefold aliases only (see route_alias_candidates.csv)",
        "review_required": "multi-route split + form conflicts (see route_review_required.csv)",
        "rejected_mapping_candidates": 0,
        "authoritative_data_modified": False,
        "reconciliation": {
            "every_product_row_scanned": scanned == total_products,
            "products_scanned": scanned,
            "products_total": total_products,
        },
    }
    (OUT / "route_quality_report.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")

    print(json.dumps(quality, indent=2))
    print("reports_dir", OUT)


if __name__ == "__main__":
    main()
