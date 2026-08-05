from __future__ import annotations

import csv
from pathlib import Path

from app.services.datasets.catalog_store import _connect


SQL = """
WITH product_keys AS (
    SELECT DISTINCT
        p.medicine_id,
        TRIM(p.route) AS route,
        TRIM(p.strength) AS strength
    FROM products p
    WHERE TRIM(COALESCE(p.route, '')) <> ''
      AND TRIM(COALESCE(p.strength, '')) <> ''
),
ranked AS (
    SELECT
        m.canonical_name AS drug,
        pk.route,
        pk.strength,
        d.dose_label AS dosage,
        f.frequency_label AS frequency,
        TRIM(m.indication) AS indication,
        d.source AS dose_source,
        f.source AS frequency_source,
        d.evidence_excerpt AS dose_evidence_excerpt,
        f.evidence_excerpt AS frequency_evidence_excerpt,
        ROW_NUMBER() OVER (
            PARTITION BY LOWER(TRIM(m.canonical_name))
            ORDER BY
                CASE
                    WHEN LOWER(pk.route) LIKE '%oral%' THEN 0
                    WHEN LOWER(pk.route) LIKE '%inhal%' THEN 1
                    ELSE 2
                END,
                pk.route,
                pk.strength,
                d.confidence DESC,
                f.confidence DESC
        ) AS rn
    FROM medicines m
    JOIN product_keys pk
      ON pk.medicine_id = m.id
    JOIN label_dose_options d
      ON d.medicine_id = m.id
     AND LOWER(TRIM(d.route)) = LOWER(pk.route)
     AND LOWER(TRIM(d.strength)) = LOWER(pk.strength)
    JOIN label_frequency_options f
      ON f.medicine_id = m.id
     AND LOWER(TRIM(f.route)) = LOWER(pk.route)
     AND LOWER(TRIM(f.strength)) = LOWER(pk.strength)
    WHERE TRIM(COALESCE(m.indication, '')) <> ''
)
SELECT
    drug,
    route,
    strength,
    dosage,
    frequency,
    indication,
    dose_source,
    frequency_source,
    dose_evidence_excerpt,
    frequency_evidence_excerpt
FROM ranked
WHERE rn = 1
ORDER BY drug COLLATE NOCASE
"""


def main() -> None:
    out_path = Path(r"D:\Projects\PharmaAssist\reports\catalog_complete_details_all.csv")
    with _connect() as conn:
        rows = conn.execute(SQL).fetchall()

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
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
            ]
        )
        for r in rows:
            writer.writerow([r[k] for k in r.keys()])

    print(f"wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
