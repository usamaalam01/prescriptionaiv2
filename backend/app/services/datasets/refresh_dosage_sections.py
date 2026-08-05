"""Refresh dosage_and_administration sections from SPL shards at 16k (no full rebuild).

Fixes catalogs built while _first_list_text still clipped to 2500 chars before insert.
Re-parses dose + frequency options afterward.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from app.services.datasets.build_index import (
    _DOSAGE_ADMIN_MAX,
    _clip,
    _first_list_text,
    ensure_label_dose_options_table,
    normalize,
    populate_label_dose_options,
)
from app.services.datasets.paths import catalog_db_path, spl_label_paths


def _resolve_medicine_id(conn: sqlite3.Connection, row: dict) -> int | None:
    openfda = row.get("openfda") or {}
    brands = list(openfda.get("brand_name") or [])
    generics = list(openfda.get("generic_name") or [])
    if not brands and not generics:
        pde = row.get("spl_product_data_elements") or []
        if pde and isinstance(pde, list) and pde:
            head = str(pde[0]).split()
            if head:
                brands = [head[0]]
    canonical = (generics[0] if generics else (brands[0] if brands else "")).strip()
    if not canonical:
        return None
    display = str(canonical).title() if str(canonical).isupper() else str(canonical)
    key = normalize(display)
    if not key:
        return None
    found = conn.execute(
        "SELECT id FROM medicines WHERE canonical_key=?",
        (key,),
    ).fetchone()
    if found:
        return int(found[0])
    # Alias fallback (brand / substance)
    for alias in {*(brands or []), *(generics or [])}:
        akey = normalize(str(alias))
        if not akey:
            continue
        hit = conn.execute(
            "SELECT medicine_id FROM aliases WHERE alias_key=? LIMIT 1",
            (akey,),
        ).fetchone()
        if hit:
            return int(hit[0])
    return None


def refresh_dosage_sections(conn: sqlite3.Connection, *, limit: int | None = None) -> tuple[int, int]:
    """Rewrite dosage_and_administration from shards. Returns (updated, scanned)."""
    import ijson

    ensure_label_dose_options_table(conn)
    updated = 0
    scanned = 0
    for path in spl_label_paths():
        print(f"Refreshing dosage sections from {path.name}…", flush=True)
        with path.open("rb") as f:
            try:
                rows = ijson.items(f, "results.item")
                first = next(rows)
            except StopIteration:
                first = None
            if first is None:
                with path.open("rb") as f2:
                    stream = ijson.items(f2, "item")
                    for row in stream:
                        scanned += 1
                        n = _refresh_one(conn, row)
                        updated += n
                        if limit is not None and scanned >= limit:
                            conn.commit()
                            return updated, scanned
                        if scanned % 2000 == 0:
                            conn.commit()
                            print(f"  scanned={scanned} updated={updated}", flush=True)
                continue

            def _all():
                yield first
                yield from rows

            for row in _all():
                scanned += 1
                updated += _refresh_one(conn, row)
                if limit is not None and scanned >= limit:
                    conn.commit()
                    return updated, scanned
                if scanned % 2000 == 0:
                    conn.commit()
                    print(f"  scanned={scanned} updated={updated}", flush=True)
        conn.commit()
    return updated, scanned


def _refresh_one(conn: sqlite3.Connection, row: dict) -> int:
    text = _first_list_text(row.get("dosage_and_administration"))
    if not text:
        return 0
    clipped = _clip(text, _DOSAGE_ADMIN_MAX)
    if not clipped:
        return 0
    mid = _resolve_medicine_id(conn, row)
    if mid is None:
        return 0
    conn.execute(
        """
        INSERT OR REPLACE INTO label_sections(medicine_id, section_key, section_text, source)
        VALUES (?,?,?,?)
        """,
        (mid, "dosage_and_administration", clipped, "FDA_SPL"),
    )
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-ingest dosage_and_administration at 16k from SPL shards, then rebuild SIG options"
    )
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Dev only: stop after N SPL rows")
    parser.add_argument(
        "--skip-sig-reparse",
        action="store_true",
        help="Only refresh section text; do not rebuild dose/frequency tables",
    )
    args = parser.parse_args()
    db = args.db or catalog_db_path()
    if not db.exists():
        raise SystemExit(f"Catalog not found: {db}")

    # Clear stale WAL/SHM from a replaced DB if present and idle
    for suffix in ("-wal", "-shm"):
        side = Path(str(db) + suffix)
        if side.exists() and side.stat().st_size > 0:
            print(f"Note: sidecar present {side.name} ({side.stat().st_size} bytes)", flush=True)

    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    updated, scanned = refresh_dosage_sections(conn, limit=args.limit)
    print(f"Dosage sections refreshed: updated={updated} scanned={scanned}", flush=True)

    max_len = conn.execute(
        """
        SELECT MAX(LENGTH(section_text)), AVG(LENGTH(section_text))
        FROM label_sections
        WHERE section_key='dosage_and_administration' AND source='FDA_SPL'
        """
    ).fetchone()
    print(f"dosage_and_administration MAX={max_len[0]} AVG={max_len[1]:.1f}", flush=True)

    if not args.skip_sig_reparse:
        print("Clearing and rebuilding label_dose_options / label_frequency_options…", flush=True)
        conn.execute("DELETE FROM label_dose_options")
        conn.execute("DELETE FROM label_frequency_options")
        conn.commit()
        n = populate_label_dose_options(conn)
        doses = conn.execute("SELECT COUNT(*) FROM label_dose_options").fetchone()[0]
        freqs = conn.execute("SELECT COUNT(*) FROM label_frequency_options").fetchone()[0]
        print(f"SIG rebuild insert_attempts={n} doses={doses} frequencies={freqs}", flush=True)

    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    print(f"Done -> {db}", flush=True)


if __name__ == "__main__":
    main()
