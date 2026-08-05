"""Audit medicine_catalog.sqlite3 for structural and content inconsistencies."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "data" / "medicine_catalog.sqlite3"
OUT = Path(__file__).resolve().parents[2] / "reports" / "catalog_inconsistency_audit.json"


def main() -> None:
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    report: dict = {"db_path": str(DB), "db_size_mb": round(DB.stat().st_size / 1e6, 1)}

    report["meta"] = dict(con.execute("SELECT key, value FROM meta").fetchall())

    src_counts: Counter[str] = Counter()
    for (sources,) in con.execute("SELECT sources FROM medicines"):
        try:
            for s in json.loads(sources or "[]"):
                src_counts[str(s)] += 1
        except Exception:  # noqa: BLE001
            src_counts["parse_error"] += 1
    report["source_tag_counts"] = dict(src_counts.most_common())

    all_lower = con.execute(
        "SELECT count(*) FROM medicines WHERE canonical_name = lower(canonical_name) "
        "AND canonical_name GLOB '*[a-z]*'"
    ).fetchone()[0]
    all_upper = con.execute(
        "SELECT count(*) FROM medicines WHERE canonical_name = upper(canonical_name) "
        "AND canonical_name GLOB '*[A-Z]*'"
    ).fetchone()[0]
    total = con.execute("SELECT count(*) FROM medicines").fetchone()[0]
    report["casing"] = {
        "all_lower": all_lower,
        "all_upper": all_upper,
        "mixed_or_other": total - all_lower - all_upper,
        "total": total,
        "pct_all_lower": round(100 * all_lower / total, 2) if total else 0,
    }

    report["dup_canonical_key_groups"] = con.execute(
        "SELECT count(*) FROM (SELECT canonical_key FROM medicines "
        "GROUP BY canonical_key HAVING count(*) > 1)"
    ).fetchone()[0]
    report["dup_canonical_key_rows"] = con.execute(
        "SELECT coalesce(sum(c),0) FROM (SELECT count(*) c FROM medicines "
        "GROUP BY canonical_key HAVING c > 1)"
    ).fetchone()[0]
    report["dup_canonical_key_top"] = [
        {"key": r[0], "count": r[1]}
        for r in con.execute(
            "SELECT canonical_key, count(*) c FROM medicines "
            "GROUP BY canonical_key HAVING c > 1 ORDER BY c DESC LIMIT 25"
        )
    ]

    report["dup_drugbank_groups"] = con.execute(
        "SELECT count(*) FROM (SELECT drugbank_id FROM medicines "
        "WHERE drugbank_id IS NOT NULL AND drugbank_id != '' "
        "GROUP BY drugbank_id HAVING count(*) > 1)"
    ).fetchone()[0]
    report["dup_drugbank_top"] = [
        {"drugbank_id": r[0], "count": r[1]}
        for r in con.execute(
            "SELECT drugbank_id, count(*) c FROM medicines "
            "WHERE drugbank_id IS NOT NULL AND drugbank_id != '' "
            "GROUP BY drugbank_id HAVING c > 1 ORDER BY c DESC LIMIT 20"
        )
    ]

    no_strength = con.execute(
        "SELECT count(*) FROM medicines m WHERE NOT EXISTS "
        "(SELECT 1 FROM strengths s WHERE s.medicine_id = m.id)"
    ).fetchone()[0]
    no_product = con.execute(
        "SELECT count(*) FROM medicines m WHERE NOT EXISTS "
        "(SELECT 1 FROM products p WHERE p.medicine_id = m.id)"
    ).fetchone()[0]
    no_dose = con.execute(
        "SELECT count(*) FROM medicines m WHERE NOT EXISTS "
        "(SELECT 1 FROM label_dose_options d WHERE d.medicine_id = m.id)"
    ).fetchone()[0]
    no_freq = con.execute(
        "SELECT count(*) FROM medicines m WHERE NOT EXISTS "
        "(SELECT 1 FROM label_frequency_options f WHERE f.medicine_id = m.id)"
    ).fetchone()[0]
    no_route_json = con.execute(
        "SELECT count(*) FROM medicines WHERE routes IS NULL OR routes = '[]' OR routes = ''"
    ).fetchone()[0]
    no_form_json = con.execute(
        "SELECT count(*) FROM medicines WHERE dosage_forms IS NULL OR dosage_forms = '[]' "
        "OR dosage_forms = ''"
    ).fetchone()[0]
    both_sig = con.execute(
        "SELECT count(*) FROM medicines m WHERE EXISTS "
        "(SELECT 1 FROM label_dose_options d WHERE d.medicine_id = m.id) AND EXISTS "
        "(SELECT 1 FROM label_frequency_options f WHERE f.medicine_id = m.id)"
    ).fetchone()[0]
    report["coverage"] = {
        "medicines": total,
        "aliases": con.execute("SELECT count(*) FROM aliases").fetchone()[0],
        "products": con.execute("SELECT count(*) FROM products").fetchone()[0],
        "strengths": con.execute("SELECT count(*) FROM strengths").fetchone()[0],
        "label_dose_options": con.execute("SELECT count(*) FROM label_dose_options").fetchone()[0],
        "label_frequency_options": con.execute(
            "SELECT count(*) FROM label_frequency_options"
        ).fetchone()[0],
        "label_sections": con.execute("SELECT count(*) FROM label_sections").fetchone()[0],
        "no_strength_rows": no_strength,
        "no_products": no_product,
        "no_dose_options": no_dose,
        "no_freq_options": no_freq,
        "no_routes_json": no_route_json,
        "no_forms_json": no_form_json,
        "has_dose_and_freq": both_sig,
        "pct_has_dose_and_freq": round(100 * both_sig / total, 2) if total else 0,
        "pct_no_dose": round(100 * no_dose / total, 2) if total else 0,
        "pct_no_freq": round(100 * no_freq / total, 2) if total else 0,
        "pct_no_strength": round(100 * no_strength / total, 2) if total else 0,
    }

    bad_names = [
        "Take",
        "Drink",
        "Advice",
        "Tablet",
        "Capsule",
        "Oral",
        "Once",
        "Twice",
        "Patient",
        "Clinic",
        "Diabetes",
        "Follow",
        "Unknown",
        "None",
    ]
    bad_hits = []
    for name in bad_names:
        rows = con.execute(
            "SELECT id, canonical_name, sources FROM medicines "
            "WHERE canonical_key = ? OR lower(canonical_name) = ?",
            (name.lower(), name.lower()),
        ).fetchall()
        for r in rows:
            bad_hits.append({"id": r[0], "name": r[1], "sources": r[2]})
    report["suspicious_medicine_names"] = bad_hits

    # Short / numeric-looking names
    short = con.execute(
        "SELECT canonical_name, sources FROM medicines "
        "WHERE length(trim(canonical_name)) < 3 ORDER BY canonical_name LIMIT 40"
    ).fetchall()
    report["short_names_sample"] = [{"name": r[0], "sources": r[1]} for r in short]
    report["short_names_count"] = con.execute(
        "SELECT count(*) FROM medicines WHERE length(trim(canonical_name)) < 3"
    ).fetchone()[0]

    strengths = [r[0] for r in con.execute("SELECT DISTINCT strength FROM strengths")]
    report["strength_format"] = {
        "distinct": len(strengths),
        "with_space_mg": sum(1 for s in strengths if re.search(r"\d\s+mg\b", s or "", re.I)),
        "no_space_mg": sum(1 for s in strengths if re.search(r"\dmg\b", s or "", re.I)),
        "with_slash": sum(1 for s in strengths if s and "/" in s),
        "null_or_empty": sum(1 for s in strengths if not (s or "").strip()),
        "sample_nospace": [s for s in strengths if re.search(r"\dmg\b", s or "", re.I)][:15],
        "sample_space": [s for s in strengths if re.search(r"\d\s+mg\b", s or "", re.I)][:15],
    }

    demo = [
        "metformin",
        "acarbose",
        "empagliflozin",
        "atorvastatin",
        "amoxicillin",
        "ibuprofen",
        "cetirizine",
        "pantoprazole",
    ]
    demo_detail = []
    for name in demo:
        meds = con.execute(
            "SELECT id, canonical_name, sources, dosage_forms, routes FROM medicines "
            "WHERE canonical_key = ? OR lower(canonical_name) = ?",
            (name, name),
        ).fetchall()
        for m in meds[:5]:
            mid = m[0]
            strs = [
                r[0]
                for r in con.execute(
                    "SELECT strength FROM strengths WHERE medicine_id = ?", (mid,)
                )
            ]
            doses = [
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT dose_label FROM label_dose_options "
                    "WHERE medicine_id = ? LIMIT 15",
                    (mid,),
                )
            ]
            freqs = [
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT frequency_label FROM label_frequency_options "
                    "WHERE medicine_id = ? LIMIT 15",
                    (mid,),
                )
            ]
            routes_p = [
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT route FROM products WHERE medicine_id = ? "
                    "AND route IS NOT NULL LIMIT 12",
                    (mid,),
                )
            ]
            demo_detail.append(
                {
                    "id": mid,
                    "name": m[1],
                    "sources": m[2],
                    "forms_json": m[3],
                    "routes_json": m[4],
                    "n_strengths": len(strs),
                    "strength_sample": strs[:10],
                    "n_doses": con.execute(
                        "SELECT count(*) FROM label_dose_options WHERE medicine_id = ?",
                        (mid,),
                    ).fetchone()[0],
                    "dose_sample": doses,
                    "n_freqs": con.execute(
                        "SELECT count(*) FROM label_frequency_options WHERE medicine_id = ?",
                        (mid,),
                    ).fetchone()[0],
                    "freq_sample": freqs,
                    "product_routes": routes_p,
                }
            )
    report["demo_drugs"] = demo_detail

    report["multi_medicine_alias_keys"] = con.execute(
        "SELECT count(*) FROM (SELECT alias_key FROM aliases "
        "GROUP BY alias_key HAVING count(DISTINCT medicine_id) > 1)"
    ).fetchone()[0]
    report["multi_medicine_aliases_top"] = [
        {"alias": r[0], "medicine_ids": r[1]}
        for r in con.execute(
            "SELECT alias_key, count(DISTINCT medicine_id) c FROM aliases "
            "GROUP BY alias_key HAVING c > 1 ORDER BY c DESC LIMIT 25"
        )
    ]

    report["empty_sig_labels"] = {
        "dose": con.execute(
            "SELECT count(*) FROM label_dose_options "
            "WHERE dose_label IS NULL OR trim(dose_label) = ''"
        ).fetchone()[0],
        "freq": con.execute(
            "SELECT count(*) FROM label_frequency_options "
            "WHERE frequency_label IS NULL OR trim(frequency_label) = ''"
        ).fetchone()[0],
    }

    report["odd_dose_labels"] = [
        {"label": r[0], "count": r[1]}
        for r in con.execute(
            "SELECT dose_label, count(*) c FROM label_dose_options "
            "WHERE lower(dose_label) IN ('take','drink','unknown','n/a','none') "
            "OR length(dose_label) < 3 "
            "GROUP BY dose_label ORDER BY c DESC LIMIT 25"
        )
    ]
    report["odd_freq_labels"] = [
        {"label": r[0], "count": r[1]}
        for r in con.execute(
            "SELECT frequency_label, count(*) c FROM label_frequency_options "
            "WHERE length(frequency_label) < 3 OR lower(frequency_label) IN "
            "('take','unknown','n/a') "
            "GROUP BY frequency_label ORDER BY c DESC LIMIT 25"
        )
    ]

    # Same lower(name) with different casing / multiple rows
    report["case_variant_group_count"] = con.execute(
        "SELECT count(*) FROM (SELECT lower(canonical_name) FROM medicines "
        "GROUP BY 1 HAVING count(*) > 1)"
    ).fetchone()[0]
    report["case_variant_groups_top"] = [
        {"lower": r[0], "count": r[1], "names": r[2][:240]}
        for r in con.execute(
            "SELECT lower(canonical_name) ln, count(*) c, "
            "group_concat(canonical_name, ' | ') names "
            "FROM medicines GROUP BY ln HAVING c > 1 ORDER BY c DESC LIMIT 25"
        )
    ]

    # Source-only silos
    only_ndc = con.execute(
        "SELECT count(*) FROM medicines WHERE sources LIKE '%FDA_NDC%' "
        "AND sources NOT LIKE '%DrugBank%' AND sources NOT LIKE '%FDA_SPL%'"
    ).fetchone()[0]
    only_db = con.execute(
        "SELECT count(*) FROM medicines WHERE sources LIKE '%DrugBank%' "
        "AND sources NOT LIKE '%FDA_NDC%' AND sources NOT LIKE '%FDA_SPL%'"
    ).fetchone()[0]
    has_spl = con.execute(
        "SELECT count(*) FROM medicines WHERE sources LIKE '%FDA_SPL%'"
    ).fetchone()[0]
    report["source_silos"] = {
        "fda_ndc_only": only_ndc,
        "drugbank_only": only_db,
        "has_fda_spl_tag": has_spl,
    }

    # Top frequency / dose label cardinality (noise)
    report["top_dose_labels"] = [
        {"label": r[0], "count": r[1]}
        for r in con.execute(
            "SELECT dose_label, count(*) c FROM label_dose_options "
            "GROUP BY dose_label ORDER BY c DESC LIMIT 20"
        )
    ]
    report["top_freq_labels"] = [
        {"label": r[0], "count": r[1]}
        for r in con.execute(
            "SELECT frequency_label, count(*) c FROM label_frequency_options "
            "GROUP BY frequency_label ORDER BY c DESC LIMIT 20"
        )
    ]

    # Products with null route/strength/form
    report["product_nulls"] = {
        "null_strength": con.execute(
            "SELECT count(*) FROM products WHERE strength IS NULL OR trim(strength) = ''"
        ).fetchone()[0],
        "null_route": con.execute(
            "SELECT count(*) FROM products WHERE route IS NULL OR trim(route) = ''"
        ).fetchone()[0],
        "null_form": con.execute(
            "SELECT count(*) FROM products WHERE dosage_form IS NULL OR trim(dosage_form) = ''"
        ).fetchone()[0],
        "total_products": con.execute("SELECT count(*) FROM products").fetchone()[0],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(
        {
            "casing": report["casing"],
            "coverage": report["coverage"],
            "source_silos": report["source_silos"],
            "source_tag_counts": report["source_tag_counts"],
            "dup_canonical_key_groups": report["dup_canonical_key_groups"],
            "dup_drugbank_groups": report["dup_drugbank_groups"],
            "multi_medicine_alias_keys": report["multi_medicine_alias_keys"],
            "case_variant_group_count": report["case_variant_group_count"],
            "suspicious_count": len(report["suspicious_medicine_names"]),
            "empty_sig_labels": report["empty_sig_labels"],
            "product_nulls": report["product_nulls"],
            "strength_format": {
                k: report["strength_format"][k]
                for k in ("distinct", "with_space_mg", "no_space_mg", "with_slash")
            },
        },
        indent=2,
    ))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
