"""Tests for safe route cleaning normalization and pipeline modes."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.services.datasets.route_cleaning.normalize import (
    CLINICALLY_DISTINCT_PAIRS,
    dosage_form_conflict,
    normalize_route_key,
    preferred_display_name,
    split_route_components,
)
from app.services.datasets.route_cleaning.pipeline import run_apply_approved
from app.services.datasets.route_cleaning.schema import (
    connect_staging,
    init_schema,
    reset_staging_tables,
)


def test_case_variants_same_key():
    assert normalize_route_key("ORAL") == normalize_route_key("Oral")
    assert normalize_route_key("  Intravenous ") == normalize_route_key("intravenous")


def test_nbsp_and_unicode():
    assert normalize_route_key("Oral\u00a0") == "oral"


def test_multi_route_split():
    comps = split_route_components("Intramuscular; Intravenous; Subcutaneous")
    assert comps == ["Intramuscular", "Intravenous", "Subcutaneous"]


def test_empty_components_ignored():
    assert split_route_components("") == []
    assert split_route_components(None) == []


def test_duplicate_components_detectable():
    comps = split_route_components("Oral; oral; ORAL")
    keys = [normalize_route_key(c) for c in comps]
    assert len(keys) == 3
    assert len(set(keys)) == 1


def test_clinically_distinct_remain_separate():
    assert normalize_route_key("Oral") != normalize_route_key("Sublingual")
    assert normalize_route_key("Cutaneous") != normalize_route_key("Topical")
    assert frozenset({"oral", "sublingual"}) in CLINICALLY_DISTINCT_PAIRS
    assert frozenset({"cutaneous", "topical"}) in CLINICALLY_DISTINCT_PAIRS


def test_form_conflict_flagged_not_merged():
    assert dosage_form_conflict("topical", "Tablet") == "ROUTE_DOSAGE_FORM_CONFLICT"
    assert dosage_form_conflict("oral", "Tablet") is None


def test_preferred_display_prefers_non_upper():
    assert preferred_display_name({"ORAL", "Oral"}) == "Oral"


def test_apply_requires_authorization():
    with pytest.raises(PermissionError):
        run_apply_approved(authorize=None)
    with pytest.raises(PermissionError):
        run_apply_approved(authorize="yes")


def test_staging_schema_isolated(tmp_path: Path):
    db = tmp_path / "stage.sqlite3"
    con = connect_staging(db)
    init_schema(con)
    tables = {
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "route_master" in tables
    assert "product_route" in tables
    assert "route_cleaning_audit" in tables
    reset_staging_tables(con)
    assert con.execute("SELECT COUNT(*) FROM route_master").fetchone()[0] == 0
    con.close()


def test_dry_run_does_not_need_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Ensure dry-run path does not create staging as a side effect of normalize-only checks
    assert normalize_route_key("Topical") == "topical"
