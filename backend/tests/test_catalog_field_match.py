"""Catalog-first OCR→option matching (no per-drug special cases)."""

from app.services.catalog_field_match import (
    catalog_dose_from_ocr_total,
    catalog_strength_from_ocr,
    prefer_unit_strengths_for_ocr,
)


def test_strength_exact_match():
    assert catalog_strength_from_ocr("40 mg", ["20 mg", "40 mg", "80 mg"]) == "40 mg"


def test_strength_nx_unit_any_drug():
    # OCR total dose vs catalog unit — works for any drug, not Acetaminophen-only
    assert catalog_strength_from_ocr("1000 mg", ["325 mg", "500 mg"]) == "500 mg"
    assert catalog_strength_from_ocr("60 mg", ["10 mg", "20 mg", "30 mg"]) == "30 mg"
    assert catalog_strength_from_ocr("750 mg", ["250 mg", "500 mg"]) == "250 mg"


def test_strength_rejects_unrelated():
    assert catalog_strength_from_ocr("37 mg", ["20 mg", "40 mg"]) is None


def test_dose_from_multiplier():
    doses = ["ONE tablet", "TWO tablets", "THREE tablets"]
    assert catalog_dose_from_ocr_total("1000 mg", "500 mg", doses) == "TWO tablets"
    assert catalog_dose_from_ocr_total("60 mg", "20 mg", doses) == "THREE tablets"


def test_prefer_unit_reorder():
    out = prefer_unit_strengths_for_ocr("1000 mg", ["325 mg", "500 mg", "80 mg"])
    assert out[0] == "500 mg"


def test_route_from_ocr_route():
    from app.services.catalog_field_match import catalog_route_from_context

    assert catalog_route_from_context(["Oral", "Injection"], ocr_route="PO") == "Oral"
    # IV is Intravenous — not merged into Injection
    assert catalog_route_from_context(["Oral", "Intravenous"], ocr_route="IV") == "Intravenous"


def test_route_single_option():
    from app.services.catalog_field_match import catalog_route_from_context

    assert catalog_route_from_context(["Inhalation"]) == "Inhalation"


def test_route_form_cue_suggests_but_does_not_auto_resolve():
    from app.services.catalog_field_match import (
        catalog_route_from_context,
        catalog_route_suggestions,
    )

    opts = ["Oral", "Injection", "Topical"]
    # Multi-route: form/dose cue must not auto-green
    assert (
        catalog_route_from_context(opts, ocr_dose="TWO tablets") is None
    )
    suggested = catalog_route_suggestions(opts, ocr_dose="TWO tablets")
    assert suggested[0] == "Oral"


def test_route_never_invents_from_bare_mg():
    from app.services.catalog_field_match import catalog_route_from_context

    # Bare mg / form majority must not imply a route when multiple options exist
    assert (
        catalog_route_from_context(
            ["Oral", "Injection", "Topical"],
            ocr_form=None,
            ocr_dose=None,
            catalog_forms=["INJECTION", "INJECTION, SOLUTION"],
        )
        is None
    )


def test_route_no_majority_vote():
    from app.services.catalog_field_match import catalog_route_from_context

    assert (
        catalog_route_from_context(
            ["Oral", "Injection", "Topical"],
            catalog_forms=["TABLET", "TABLET, FILM COATED", "TABLET", "INJECTION"],
        )
        is None
    )
