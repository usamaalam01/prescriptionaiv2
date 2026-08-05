"""Unit tests for FDA_SPL dosage_and_administration → dose extraction."""

from app.services.catalog_sig_options import build_cascade_options
from app.services.datasets.label_dose_extract import (
    doses_for_label_context,
    extract_dose_candidates,
    scope_doses_to_route_strength,
)


NUBEQA_DOSAGE = (
    "2 DOSAGE AND ADMINISTRATION Recommended Dosage : NUBEQA 600 mg "
    "(two 300 mg tablets) administered orally twice daily. Swallow tablets whole. "
    "Take NUBEQA with food. ( 2.1 ) The recommended dose of NUBEQA is 600 mg "
    "(two 300 mg tablets) taken orally, twice daily, with food. "
    "If a patient experiences toxicity, withhold NUBEQA or reduce dosage to "
    "300 mg twice daily until symptoms improve."
)

LIQUID_DOSAGE = (
    "2 DOSAGE AND ADMINISTRATION The recommended dose is 5 mL of the oral "
    "suspension (400 mg/5 mL) taken twice daily. Alternatively administer 2.5 mL "
    "for younger patients. Do not exceed 10 mL per dose."
)


def test_amoxicillin_mg_every_hours_to_capsule_units():
    """FDA table style '500 mg every 8 hours' → ONE capsule for 500 mg strength."""
    from app.services.datasets.catalog_store import get_medicine_by_canonical, list_label_sections
    from app.services.datasets.label_dose_extract import (
        doses_for_label_context,
        frequencies_for_label_context,
    )

    rec = get_medicine_by_canonical("Amoxicillin")
    assert rec is not None
    text = list_label_sections(rec.id).get("dosage_and_administration") or ""
    assert "500 mg every 8 hours" in text.lower() or "500 mg every" in text.lower()

    doses = doses_for_label_context(
        text,
        route="Oral",
        strength="500 mg",
        dosage_form="CAPSULE",
    )
    labels = [c.dose_label for c in doses]
    assert any("ONE" in x.upper() and "capsule" in x.lower() for x in labels), labels

    freqs = frequencies_for_label_context(
        text,
        route="Oral",
        strength="500 mg",
        dose="ONE capsule",
    )
    freq_labels = {f.frequency_label for f in freqs}
    assert "THREE times daily" in freq_labels or "TWICE daily" in freq_labels


def test_evidence_doses_amoxicillin_oral_500():
    from app.services.catalog_sig_options import evidence_doses_for_drug_route_strength

    labels, src, meta = evidence_doses_for_drug_route_strength(
        canonical_name="Amoxicillin",
        route="Oral",
        strength="500 mg",
        forms=["CAPSULE"],
    )
    assert labels, f"expected SPL doses, got src={src}"
    assert src.startswith("FDA_SPL")
    assert any("capsule" in x.lower() or "tablet" in x.lower() or "mg" in x.lower() for x in labels)
    assert meta and meta[0].get("evidence_excerpt")

    cands = extract_dose_candidates(NUBEQA_DOSAGE)
    labels = {c.dose_label.lower() for c in cands}
    assert any("two tablet" in x or x == "two tablets" for x in labels) or any(
        "two" in c.dose_label.lower() and "tablet" in c.dose_label.lower() for c in cands
    )


def test_extract_tablet_count_from_nubeqa_style():
    cands = extract_dose_candidates(NUBEQA_DOSAGE)
    labels = {c.dose_label.lower() for c in cands}
    assert any("two tablet" in x or x == "two tablets" for x in labels) or any(
        "two" in c.dose_label.lower() and "tablet" in c.dose_label.lower() for c in cands
    )


def test_extract_frequency_twice_daily_from_nubeqa():
    from app.services.datasets.label_dose_extract import extract_frequency_candidates

    freqs = extract_frequency_candidates(NUBEQA_DOSAGE)
    labels = {f.frequency_label for f in freqs}
    assert "TWICE daily" in labels


def test_frequencies_for_label_context_scoped():
    from app.services.datasets.label_dose_extract import frequencies_for_label_context

    freqs = frequencies_for_label_context(NUBEQA_DOSAGE, route="Oral", strength="300 mg")
    assert any(f.frequency_label == "TWICE daily" for f in freqs)


MULTI_REGIMEN = (
    "Adults: take two tablets orally twice daily with food. "
    "Pediatric patients: take one tablet orally once daily. "
    "Do not crush tablets."
)


def test_dose_adjacent_frequency_prefers_nearby_regimen():
    from app.services.datasets.label_dose_extract import frequencies_for_label_context

    adult = frequencies_for_label_context(
        MULTI_REGIMEN,
        route="Oral",
        strength="300 mg",
        dose="TWO tablets",
    )
    adult_labels = [f.frequency_label for f in adult]
    assert "TWICE daily" in adult_labels
    assert all(f.dose_adjacent for f in adult)
    # Once daily sits with the pediatric one-tablet phrase — excluded when adjacent hits exist
    assert "ONCE daily" not in adult_labels

    peds = frequencies_for_label_context(
        MULTI_REGIMEN,
        route="Oral",
        strength="300 mg",
        dose="ONE tablet",
    )
    peds_labels = [f.frequency_label for f in peds]
    assert "ONCE daily" in peds_labels
    assert "TWICE daily" not in peds_labels


def test_dose_adjacent_soft_fallback_when_no_nearby_freq():
    from app.services.datasets.label_dose_extract import frequencies_for_label_context

    # Dose phrase present; frequency only appears far away — still return freqs
    text = (
        "The recommended dosage is two tablets. "
        + ("Swallow whole. " * 40)
        + "Administer twice daily with food."
    )
    freqs = frequencies_for_label_context(
        text,
        route="Oral",
        strength="300 mg",
        dose="TWO tablets",
        adjacency_window=40,
    )
    assert any(f.frequency_label == "TWICE daily" for f in freqs)


def test_scope_nubeqa_to_300mg_oral_tablet():
    scoped = doses_for_label_context(
        NUBEQA_DOSAGE,
        route="Oral",
        strength="300 mg",
        dosage_form="TABLET",
    )
    labels = [c.dose_label for c in scoped]
    assert any("TWO" in x.upper() and "tablet" in x.lower() for x in labels)
    # Mass-only vague options should convert or drop when form is tablet
    assert all(c.unit_family in {"tablet", "mass"} for c in scoped)


def test_liquid_volumes_ignore_concentration_denominator():
    scoped = doses_for_label_context(
        LIQUID_DOSAGE,
        route="Oral",
        strength="400 mg/5mL",
        dosage_form="POWDER FOR ORAL SUSPENSION",
    )
    labels = [c.dose_label.lower() for c in scoped]
    assert "5 ml" in labels
    assert "2.5 ml" in labels
    assert "10 ml" in labels
    # Concentration 5 mL in "400 mg/5 mL" must not be the only hit without prose doses —
    # we still accept 5 ml from "recommended dose is 5 mL"
    assert labels


def test_fail_closed_wrong_form_family():
    cands = extract_dose_candidates(NUBEQA_DOSAGE)
    scoped = scope_doses_to_route_strength(
        cands,
        route="Oral",
        strength="400 mg/5mL",
        dosage_form="POWDER FOR ORAL SUSPENSION",
        section_text=NUBEQA_DOSAGE,
    )
    # Tablet counts should not survive liquid strength scoping
    assert not any(c.unit_family == "tablet" for c in scoped)


def test_cascade_fail_closed_without_templates(monkeypatch):
    monkeypatch.setattr(
        "app.core.config.settings.HITL_ALLOW_DOSE_TEMPLATES",
        False,
        raising=False,
    )
    # No catalog medicine → empty evidence doses
    cascade = build_cascade_options(
        drug_matched=True,
        catalog_forms=["TABLET"],
        catalog_routes=["ORAL"],
        catalog_strengths=["200 mg"],
        matched_route="Oral",
        matched_strength="200 mg",
        canonical_name="__no_such_drug_xyz__",
        allow_dose_templates=False,
    )
    assert cascade["dose"]["options"] == []
    assert cascade["dose"]["option_source"] == "FDA_SPL_none"


def test_cascade_templates_when_explicitly_allowed(monkeypatch):
    """Offline demos only: templates require catalog DB absent + allow flags."""
    monkeypatch.setattr(
        "app.services.datasets.catalog_store.catalog_available",
        lambda: False,
    )
    cascade = build_cascade_options(
        drug_matched=True,
        catalog_forms=["TABLET"],
        catalog_routes=["ORAL"],
        catalog_strengths=["200 mg"],
        matched_route="Oral",
        matched_strength="200 mg",
        matched_dose="One tablet",
        canonical_name="__no_such_drug_xyz__",
        allow_dose_templates=True,
        allow_freq_templates=True,
    )
    assert cascade["dose"]["options"]
    assert "One tablet" in cascade["dose"]["options"] or any(
        "tablet" in o.lower() for o in cascade["dose"]["options"]
    )
    assert cascade["frequency"]["options"]


def test_cascade_templates_blocked_when_catalog_db_present(monkeypatch):
    """Even with allow flags, catalog DB presence blocks template invention."""
    monkeypatch.setattr(
        "app.services.datasets.catalog_store.catalog_available",
        lambda: True,
    )
    cascade = build_cascade_options(
        drug_matched=True,
        catalog_forms=["TABLET"],
        catalog_routes=["ORAL"],
        catalog_strengths=["200 mg"],
        matched_route="Oral",
        matched_strength="200 mg",
        matched_dose="One tablet",
        canonical_name="__no_such_drug_xyz__",
        allow_dose_templates=True,
        allow_freq_templates=True,
    )
    assert cascade["dose"]["options"] == []
    assert cascade["frequency"]["options"] == []


def test_cascade_freq_fail_closed_without_templates():
    cascade = build_cascade_options(
        drug_matched=True,
        catalog_forms=["TABLET"],
        catalog_routes=["ORAL"],
        catalog_strengths=["200 mg"],
        matched_route="Oral",
        matched_strength="200 mg",
        matched_dose="One tablet",
        canonical_name="__no_such_drug_xyz__",
        allow_dose_templates=True,
        allow_freq_templates=False,
    )
    assert cascade["frequency"]["options"] == []
    assert cascade["frequency"]["option_source"] == "FDA_SPL_none"
