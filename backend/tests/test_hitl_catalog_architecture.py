"""Catalog-driven HITL architecture: fail-closed intersections, no auto-dose write."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def test_no_auto_dose_after_strength_apply(monkeypatch):
    """pharmacist_dose must only be written when the dose field is applied."""
    from app.services import field_verification as fv

    medicine = SimpleNamespace(
        id="med-1",
        session_id="sess-1",
        item_number=1,
        pharmacist_status="field_review",
        pharmacist_medicine_name="Acetaminophen",
        ai_medicine_name="Acetaminophen",
        pharmacist_route="Oral",
        pharmacist_strength=None,
        pharmacist_dose=None,
        pharmacist_frequency=None,
        pharmacist_form=None,
        pharmacist_verified_indication=None,
        ai_route="PO",
        ai_strength="1000 mg",
        ai_dose=None,
        ai_frequency=None,
        ai_form="tablet",
        formulary_matched=True,
        formulary_id="acetaminophen",
    )

    entry = {
        "formulary_id": "acetaminophen",
        "canonical_name": "Acetaminophen",
        "exact_canonical": True,
        "strengths": ["500 mg", "325 mg"],
        "doses": ["ONE tablet", "TWO tablets"],
        "frequencies": ["every 6 hours"],
        "forms": ["TABLET"],
        "routes": ["ORAL"],
        "products": [{"strength": "500 mg", "route": "ORAL", "dosage_form": "TABLET"}],
        "source": "FDA_NDC",
    }

    def _fake_cascade(**kwargs):
        matched_route = kwargs.get("matched_route")
        matched_strength = kwargs.get("matched_strength")
        matched_dose = kwargs.get("matched_dose")
        out = {
            "route": {
                "options": ["Oral"],
                "option_source": "products.route",
                "catalog_sources": ["FDA_NDC"],
                "depends_on": ["drug"],
                "context": {},
            },
            "strength": {
                "options": ["500 mg", "325 mg"] if matched_route else [],
                "option_source": "catalog_products",
                "catalog_sources": ["FDA_NDC"],
                "depends_on": ["drug", "route"],
                "context": {},
            },
            "dose": {
                "options": ["ONE tablet", "TWO tablets"] if matched_strength else [],
                "option_source": "FDA_SPL_label_dose_options",
                "catalog_sources": ["FDA_SPL"],
                "depends_on": ["drug", "route", "strength"],
                "context": {},
                "evidence": [],
            },
            "frequency": {
                "options": ["every 6 hours"] if matched_dose else [],
                "option_source": "FDA_SPL_label_dose_frequency_options",
                "catalog_sources": ["FDA_SPL"],
                "depends_on": ["drug", "route", "strength", "dose"],
                "context": {},
                "evidence": [],
            },
            "forms_for_route": ["TABLET"],
        }
        return out

    monkeypatch.setattr(fv.prescription_service, "get_owned_session", lambda *a, **k: None)
    monkeypatch.setattr(fv, "resolve_hitl_drug", lambda *_a, **_k: entry)
    monkeypatch.setattr(fv, "build_cascade_options", _fake_cascade)
    monkeypatch.setattr(
        fv,
        "build_field_state",
        lambda med: {
            "fields": {
                "strength": {"locked": False, "value": med.pharmacist_strength},
                "dose": {"locked": False, "value": med.pharmacist_dose},
            },
            "can_confirm": False,
            "next_field": "dose",
        },
    )
    monkeypatch.setattr(fv, "record_hitl_event", lambda *a, **k: None)
    monkeypatch.setattr(fv, "_invalidate_session_analytics", lambda *a, **k: None)
    monkeypatch.setattr(fv, "_prefer_dose_for_ocr_total", lambda *a, **k: "TWO tablets")

    db = MagicMock()
    db.get.return_value = medicine

    fv.apply_field_correction(
        db,
        pharmacist=SimpleNamespace(id="u1"),
        session_id="sess-1",
        medicine_id="med-1",
        field="strength",
        value="500 mg",
    )
    assert medicine.pharmacist_strength == "500 mg"
    assert medicine.pharmacist_dose is None  # no auto-write


def test_ambiguous_multi_route_stays_unselected():
    from app.services.catalog_field_match import catalog_route_from_context

    assert (
        catalog_route_from_context(
            ["Oral", "Injection"],
            ocr_route=None,
            catalog_forms=["TABLET", "INJECTION"],
            ocr_form=None,
            ocr_dose=None,
        )
        is None
    )


def test_bare_strength_does_not_imply_route():
    from app.services.catalog_field_match import catalog_route_from_context

    assert (
        catalog_route_from_context(
            ["Oral", "Injection", "Topical"],
            ocr_route=None,
            ocr_form="1000 mg",
            ocr_dose=None,
            catalog_forms=["TABLET"],
        )
        is None
    )


def test_strict_intersections_query_layer(tmp_path, monkeypatch):
    from app.services.datasets import catalog_store as store
    from app.services.datasets import hitl_catalog_query as hq

    db = tmp_path / "cat.sqlite3"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE medicines (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            canonical_key TEXT UNIQUE,
            drugbank_id TEXT,
            product_ndc TEXT,
            dosage_forms TEXT,
            routes TEXT,
            sources TEXT,
            indication TEXT,
            spl_set_id TEXT
        );
        CREATE TABLE aliases (
            alias_key TEXT NOT NULL,
            medicine_id INTEGER NOT NULL,
            alias_raw TEXT NOT NULL,
            PRIMARY KEY (alias_key, medicine_id)
        );
        CREATE TABLE strengths (
            medicine_id INTEGER NOT NULL,
            strength TEXT NOT NULL,
            PRIMARY KEY (medicine_id, strength)
        );
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            strength TEXT,
            dosage_form TEXT,
            route TEXT,
            product_ndc TEXT,
            spl_set_id TEXT,
            source TEXT NOT NULL
        );
        CREATE TABLE label_dose_options (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            route TEXT NOT NULL,
            strength TEXT NOT NULL,
            dosage_form TEXT,
            dose_label TEXT NOT NULL,
            evidence_excerpt TEXT,
            spl_set_id TEXT,
            source TEXT NOT NULL DEFAULT 'FDA_SPL',
            confidence REAL NOT NULL DEFAULT 0.8,
            UNIQUE (medicine_id, route, strength, dose_label)
        );
        CREATE TABLE label_dose_frequency_options (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            route TEXT NOT NULL,
            strength TEXT NOT NULL,
            dose_label TEXT NOT NULL,
            frequency_label TEXT NOT NULL,
            evidence_excerpt TEXT,
            spl_set_id TEXT,
            source TEXT NOT NULL DEFAULT 'FDA_SPL',
            confidence REAL NOT NULL DEFAULT 0.8,
            UNIQUE (medicine_id, route, strength, dose_label, frequency_label)
        );
        """
    )
    conn.execute(
        "INSERT INTO medicines VALUES (1,'Demo Drug','demo drug',NULL,NULL,'[]','[]','[\"FDA_NDC\"]',NULL,NULL)"
    )
    conn.execute("INSERT INTO aliases VALUES ('demo drug',1,'Demo Drug')")
    conn.execute(
        "INSERT INTO products(medicine_id,strength,dosage_form,route,product_ndc,source) "
        "VALUES (1,'500 mg','TABLET','ORAL',NULL,'FDA_NDC')"
    )
    conn.execute(
        "INSERT INTO products(medicine_id,strength,dosage_form,route,product_ndc,source) "
        "VALUES (1,'500 mg','INJECTION','INTRAVENOUS',NULL,'FDA_NDC')"
    )
    conn.execute(
        "INSERT INTO label_dose_options(medicine_id,route,strength,dose_label,evidence_excerpt,source,confidence) "
        "VALUES (1,'Oral','500 mg','ONE tablet','give one tablet','FDA_SPL',0.9)"
    )
    conn.execute(
        "INSERT INTO label_dose_options(medicine_id,route,strength,dose_label,evidence_excerpt,source,confidence) "
        "VALUES (1,'Intravenous','500 mg','5 mL','inject 5 mL','FDA_SPL',0.9)"
    )
    conn.execute(
        "INSERT INTO label_dose_frequency_options"
        "(medicine_id,route,strength,dose_label,frequency_label,evidence_excerpt,source,confidence) "
        "VALUES (1,'Oral','500 mg','ONE tablet','TWICE daily','twice daily','FDA_SPL',0.9)"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(store, "catalog_db_path", lambda: db)
    store.clear_runtime_catalog_copy_cache()
    if hasattr(store._get_medicine_cached, "cache_clear"):
        store._get_medicine_cached.cache_clear()
    if hasattr(store._alias_rows, "cache_clear"):
        store._alias_rows.cache_clear()
    # Avoid staging a shared temp copy of a previous catalog during unit tests
    monkeypatch.setattr(store, "_runtime_catalog_copy", lambda: None)

    routes, rsrc = hq.query_routes("Demo Drug")
    assert {o["value"] for o in routes} == {"Oral", "Intravenous"}
    assert rsrc == "products.route"

    strengths_oral, _ = hq.query_strengths("Demo Drug", route="Oral")
    assert [o["value"] for o in strengths_oral] == ["500 mg"]

    doses_oral, dsrc = hq.query_doses("Demo Drug", route="Oral", strength="500 mg")
    assert [o["value"] for o in doses_oral] == ["ONE tablet"]
    assert "label_dose" in dsrc

    # Intravenous dose must not leak into Oral intersection
    doses_inj, _ = hq.query_doses("Demo Drug", route="Intravenous", strength="500 mg")
    assert [o["value"] for o in doses_inj] == ["5 mL"]

    freqs, fsrc = hq.query_frequencies(
        "Demo Drug", route="Oral", strength="500 mg", dose="ONE tablet"
    )
    assert [o["value"] for o in freqs] == ["TWICE daily"]
    assert "dose_frequency" in fsrc

    # Wrong dose → empty intersection
    empty, _ = hq.query_frequencies(
        "Demo Drug", route="Oral", strength="500 mg", dose="TWO tablets"
    )
    assert empty == []


def test_dose_frequency_and_indication_schema_backfill(tmp_path):
    from app.services.datasets.build_index import (
        ensure_label_dose_options_table,
        populate_indication_options,
        _insert_dose_options_from_section,
    )

    db = tmp_path / "backfill.sqlite3"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE medicines (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            canonical_key TEXT UNIQUE,
            drugbank_id TEXT,
            product_ndc TEXT,
            dosage_forms TEXT,
            routes TEXT,
            sources TEXT,
            indication TEXT,
            spl_set_id TEXT
        );
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            strength TEXT,
            dosage_form TEXT,
            route TEXT,
            product_ndc TEXT,
            spl_set_id TEXT,
            source TEXT NOT NULL
        );
        CREATE TABLE label_sections (
            medicine_id INTEGER NOT NULL,
            section_key TEXT NOT NULL,
            section_text TEXT NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY (medicine_id, section_key, source)
        );
        """
    )
    ensure_label_dose_options_table(conn)
    conn.execute(
        "INSERT INTO medicines VALUES (1,'Acetaminophen','acetaminophen',NULL,NULL,"
        "'[\"TABLET\"]','[\"ORAL\"]','[\"FDA_SPL\"]',"
        "'Uses temporarily reduces fever relieves headache','set1')"
    )
    conn.execute(
        "INSERT INTO products(medicine_id,strength,dosage_form,route,source) "
        "VALUES (1,'500 mg','TABLET','ORAL','FDA_NDC')"
    )
    section = (
        "DOSAGE AND ADMINISTRATION Adults: take TWO tablets every 6 hours "
        "while symptoms persist. Do not exceed 6 tablets in 24 hours."
    )
    conn.execute(
        "INSERT INTO label_sections VALUES (1,'dosage_and_administration',?, 'FDA_SPL')",
        (section,),
    )
    conn.execute(
        "INSERT INTO label_sections VALUES (1,'indications_and_usage',?, 'FDA_SPL')",
        ("INDICATIONS AND USAGE temporarily reduces fever; relieves headache",),
    )
    conn.commit()

    n = _insert_dose_options_from_section(conn, 1, section_text=section, spl_set_id="set1")
    assert n > 0
    dose_freq = conn.execute(
        "SELECT dose_label, frequency_label FROM label_dose_frequency_options"
    ).fetchall()
    assert dose_freq, "expected dose↔frequency typed rows"
    ind_n = populate_indication_options(conn)
    assert ind_n > 0
    labels = [
        r[0].lower()
        for r in conn.execute("SELECT indication_label FROM indication_options").fetchall()
    ]
    assert any("fever" in x or "headache" in x for x in labels)
    conn.close()


def test_template_not_confirm_eligible_when_catalog_available(monkeypatch):
    from app.services import field_verification as fv

    medicine = SimpleNamespace(
        id="m1",
        session_id="s1",
        item_number=1,
        pharmacist_status="field_review",
        pharmacist_medicine_name="Acetaminophen",
        ai_medicine_name="Acetaminophen",
        pharmacist_route="Oral",
        pharmacist_strength="500 mg",
        pharmacist_dose="TWO tablets",
        pharmacist_frequency="every 6 hours",
        pharmacist_form=None,
        pharmacist_verified_indication=None,
        ai_route="PO",
        ai_strength="1000 mg",
        ai_dose="TWO tablets",
        ai_frequency="every 6 hours",
        ai_form="tablet",
        formulary_matched=True,
        formulary_id="x",
        unable_to_verify=False,
        parser_confidence=0.9,
    )

    entry = {
        "formulary_id": "x",
        "canonical_name": "Acetaminophen",
        "exact_canonical": True,
        "strengths": ["500 mg"],
        "doses": ["TWO tablets"],
        "frequencies": ["every 6 hours"],
        "forms": ["TABLET"],
        "routes": ["ORAL"],
        "products": [{"strength": "500 mg", "route": "ORAL", "dosage_form": "TABLET"}],
        "source": "FDA_NDC",
    }

    def _cascade(**kwargs):
        return {
            "route": {
                "options": ["Oral"],
                "option_source": "catalog_routes",
                "catalog_sources": ["FDA_NDC"],
                "depends_on": ["drug"],
                "context": {},
            },
            "strength": {
                "options": ["500 mg"],
                "option_source": "catalog_products",
                "catalog_sources": ["FDA_NDC"],
                "depends_on": ["drug", "route"],
                "context": {},
            },
            "dose": {
                "options": ["TWO tablets"],
                "option_source": "catalog_route_form_derived",
                "catalog_sources": ["FDA_NDC"],
                "depends_on": ["drug", "route", "strength"],
                "context": {},
                "evidence": [],
            },
            "frequency": {
                "options": ["every 6 hours"],
                "option_source": "seed_formulary",
                "catalog_sources": ["FDA_NDC"],
                "depends_on": ["drug", "route", "strength", "dose"],
                "context": {},
                "evidence": [],
            },
            "forms_for_route": ["TABLET"],
        }

    monkeypatch.setattr(fv, "resolve_hitl_drug", lambda *_a, **_k: entry)
    monkeypatch.setattr(fv, "build_cascade_options", _cascade)
    monkeypatch.setattr(fv, "_indication_options_catalog", lambda *_a, **_k: [])
    monkeypatch.setattr(
        "app.services.datasets.catalog_store.catalog_available", lambda: True
    )

    state = fv.build_field_state(medicine)
    assert state["fields"]["dose"]["status"] == "green"
    assert state["fields"]["frequency"]["status"] == "green"
    assert state["can_confirm"] is False
    assert "template" in (state.get("confirm_hint") or "").lower() or "catalog" in (
        state.get("confirm_hint") or ""
    ).lower()


def test_augmentin_ranking_is_generic_not_named():
    from app.services.field_verification import _pick_best_catalog_hit

    hits = [
        SimpleNamespace(
            canonical_name="Amoxicillin",
            matched_alias="augmentin",
            strengths=[],
            dosage_forms=[],
            routes=[],
            source="FDA_SPL",
            score=90,
        ),
        SimpleNamespace(
            canonical_name="Amoxicillin and Clavulanate Potassium",
            matched_alias="augmentin",
            strengths=["875 mg"],
            dosage_forms=["TABLET"],
            routes=["ORAL"],
            source="FDA_NDC",
            score=88,
        ),
    ]
    best = _pick_best_catalog_hit(hits, "Augmentin")
    assert best.canonical_name == "Amoxicillin and Clavulanate Potassium"
    # Ensure source has no named brand branch remaining
    import inspect
    from app.services import field_verification, formulary_catalog

    assert "augmentin" not in inspect.getsource(field_verification._pick_best_catalog_hit).lower()
    assert "augmentin" not in inspect.getsource(formulary_catalog.suggest_drugs).lower()


def test_catalog_db_blocks_form_inferred_routes(tmp_path, monkeypatch):
    """With catalog DB mounted, empty products.route must not invent Oral from TABLET."""
    from app.services.datasets import catalog_store as store
    from app.services.catalog_sig_options import build_cascade_options

    db = tmp_path / "empty_routes.sqlite3"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE medicines (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            canonical_key TEXT UNIQUE,
            drugbank_id TEXT,
            product_ndc TEXT,
            dosage_forms TEXT,
            routes TEXT,
            sources TEXT,
            indication TEXT,
            spl_set_id TEXT
        );
        CREATE TABLE aliases (
            alias_key TEXT NOT NULL,
            medicine_id INTEGER NOT NULL,
            alias_raw TEXT NOT NULL,
            PRIMARY KEY (alias_key, medicine_id)
        );
        CREATE TABLE strengths (
            medicine_id INTEGER NOT NULL,
            strength TEXT NOT NULL,
            PRIMARY KEY (medicine_id, strength)
        );
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            strength TEXT,
            dosage_form TEXT,
            route TEXT,
            product_ndc TEXT,
            spl_set_id TEXT,
            source TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO medicines VALUES (1,'Shell Drug','shell drug',NULL,NULL,"
        "'[\"TABLET\"]','[]','[\"FDA_NDC\"]',NULL,NULL)"
    )
    conn.execute("INSERT INTO aliases VALUES ('shell drug',1,'Shell Drug')")
    # Product row with no route — must not invent Oral from dosage form
    conn.execute(
        "INSERT INTO products(medicine_id,strength,dosage_form,route,source) "
        "VALUES (1,'500 mg','TABLET',NULL,'FDA_NDC')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(store, "catalog_db_path", lambda: db)
    store.clear_runtime_catalog_copy_cache()
    if hasattr(store._get_medicine_cached, "cache_clear"):
        store._get_medicine_cached.cache_clear()
    if hasattr(store._alias_rows, "cache_clear"):
        store._alias_rows.cache_clear()
    monkeypatch.setattr(store, "_runtime_catalog_copy", lambda: None)
    monkeypatch.setattr(store, "catalog_available", lambda: True)

    cascade = build_cascade_options(
        drug_matched=True,
        catalog_forms=["TABLET"],
        catalog_routes=[],
        catalog_strengths=["500 mg"],
        canonical_name="Shell Drug",
        allow_dose_templates=True,
        allow_freq_templates=True,
    )
    assert cascade["route"]["options"] == []
    assert "products" in cascade["route"]["option_source"]


def test_acetaminophen_single_route_resolves_benztropine_ambiguous_does_not():
    """Preserve Acetaminophen single-route resolve; Benztropine multi-route stays open."""
    from app.services.catalog_field_match import catalog_route_from_context

    assert (
        catalog_route_from_context(
            ["Oral"],
            ocr_route=None,
            catalog_forms=["TABLET"],
            ocr_form="tablet",
            ocr_dose="TWO tablets",
        )
        == "Oral"
    )
    assert (
        catalog_route_from_context(
            ["Oral", "Injection"],
            ocr_route=None,
            catalog_forms=["TABLET", "INJECTION"],
            ocr_form="tablet",
            ocr_dose=None,
        )
        is None
    )
    # Explicit OCR route may resolve Benztropine-like ambiguity
    assert (
        catalog_route_from_context(
            ["Oral", "Injection"],
            ocr_route="PO",
            catalog_forms=["TABLET", "INJECTION"],
            ocr_form=None,
            ocr_dose=None,
        )
        == "Oral"
    )
