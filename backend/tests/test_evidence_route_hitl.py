"""Evidence-based HITL route resolution (no clinical merging)."""

from app.services.catalog_field_match import catalog_route_from_context
from app.services.datasets.evidence_route import (
    atomic_route_labels,
    display_route_label,
    resolve_route_key,
    routes_equivalent,
)


def test_oral_case_variants_equivalent():
    assert resolve_route_key("ORAL") == resolve_route_key("Oral")
    assert routes_equivalent("ORAL", "Oral")
    assert display_route_label("ORAL") == display_route_label("Oral") or display_route_label(
        "ORAL"
    ) in {"Oral", "ORAL"}


def test_oral_not_merged_with_sublingual():
    assert resolve_route_key("Oral") != resolve_route_key("Sublingual")
    assert not routes_equivalent("Oral", "Sublingual")


def test_iv_not_merged_with_im():
    assert resolve_route_key("Intravenous") != resolve_route_key("Intramuscular")
    assert resolve_route_key("IV") == "intravenous"
    assert resolve_route_key("IM") == "intramuscular"
    assert not routes_equivalent("IV", "IM")


def test_cutaneous_not_merged_with_topical():
    assert resolve_route_key("Cutaneous") != resolve_route_key("Topical")
    assert not routes_equivalent("Cutaneous", "Topical")


def test_multi_route_split_preserves_atoms():
    labels = atomic_route_labels("Intramuscular; Intravenous; Subcutaneous")
    keys = {resolve_route_key(x) for x in labels}
    assert "intramuscular" in keys
    assert "intravenous" in keys
    assert "subcutaneous" in keys
    assert "injection" not in keys


def test_po_maps_to_oral_only():
    assert resolve_route_key("PO") == "oral"
    assert catalog_route_from_context(["Oral", "Intravenous"], ocr_route="PO") == "Oral"


def test_ambiguous_multi_route_not_autogreen_without_ocr():
    assert (
        catalog_route_from_context(["Oral", "Intravenous"], ocr_route=None) is None
    )


def test_single_route_autogreen():
    assert catalog_route_from_context(["Oral"], ocr_route=None) == "Oral"
