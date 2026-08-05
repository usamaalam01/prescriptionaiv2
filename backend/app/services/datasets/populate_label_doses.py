"""Backfill label_dose_options + label_frequency_options on an existing catalog."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from app.services.datasets.build_index import (
    ensure_label_dose_options_table,
    populate_indication_options,
    populate_label_dose_options,
)
from app.services.datasets.paths import catalog_db_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract dose + frequency + indication options from catalog label text"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Catalog SQLite path (default: MEDICINE_CATALOG_DB / data/medicine_catalog.sqlite3)",
    )
    args = parser.parse_args()
    db = args.db or catalog_db_path()
    if not db.exists():
        raise SystemExit(f"Catalog not found: {db}")
    print(f"Backfilling SPL SIG + indication options in {db}", flush=True)
    conn = sqlite3.connect(str(db))
    ensure_label_dose_options_table(conn)
    n = populate_label_dose_options(conn)
    ind_n = populate_indication_options(conn)
    dose_n = conn.execute("SELECT COUNT(*) FROM label_dose_options").fetchone()[0]
    freq_n = conn.execute("SELECT COUNT(*) FROM label_frequency_options").fetchone()[0]
    try:
        dose_freq_n = conn.execute(
            "SELECT COUNT(*) FROM label_dose_frequency_options"
        ).fetchone()[0]
    except sqlite3.Error:
        dose_freq_n = 0
    try:
        ind_count = conn.execute("SELECT COUNT(*) FROM indication_options").fetchone()[0]
    except sqlite3.Error:
        ind_count = 0
    conn.close()
    print(
        f"Done. insert_attempts={n} doses={dose_n} frequencies={freq_n} "
        f"dose_freq={dose_freq_n} indication_inserts={ind_n} indications={ind_count}",
        flush=True,
    )


if __name__ == "__main__":
    main()
