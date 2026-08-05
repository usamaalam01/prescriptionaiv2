"""Title Case standardization for catalog / HITL drug display names."""

from app.services.formulary_catalog import catalog_display_name


def test_lower_to_title():
    assert catalog_display_name("metformin") == "Metformin"
    assert catalog_display_name("atorvastatin") == "Atorvastatin"


def test_upper_to_title():
    assert catalog_display_name("ATORVASTATIN") == "Atorvastatin"
    assert catalog_display_name("METFORMIN") == "Metformin"


def test_mixed_normalized_to_title():
    # Always standardize: first capital, rest lower per word
    assert catalog_display_name("eMpagLiflozin") == "Empagliflozin"
    assert catalog_display_name("Amoxicillin") == "Amoxicillin"


def test_combo_and_connectors():
    assert catalog_display_name("amoxicillin/clavulanate") == "Amoxicillin/Clavulanate"
    assert catalog_display_name("amoxicillin and clavulanate potassium") == (
        "Amoxicillin and Clavulanate Potassium"
    )


def test_hyphenated():
    assert catalog_display_name("pseudoephedrine-hcl") == "Pseudoephedrine-Hcl"


def test_none_and_blank():
    assert catalog_display_name(None) is None
    assert catalog_display_name("") == ""
    assert catalog_display_name("   ") == ""


def test_whitespace_collapsed():
    assert catalog_display_name("  metformin   hcl  ") == "Metformin Hcl"
