"""Staging / audit schema for route cleaning (separate SQLite — never the catalog)."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS route_master (
  route_id INTEGER PRIMARY KEY,
  route_code TEXT NOT NULL UNIQUE,
  route_name TEXT NOT NULL,
  route_name_normalized TEXT NOT NULL UNIQUE,
  route_category TEXT,
  source_system TEXT,
  source_code TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS route_aliases (
  route_alias_id INTEGER PRIMARY KEY,
  route_id INTEGER NOT NULL REFERENCES route_master(route_id),
  alias_raw TEXT NOT NULL,
  alias_normalized TEXT NOT NULL,
  source_system TEXT,
  mapping_rule TEXT NOT NULL,
  validation_status TEXT NOT NULL,
  match_type TEXT,
  confidence REAL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (alias_normalized, route_id)
);

CREATE TABLE IF NOT EXISTS product_route (
  product_route_id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL,
  medicine_id INTEGER,
  route_id INTEGER REFERENCES route_master(route_id),
  route_component_raw TEXT,
  route_raw_full TEXT,
  source_order INTEGER,
  source_system TEXT,
  source_record_id TEXT,
  source_evidence TEXT,
  dosage_form TEXT,
  validation_status TEXT NOT NULL,
  issue_codes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (product_id, route_id, source_system, route_component_raw)
);

CREATE TABLE IF NOT EXISTS route_cleaning_audit (
  audit_id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,
  product_id INTEGER,
  medicine_id INTEGER,
  source_table TEXT,
  source_primary_key TEXT,
  route_raw TEXT,
  route_component_raw TEXT,
  route_normalized TEXT,
  route_id INTEGER,
  rule_id TEXT,
  issue_code TEXT,
  severity TEXT,
  before_value TEXT,
  after_value TEXT,
  validation_status TEXT,
  reviewed_by TEXT,
  reviewed_at TEXT,
  applied_by TEXT,
  applied_at TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pr_product ON product_route(product_id);
CREATE INDEX IF NOT EXISTS idx_pr_status ON product_route(validation_status);
CREATE INDEX IF NOT EXISTS idx_alias_norm ON route_aliases(alias_normalized);
CREATE INDEX IF NOT EXISTS idx_audit_run ON route_cleaning_audit(run_id);
"""


def staging_db_path(data_dir: Path) -> Path:
    return data_dir / "route_cleaning_staging.sqlite3"


def connect_staging(path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if read_only:
        if not path.exists():
            raise FileNotFoundError(path)
        uri = f"file:{path.as_posix()}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
    else:
        con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_schema(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA_SQL)
    con.commit()


def reset_staging_tables(con: sqlite3.Connection) -> None:
    """Clear staged content for a fresh STAGE run (does not touch catalog)."""
    for t in (
        "route_cleaning_audit",
        "product_route",
        "route_aliases",
        "route_master",
    ):
        con.execute(f"DELETE FROM {t}")
    con.commit()
